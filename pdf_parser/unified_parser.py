import os
import re
import io

from utils import get_logger, count_tokens_in_pdf
from .textual_parser import TextualParser
from .visual_parser import VisualParser


class PdfParser:
    """
    Parses PDF files using either a structured text parser (TextualParser) or
    OCR-based parser (VisualParser), depending on content.

    Compatible with both S3 and local paths.
    """

    def __init__(self, file_path: str):
        """
        Args:
            file_path (str): Path to the file (S3 key or local path).
            source (str): "s3" or "local".
        """
        self.logger = get_logger(__name__)
        self.file_path = file_path

        self._validate_file_type()
        self.file = self._load_file()

        self.n_tokens = count_tokens_in_pdf(file=self.file)
        self.token_threshold = 10
        self.parser = self._select_parser()
        self.parse_method = self.parser.__method__

        self.pages_text = self.parser.pages_text
        cleaned = self.parser.raw_text.replace('\xa0', ' ')
        self.raw_text = f"*File name*: {self.file_path}\n{cleaned}"
        self.preview = getattr(self.parser, "preview", cleaned[:1500])

    def __str__(self) -> str:
        return (
            f"FILE_NAME: '{self.file_path}'\n"
            f"\t- N_TOKENS: {self.n_tokens}\n"
            f"\t- PARSE_METHOD: {self.parse_method}\n\n"
            f"{'=' * 70}\n\n"
            f"{self.raw_text}"
        )

    def _validate_file_type(self):
        _, ext = os.path.splitext(self.file_path)
        if ext.lower() != ".pdf":
            self.logger.error("Invalid file type: '%s'", ext)
            raise ValueError(f"Invalid file type '{ext}'. Only PDFs are supported.")

    def _load_file(self) -> io.BytesIO:
        with open(self.file_path, "rb") as f:
            return io.BytesIO(f.read())

    def _has_binary_encoding(self, text: str) -> bool:
        """Detects binary/control characters."""
        hex_pattern = re.compile(r"\\x[0-9A-Fa-f]{2}")
        ctrl_pattern = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
        allowed = {"\n", "\t", "\r"}
        cleaned = "".join(c for c in text if c not in allowed)

        if hex_pattern.search(text):
            self.logger.warning(r"Detected \xNN hex escape.")
            return True
        if ctrl_pattern.search(cleaned):
            self.logger.warning("Detected control characters.")
            return True

        return False

    def _select_parser(self):
        """Chooses between TextualParser and VisualParser."""
        if self.n_tokens > self.token_threshold:
            try:
                text_parser = TextualParser(file=self.file)
                if not self._has_binary_encoding(text_parser.raw_text):
                    return text_parser

            except Exception as e:
                self.logger.warning("TextualParser failed: %s", str(e), exc_info=True)

        return VisualParser(file=self.file)
