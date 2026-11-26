from pydantic import BaseModel, Field


class OcrLine(BaseModel):
    text: str
    confidence: float = Field(description="0~1 인식 신뢰도")
    bbox: list[float] = Field(description="[x1, y1, x2, y2] 페이지 이미지 픽셀 좌표 (좌상단 기준)")


class OcrPage(BaseModel):
    page: int = Field(description="1부터 시작하는 페이지 번호 (업로드 순서 기준)")
    width: int
    height: int
    text: str = Field(description="줄을 위→아래 순서로 이어 붙인 전체 텍스트")
    lines: list[OcrLine]
    avg_confidence: float
    needs_retake: bool = Field(description="글자를 제대로 못 읽어 다시 찍어야 하는 페이지")


class OcrResponse(BaseModel):
    page_count: int
    pages: list[OcrPage]
    retake_pages: list[int] = Field(description="다시 찍어야 하는 페이지 번호 목록")
