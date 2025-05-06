import os
from typing import Tuple, List, Union, IO
from collections import defaultdict

import pandas as pd
from pdf2image import convert_from_path, convert_from_bytes
import pytesseract
from PIL import Image, ImageOps

from utils import get_logger

class VisualParser:
    """
    A class to parse text from image-based PDF files using OCR.

    Attributes:
        file_name (str): The name of the file being processed.
        ext (str): The extension of the file being processed.
        page_delimiter (str): The delimiter used to separate pages in the raw text.
        page_removal_patterns (list): List of patterns used to identify pages to be removed.
        max_pages_ingestion (int): Maximum number of pages to process.
        preview_pages (int): Number of pages to include in the preview text.
        images (list): List of images converted from the PDF.
        raw_text (str): Extracted raw text from the PDF.
        preview (str): Preview text from the first few pages of the PDF.
        line_tol (int): Y-coordinate tolerance to group words into the same line.
    """
    def __init__(self, file:Union[str, IO[bytes]]):
        """
        Initialize the PdfImageParser with the file path and maximum number of pages to ingest.

        Args:
            file_path (str): The path to the PDF file.
            temp_file_path (str): When working with temporary files, use this file path.
        """
        self.logger = get_logger(__name__)
        self.__method__ = "IMAGE-PDF"
        self.file = file

        self.raw_text = ""
        self.pages_text = []

        self.page_delimiter = '\n------------\n'
        self.max_pages_ingestion = 10
        self.format__line_tol = 10

        try:
            self.images = self.read_images_from_file()
            self.raw_text = self.read_text_from_images()
            self.logger.info(
                "SCRAPER - Successfully completed Image-PDF parsing"
            )

        except Exception as e:
            self.logger.error(
                "SCRAPER - Error during Image-PDF parsing: %s", str(e), exc_info=True
            )

    def __str__(self) -> str:
        """
        Return the length of the raw text.

        Returns:
            int: Number of characters in the raw text.
        """
        return self.raw_text

    def __len__(self) -> int:
        """
        Return the length of the raw text found in the PDF.

        Returns:
            int: Integer amount of words.
        """
        return len(self.raw_text)

    def read_images_from_file(self) -> List[object]:
        """
        Convert PDF to images either from file path or in-memory BytesIO.
        Returns:
            List[object]: Collection of images for each page.
        """
        try:
            if isinstance(self.file, str) and os.path.isfile(self.file):
                # Load from file path
                images = convert_from_path(
                    self.file,
                    last_page=self.max_pages_ingestion + 5
                )
            else:
                # Load from file-like object (BytesIO)
                self.file.seek(0)
                images = convert_from_bytes(
                    self.file.read(),
                    last_page=self.max_pages_ingestion + 5
                )

            self.logger.info(
                "SCRAPER - Successfully scraped %s page image(s) from file",
                len(images)
            )
            return images

        except Exception as e:
            self.logger.error(
                "SCRAPER - Unable to convert PDF to images: %s",
                str(e), exc_info=True
            )
            return []

    def preprocess(self, image: Image.Image) -> Image.Image:
        """
        Apply grayscaling and binarization for better OCR performance.

        Args:
            image (Image.Image): Original PDF image.

        Returns:
            Image.Image: Preprocessed PDF image.
        """
        gray = image.convert('L')  # Grayscale
        return ImageOps.invert(gray.point(lambda x: 0 if x < 140 else 255, '1'))

    def read_images_from_file(self) -> List[object]:
        """
        Convert PDF to images either from a file path or in-memory BytesIO.

        Returns:
            List[object]: Collection of images for every page in the PDF.
        """
        try:
            if isinstance(self.file, str):
                images = convert_from_path(
                    self.file,
                    last_page=self.max_pages_ingestion + 5
                )
            else:
                self.file.seek(0)
                images = convert_from_bytes(
                    self.file.read(),
                    last_page=self.max_pages_ingestion + 5
                )

            self.logger.info(
                "SCRAPER - Successfully scraped %s page image(s) from file",
                len(images)
            )
            return images

        except Exception as e:
            self.logger.error(
                "SCRAPER - Unable to convert PDF to images: %s",
                str(e), exc_info=True
            )
            return []

    def reconstruct_text_from_df(self, data: pd.DataFrame) -> str:
        """
        Reconstruct readable text layout from pytesseract.image_to_data output.

        Args:
            data (pd.DataFrame): Cleaned OCR data (with conf != -1 and non-null text).

        Returns:
            str: Reconstructed human-readable text.
        """
        data["text"] = data["text"].str.strip()
        data = data[data["text"] != ""]

        lines = defaultdict(list)
        for _, row in data.iterrows():
            y = int(row["top"])
            matched_line = None
            for line_y in lines:
                if abs(line_y - y) <= self.format__line_tol:
                    matched_line = line_y
                    break
            line_key = matched_line if matched_line is not None else y
            lines[line_key].append((row["left"], row["text"]))

        reconstructed = []
        for line_y in sorted(lines.keys()):
            words = sorted(lines[line_y], key=lambda x: x[0])
            reconstructed.append(" ".join(word for _, word in words))

        return "\n".join(reconstructed)

    def read_text_from_images(self) -> Tuple[str, str]:
        text = ""
        pages_added = 0
        page_texts = []

        for image in self.images:
            try:
                preprocessed = self.preprocess(image)
                data = pytesseract.image_to_data(
                    preprocessed,
                    lang='nld',
                    output_type=pytesseract.Output.DATAFRAME
                )
                data = data[data.conf != -1].dropna(subset=["text"])
                
                if len(data) < 10:
                    img_text = pytesseract.image_to_string(
                        preprocessed,
                        lang='nld'
                    ).strip().lower()
                else:
                    img_text = self.reconstruct_text_from_df(data)

                page_texts.append(img_text)
                text += img_text + self.page_delimiter
                pages_added += 1

                if pages_added == self.max_pages_ingestion:
                    break

            except Exception as e:
                self.logger.error("SCRAPER - OCR failed: %s", str(e), exc_info=True)
                continue

        self.pages_text = page_texts
        return text

if __name__ == "__main__":
    parser = VisualParser(file="ZZ_test_files/staffel januari 2025 in concept.pdf")