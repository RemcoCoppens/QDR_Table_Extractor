from pdf_parser import PdfParser, TableExtractor

pdf = PdfParser(file_path="test_docs/pdf_staffel_test.pdf")

raw_page_texts = pdf.raw_text.split("\n------------\n")

table_extractor = TableExtractor()
tables = table_extractor.extract_from_pages(pages_text=raw_page_texts)