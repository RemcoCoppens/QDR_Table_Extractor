from typing import List, Tuple
import io

from pypdf import PdfReader
import tiktoken

def count_tokens_in_pdf(file: io.BytesIO, model: str = "gpt-3.5-turbo") -> int:
    """
    Count the number of tokens in a PDF file using OpenAI-compatible tokenizer.

    Args:
        file (io.BytesIO): The PDF file in memory.
        model (str): Name of the model to match tokenizer rules (e.g., 'gpt-4').

    Returns:
        int: Total estimated token count.
    """
    encoding = tiktoken.encoding_for_model(model)
    pdf_reader = PdfReader(file)
    total_tokens = 0

    for page in pdf_reader.pages:
        text = page.extract_text() or ""
        total_tokens += len(encoding.encode(text))

    return total_tokens

def group_words_into_lines(words, vertical_threshold=5) -> List[List[dict]]:
    """
    Groups words into lines based on similar 'top' coordinates.
    
    Args:
        words (list): List of word dictionaries with positional info.
        vertical_threshold (float): Maximum difference in 'top' to consider words in the same line.
    
    Returns:
        list: A list of lines; each line is a list of word dictionaries.
    """
    words_sorted = sorted(words, key=lambda w: w['top'])
    lines = []
    current_line = []
    current_y = None
    
    for word in words_sorted:
        if current_y is None:
            current_y = word['top']
            current_line.append(word)
        else:
            if abs(word['top'] - current_y) <= vertical_threshold:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word['top']
    if current_line:
        lines.append(current_line)
    return lines

def group_line_words_into_cells(line_words, horizontal_threshold=10) -> List[List[dict]]:
    """
    Groups words in a single line into cells based on similar horizontal positions.
    
    Args:
        line_words (list): List of word dictionaries in a single line.
        horizontal_threshold (float): Maximum difference in x0 positions to consider words as part of the same cell.
    
    Returns:
        list: A list of cells; each cell is a list of word dictionaries.
    """
    line_words_sorted = sorted(line_words, key=lambda w: w['x0'])
    cells = []
    current_cell = []
    current_x = None
    
    for word in line_words_sorted:
        if current_x is None:
            current_x = word['x0']
            current_cell.append(word)
        else:
            if abs(word['x0'] - current_x) <= horizontal_threshold:
                current_cell.append(word)
            else:
                cells.append(current_cell)
                current_cell = [word]
                current_x = word['x0']
    if current_cell:
        cells.append(current_cell)
    return cells

def cell_to_tuple(cell_words: List[dict]) -> Tuple[str, int, int, int, int]:
    """
    Combines words within a cell into a tuple containing:
    (text, x0, x1, top, bottom)
    
    The function orders the cell words by their x0, then:
      - Joins the texts with spaces.
      - Computes the minimum x0 and top, and the maximum x1 and bottom.
      - Returns the numbers as integers.
      
    Args:
        cell_words (list): List of word dictionaries that belong to a cell.
        
    Returns:
        tuple: A tuple (text, x0, x1, top, bottom)
    """
    cell_sorted = sorted(cell_words, key=lambda w: w['x0'])
    combined_text = " ".join(word['text'] for word in cell_sorted)
    min_x0 = min(word['x0'] for word in cell_sorted)
    max_x1 = max(word['x1'] for word in cell_sorted)
    min_top = min(word['top'] for word in cell_sorted)
    max_bottom = max(word['bottom'] for word in cell_sorted)
    return (combined_text,
            int(round(min_x0)),
            int(round(max_x1)),
            int(round(min_top)),
            int(round(max_bottom)))

def extract_rows_from_page(
        page, vertical_threshold=5, horizontal_threshold=10
) -> Tuple[List[List[Tuple[str, int, int, int, int]]], List]:
    """
    Extracts a table from a PDF page by grouping words into rows and cells.
    
    Args:
        page (pdfplumber.page.Page): A pdfplumber page object.
        vertical_threshold (float): Vertical proximity threshold for grouping words into the same line.
        horizontal_threshold (float): Horizontal proximity threshold for grouping words into the same cell.
    
    Returns:
        tuple: A tuple with two elements:
            - The table as a list of rows, each row is a list of cell tuples (text, x0, x1, top, bottom).
            - The raw cell groups (for debugging or further processing).
    """
    words = page.extract_words()
    lines = group_words_into_lines(words, vertical_threshold)

    table = []
    raw_cells = []
    for line in lines:
        cells = group_line_words_into_cells(line, horizontal_threshold)
        row = [cell_to_tuple(cell) for cell in cells]
        table.append(row)
        raw_cells.append(cells)
    return table, raw_cells
