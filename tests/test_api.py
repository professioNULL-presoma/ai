from app.schemas.ocr import OcrLine
from app.services.ocr import sort_reading_order


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ocr_pdf_and_image_pages_are_numbered_in_order(client, pdf_bytes, png_bytes):
    res = client.post(
        "/ocr",
        files=[
            ("files", ("contract.pdf", pdf_bytes, "application/pdf")),
            ("files", ("page3.png", png_bytes, "image/png")),
        ],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["page_count"] == 3
    assert [p["page"] for p in body["pages"]] == [1, 2, 3]
    assert body["pages"][0]["text"] == "첫째 줄\n둘째 줄\n셋째 줄"
    assert body["pages"][0]["lines"][0]["bbox"] == [10, 10, 100, 30]
    assert body["retake_pages"] == []


def test_ocr_requires_exactly_one_input(client, pdf_bytes):
    assert client.post("/ocr").status_code == 400
    res = client.post(
        "/ocr",
        files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))],
        data={"s3_key": "contracts/1.pdf"},
    )
    assert res.status_code == 400


def test_ocr_rejects_unsupported_type(client):
    res = client.post("/ocr", files=[("files", ("a.txt", b"hello", "text/plain"))])
    assert res.status_code == 415


def test_ocr_flags_low_confidence_page(client, monkeypatch, pdf_bytes):
    from app.services import ocr as ocr_service

    class BlurryEngine:
        def recognize(self, image):
            return [OcrLine(text="??", confidence=0.2, bbox=[0, 0, 10, 10])]

    monkeypatch.setattr(ocr_service, "_engine", BlurryEngine())
    res = client.post("/ocr", files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))])
    assert res.json()["retake_pages"] == [1, 2]


def test_sort_reading_order_same_row_left_to_right():
    lines = [
        OcrLine(text="오른쪽", confidence=1, bbox=[200, 12, 300, 32]),
        OcrLine(text="아래", confidence=1, bbox=[10, 60, 100, 80]),
        OcrLine(text="왼쪽", confidence=1, bbox=[10, 10, 100, 30]),
    ]
    assert [l.text for l in sort_reading_order(lines)] == ["왼쪽", "오른쪽", "아래"]


def test_ocr_swagger_shows_file_picker():
    """Swagger UI는 format: binary이고 null이 섞이지 않아야 파일 선택 버튼을 그린다."""
    from app.main import app

    props = app.openapi()["components"]["schemas"]["Body_run_ocr_ocr_post"]["properties"]
    assert props["files"]["type"] == "array"
    assert props["files"]["items"] == {"type": "string", "format": "binary"}
    assert "anyOf" not in props["files"] and "anyOf" not in props["s3_key"]
