import pymupdf as fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ocr import OcrLine
from app.services import ocr as ocr_service


class FakeEngine:
    """PaddleOCR 없이 라우터 동작을 확인하기 위한 가짜 엔진."""

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        return [
            OcrLine(text="둘째 줄", confidence=0.95, bbox=[10, 60, 100, 80]),
            OcrLine(text="첫째 줄", confidence=0.99, bbox=[10, 10, 100, 30]),
            OcrLine(text="셋째 줄", confidence=0.90, bbox=[10, 110, 100, 130]),
        ]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ocr_service, "_engine", FakeEngine())
    return TestClient(app)


@pytest.fixture
def pdf_bytes() -> bytes:
    doc = fitz.open()
    for _ in range(2):
        doc.new_page(width=200, height=300).insert_text((20, 40), "test")
    return doc.tobytes()


@pytest.fixture
def png_bytes() -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 40), False)
    pix.clear_with(255)
    return pix.tobytes("png")
