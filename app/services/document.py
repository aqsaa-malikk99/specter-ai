"""Extracts contract text from an uploaded file.

Contracts arrive as PDFs in practice, so that's the primary path (embedded
text extraction via pypdf - no OCR yet, so a scanned image with no text
layer will come back empty and gets rejected with a clear error rather than
silently producing garbage). Plain .txt is still accepted since it's useful
for fixtures/testing, but the UI only offers PDF.
"""
import io
from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader


def extract_contract_text(filename: str | None, raw_bytes: bytes) -> str:
    ext = Path(filename or "").suffix.lower()

    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse PDF: {exc}") from exc
        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in this PDF. It may be a scanned image "
                "with no text layer - OCR isn't supported yet.",
            )
        return text

    if ext == ".txt":
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode file as UTF-8 text.")

    raise HTTPException(status_code=400, detail="Only .pdf files are supported.")
