from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    # OCR
    # 모델 이름을 직접 지정할 때 PaddleOCR의 lang 옵션은 무시되므로 인식 모델도 꼭 한국어로 지정
    ocr_det_model: str = "PP-OCRv5_mobile_det"
    ocr_rec_model: str = "korean_PP-OCRv5_mobile_rec"
    ocr_det_max_side: int = 1280  # 검출 입력 긴 변 상한. 너무 크면 macOS arm64에서 Paddle이 멈춤
    ocr_preload: bool = False  # true면 서버 시작 때 모델을 미리 올림
    pdf_dpi: int = 200
    ocr_min_confidence: float = 0.6  # 페이지 평균 신뢰도가 이보다 낮으면 다시 찍기 요청
    ocr_min_lines: int = 3  # 읽은 줄이 이보다 적으면 다시 찍기 요청
    max_upload_mb: int = 20
    max_pages: int = 20

    # S3
    aws_region: str = "ap-northeast-2"
    s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
