from typing import List, Optional
import json
import re

import pandas as pd
from openai import OpenAI

from utils import get_logger

class TableExtractor:
    def __init__(self, model: str = "gpt-4o", row_threshold: int = 5):
        self.logger = get_logger(__name__)

        self.client = OpenAI()
        self.model = model
        self.row_threshold = row_threshold

    def _build_prompt(self, text: str, previous_columns: Optional[List[str]] = None) -> List[dict]:
        system_msg = (
            "You are a data extraction tool. Your job is to extract all tables from raw text "
            "extracted from PDF files. Return only JSON arrays (one per table)."
        )

        user_msg = (
            "Given the following OCR or PDF-extracted raw text, extract all tables you can find. "
            "Output only valid JSON arrays. Wrap each in triple backticks using the json tag like:\n"
            "```json\n[{...}, {...}]\n```\n\n"
            "If multiple tables exist, include them all one after another.\n\n"
        )

        if previous_columns:
            joined_cols = ", ".join(previous_columns)
            user_msg += (
                f"The previous page contained tables with the following column names:\n[{joined_cols}]\n"
                "If column names are missing from the current page, attempt to assign them "
                "based on the structure and values, using these previous column names as a guide.\n\n"
            )

        user_msg += f"RAW TEXT:\n{text}"

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def extract(self, text: str) -> List[pd.DataFrame]:
        """
        Extract tables from a single piece of raw text.

        Args:
            text (str): Parsed PDF text.

        Raises:
            ValueError: If no valid JSON block is found in the response.

        Returns:
            List[pd.DataFrame]: List of one or more extracted tables.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_prompt(text),
                temperature=0,
                max_tokens=4096,
            )

            content = response.choices[0].message.content.strip()

            # Extract all JSON arrays using regex
            json_blocks = re.findall(r"```json\n(.*?)```", content, re.DOTALL)
            if not json_blocks:
                raise ValueError("No valid JSON blocks found in response.")

            tables = []
            for block in json_blocks:
                try:
                    table_data = json.loads(block)
                    df = pd.DataFrame(table_data)
                    tables.append(df)
                except Exception as e:
                    self.logger.warning(
                        "⚠️ Failed to parse one JSON table: %s\n\n%s\n",
                        e, block
                    )

            return tables

        except Exception as e:
            self.logger.warning(
                "❌ OpenAI API call failed: %s", str(e)
            )
            return []

    def extract_from_page(self, page_text: str, previous_columns:Optional[List[str]]=None) -> List[pd.DataFrame]:
        """
        Extract tables frrom a single page of parsed PDF text.

        Args:
            page_text (str): Parsed PDF text of a single page.
            previous_columns (List[str]): The columns found on the previous page.

        Raises:
            ValueError: If no valid JSON block is found in the response.

        Returns:
            List[pd.DataFrame]: List of one or more extracted tables.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_prompt(page_text, previous_columns),
                temperature=0,
                max_tokens=4096,
            )

            content = response.choices[0].message.content.strip()
            json_blocks = re.findall(r"```json\n(.*?)```", content, re.DOTALL)

            if not json_blocks:
                raise ValueError("No valid JSON blocks found in response.")

            tables = []
            for block in json_blocks:
                try:
                    table_data = json.loads(block)
                    df = pd.DataFrame(table_data)
                    tables.append(df)
                except Exception as e:
                    self.logger.warning(
                        "⚠️ Failed to parse one JSON table: %s\n\n%s\n",
                        str(e), block
                    )

            return tables

        except Exception as e:
            self.logger.warning(
                "❌ OpenAI API call failed on page: %s", str(e)
            )
            return []

    def extract_from_pages(self, pages_text: List[str]) -> List[pd.DataFrame]:
        """
        Extract tables from each page independently and combine the results.

        Args:
            pages_text (List[str]): A list of text blocks, one per PDF page.

        Returns:
            List[pd.DataFrame]: All tables found across all pages.
        """
        all_tables = []
        previous_column_names = []
        for i, page_text in enumerate(pages_text):
            self.logger.info(
                "📄 Processing page %d...", i + 1
            )
            page_tables = self.extract_from_page(page_text, previous_column_names)
            
            filtered_tables = []
            for table in page_tables:
                if len(table) >= self.row_threshold:
                    filtered_tables.append(table)
                else:
                    self.logger.warning(
                        "⚠️ Skipped table on page %d: only %d rows.",
                        i + 1, len(table)
                    )

            all_tables.extend(filtered_tables)
            if filtered_tables:
                previous_column_names = list(filtered_tables[-1].columns)

        return all_tables
