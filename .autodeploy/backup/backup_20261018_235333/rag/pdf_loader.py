from io import BytesIO
from pypdf import PdfReader

def extract_pdf_pages(file_bytes: bytes, filename: str) -> list[dict]:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append({"text":text, "filename":filename, "page":i})
    return pages
