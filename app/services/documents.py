"""업로드된 PDF·이미지를 OCR에 넣을 페이지 이미지(RGB numpy 배열)로 바꾼다.

파일은 디스크에 저장하지 않고 메모리에서만 다룬다 (원본 계약서를 남기지 않기 위해).
"""

import pymupdf as fitz
import numpy as np

PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
SUPPORTED_TYPES = PDF_TYPES | IMAGE_TYPES


class UnsupportedFileError(ValueError):
    pass


class TooManyPagesError(ValueError):
    pass


def guess_content_type(filename: str | None, content_type: str | None, data: bytes) -> str:
    """브라우저가 content_type을 비워 보내는 경우가 있어 파일 앞부분으로도 판단한다."""
    if content_type in SUPPORTED_TYPES:
        return content_type
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    raise UnsupportedFileError(f"지원하지 않는 형식입니다: {content_type or filename}")


def _pixmap_to_array(pix: fitz.Pixmap) -> np.ndarray:
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        arr = arr[:, :, :3]
    return np.ascontiguousarray(arr)


def to_page_images(data: bytes, content_type: str, dpi: int, max_pages: int) -> list[np.ndarray]:
    if content_type in PDF_TYPES:
        doc = fitz.open(stream=data, filetype="pdf")
    else:
        # PyMuPDF는 이미지 파일도 1페이지 문서로 연다
        doc = fitz.open(stream=data, filetype=content_type.split("/")[1])

    with doc:
        if doc.page_count > max_pages:
            raise TooManyPagesError(f"페이지가 너무 많습니다 ({doc.page_count}쪽, 최대 {max_pages}쪽)")
        images = []
        for page in doc:
            if content_type in PDF_TYPES:
                pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            else:
                pix = page.get_pixmap(colorspace=fitz.csRGB, alpha=False)
            images.append(_pixmap_to_array(pix))
        return images
