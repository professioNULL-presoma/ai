from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.schemas.ocr import OcrResponse
from app.services import documents
from app.services.ocr import build_page, get_engine
from app.services.storage import StorageError, download_from_s3

router = APIRouter(tags=["ocr"])


@router.post(
    "/ocr",
    response_model=OcrResponse,
    summary="계약서 글자 읽기",
    description=(
        "계약서 PDF·사진에서 페이지별 텍스트와 위치를 뽑는다. "
        "`files`(여러 장 업로드)와 `s3_key` 중 하나만 보낸다. "
        "페이지 번호는 업로드 순서대로 이어진다 (PDF 2쪽 + 사진 1장 → 1~3쪽)."
    ),
)
def run_ocr(
    files: list[UploadFile] | None = File(default=None, description="계약서 PDF 또는 이미지 (여러 개 가능)"),
    s3_key: str | None = Form(default=None, description="S3 객체 키 (backend가 올린 파일)"),
) -> OcrResponse:
    # Swagger에서 파일 칸을 비워 보내면 빈 문자열이 들어오는 경우가 있어 걸러냄
    files = [f for f in (files or []) if getattr(f, "filename", None)]
    if bool(files) == bool(s3_key):
        raise HTTPException(400, "files와 s3_key 중 하나만 보내 주세요")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    sources: list[tuple[bytes, str | None, str | None]] = []  # (데이터, 파일명, content_type)
    if s3_key:
        try:
            data, ctype = download_from_s3(s3_key)
        except StorageError as e:
            raise HTTPException(502, str(e)) from e
        sources.append((data, s3_key, ctype))
    else:
        for f in files:
            sources.append((f.file.read(), f.filename, f.content_type))

    images = []
    for data, name, ctype in sources:
        if len(data) > max_bytes:
            raise HTTPException(413, f"파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB): {name}")
        try:
            ctype = documents.guess_content_type(name, ctype, data)
            remaining = settings.max_pages - len(images)
            images.extend(documents.to_page_images(data, ctype, settings.pdf_dpi, remaining))
        except documents.TooManyPagesError:
            raise HTTPException(400, f"페이지가 너무 많습니다 (최대 {settings.max_pages}쪽)")
        except documents.UnsupportedFileError as e:
            raise HTTPException(415, str(e)) from e
        except Exception as e:  # 깨진 PDF 등
            raise HTTPException(400, f"파일을 열 수 없습니다: {name}") from e

    engine = get_engine()
    pages = [build_page(i, img, engine.recognize(img)) for i, img in enumerate(images, start=1)]
    return OcrResponse(
        page_count=len(pages),
        pages=pages,
        retake_pages=[p.page for p in pages if p.needs_retake],
    )
