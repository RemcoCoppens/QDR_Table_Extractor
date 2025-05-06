from typing import List, Tuple, Union, IO
from collections import defaultdict

import pdfplumber
import numpy as np
import pandas as pd

from utils import extract_rows_from_page, get_logger


class TextualParser:
    def __init__(self, file:Union[str, IO[bytes]]):
        self.logger = get_logger(__name__)
        self.__method__ = "TEXT-PDF"
        self.file = file
        self.word_spacing = 4
        self.inaccuracy_threshold = 5

        self.format__column_spacing = 6
        self.format__min_gap = 2
        self.format__line_length = 200

        self.page_delimiter = '\n------------\n'
        self.max_pages_ingestion = 10

        self.pages_text = []
        self.raw_text = self.parse_pdf_and_format()

    def combine_close_words(
            self, rows: List[List[Tuple]], word_spacing: int = 4
    ) -> List[List[Tuple]]:
        """
        Args:
            rows (List[List[Tuple]]): Collection of words per row.
                    Formatted as: (text, x_left, x_right, y_top, y_bottom)
            word_spacing (int, optional): The space between words. Defaults to 4.

        Returns:
            List[List[Tuple]]: New collection of words per row, combined using word spacing.
        """
        merged_rows = []
        for row in rows:
            if not row:
                merged_rows.append([])
                continue

            merged_words = [row[0]]

            for i in range(1, len(row)):
                last_word = merged_words[-1]
                current_word = row[i]
                gap = abs(last_word[2] - current_word[1])
                
                if gap <= word_spacing:
                    combined_text = last_word[0] + " " + current_word[0]
                    new_x_right = current_word[2]

                    merged_words[-1] = (
                        combined_text, last_word[1], new_x_right,
                        last_word[3], last_word[4],
                    )
                else:
                    merged_words.append(current_word)

            merged_rows.append(merged_words)
        
        return merged_rows
    
    def create_coords_dataframe(self, word_rows:List[List[Tuple]]) -> pd.DataFrame:
        """
        Organize the word rows in a DataFrame with X and Y coordinates per word combination.

        Args:
            word_rows (List[List[Tuple]]): Aggregated word rows.

        Returns:
            pd.DataFrame: Overview of word groups and their coordinates.
        """
        combined_word_rows = self.combine_close_words(rows=word_rows)
        deconstructed_text = {"x": [], "y": [], "text": []}
        for row in combined_word_rows:
            for word_inf in row:
                deconstructed_text["x"].append(word_inf[1])
                deconstructed_text["y"].append(word_inf[3])
                deconstructed_text["text"].append(word_inf[0])

        return pd.DataFrame(data=deconstructed_text)

    def group_coords(self, values:pd.Series) -> List[int]:
        """
        Group coordinate values using the inaccuracy threshold.

        Args:
            values (pd.Series): Coordinate values.

        Returns:
            List[int]: Bins used to cluster coordinates.
        """
        sorted_vals = sorted(values)
        groups = []
        for val in sorted_vals:
            if not groups or abs(val - groups[-1][-1]) > self.inaccuracy_threshold:
                groups.append([val])
            else:
                groups[-1].append(val)
        return [int(np.mean(g)) for g in groups]
    
    def map_to_bin(self, val:int, y_bins:List[int]) -> int:
        """
        Map the (aggregated) word coordinate to a bin.

        Args:
            val (int): Original coordinate.
            y_bins (List[int]): A list of integer bins.

        Returns:
            int: Assigned bin.
        """
        for bin_y in y_bins:
            if abs(val - bin_y) <= 5:
                return bin_y
        return val
    
    def add_bin_index(self, df:pd.DataFrame) -> pd.DataFrame:
        """
        Add bin index for filtering and clustering.

        Args:
            df (pd.DataFrame): Dataframe with binned coordinates.

        Returns:
            pd.DataFrame: Dataframe with bin index included.
        """
        sorted_y_bins = sorted(df['y_bin'].unique(), reverse=False)
        ybin_to_index = {y_bin: i for i, y_bin in enumerate(sorted_y_bins)}
        df['y_index'] = df['y_bin'].map(ybin_to_index)

        sorted_x_bins = sorted(df['x_bin'].unique(), reverse=False)
        xbin_to_index = {x_bin: i for i, x_bin in enumerate(sorted_x_bins)}
        df['x_index'] = df['x_bin'].map(xbin_to_index)
        return df
    
    def get_binned_coords_dataframe(self, word_rows:List[List[Tuple]]) -> pd.DataFrame:
        """
        Organize the words in a row-based dataframe with binned coordinates.

        Args:
            word_rows (List[List[Tuple]]): Aggregated word rows.

        Returns:
            pd.DataFrame: Overview of word groups and their binned coordinates.
        """
        df = self.create_coords_dataframe(word_rows=word_rows)
        y_bins = self.group_coords(df['y'].tolist())
        df['y_bin'] = df['y'].apply(lambda x: self.map_to_bin(x, y_bins))

        x_bins = self.group_coords(df['x'].tolist())
        df['x_bin'] = df['x'].apply(lambda x: self.map_to_bin(x, x_bins))

        return self.add_bin_index(df)
    
    def format_text_by_grid_position(self, df:pd.DataFrame):
        """
        Format text so each word starts at a fixed position based on x_index,
        unless the previous word overflows into that space.

        Args:
            df (pd.DataFrame): Input dataframe with y_index, x_index, and text.
            column_spacing (int): Minimum space between columns (default = 4).
            min_gap (int): Minimum spaces between consecutive words (if overlap happens).
            line_length (int): Max length of each line (characters).

        Returns:
            str: Formatted string preserving relative x/y positions.
        """
        # Group words by y_index
        lines_by_y = defaultdict(list)
        for _, row in df.iterrows():
            lines_by_y[row['y_index']].append((row['x_index'], row['text']))

        # Estimate base column positions by x_index
        x_indices = sorted(df['x_index'].unique())
        x_index_to_col = {}
        current_pos = 0
        for x in x_indices:
            x_index_to_col[x] = current_pos
            current_pos += self.format__column_spacing

        # Build lines
        formatted_lines = []
        for y_index in sorted(lines_by_y.keys()):
            line = [" "] * self.format__line_length
            cursor_pos = 0

            for x_index, text in sorted(lines_by_y[y_index], key=lambda x: x[0]):
                target_pos = x_index_to_col.get(x_index, cursor_pos)

                # Adjust if the text would overwrite previous text
                actual_pos = max(cursor_pos + self.format__min_gap, target_pos)

                # Place text
                for i, char in enumerate(text):
                    if actual_pos + i < self.format__line_length:
                        line[actual_pos + i] = char

                # Move cursor forward
                cursor_pos = actual_pos + len(text)

            formatted_lines.append("".join(line).rstrip())

        return "\n".join(formatted_lines)

    def parse_pdf_and_format(self) -> str:
        """
        Parse each page of the PDF and combine into a single formatted string.
        Maintains consistent y_index offset between pages.

        Returns:
            str: Full formatted text with all pages combined.
        """
        all_dfs = []
        y_offset = 0
        pages_text = []

        with pdfplumber.open(self.file) as pdf:
            for page_num, page in enumerate(pdf.pages[:self.max_pages_ingestion]):
                try:
                    word_rows, _ = extract_rows_from_page(
                        page, vertical_threshold=5, horizontal_threshold=10
                    )
                    df = self.get_binned_coords_dataframe(word_rows)

                    df['y_index'] += y_offset
                    y_offset = df['y_index'].max() + 1

                    all_dfs.append(df)

                    page_text = self.format_text_by_grid_position(df=df)
                    pages_text.append(page_text)

                except Exception as e:
                    self.logger.warning(f"Failed to process page {page_num + 1}: {e}")

        self.pages_text = pages_text
        full_text = self.page_delimiter.join(pages_text)
        return full_text


if __name__ == "__main__":
    pdf_table_parser = TextualParser(file="ZZ_test_files/table_example_2.pdf")
    formatted_pdf = pdf_table_parser.parse_pdf_and_format()
