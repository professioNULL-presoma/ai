"""PaddleOCR 래퍼.

모델 로딩이 무거워서(수 초) 프로세스당 한 번만 만들고 재사용한다.
OCR 엔진은 스레드 안전하지 않아 락으로 한 번에 한 페이지씩 돌린다.
"""

import logging
import threading
from typing import Protocol

import numpy as np

from app.config import get_settings
from app.schemas.ocr import OcrLine, OcrPage

logger = logging.getLogger(__name__)


class OcrEngine(Protocol):
    def recognize(self, image: np.ndarray) -> list[OcrLine]: ...


class PaddleOcrEngine:
    def __init__(self, lang: str):
        from paddleocr import PaddleOCR  # 임포트만으로도 느려서 여기서 불러옴

        self._ocr = PaddleOCR(
            lang=lang,
            # 계약서는 정면 촬영·스캔이 대부분이라 문서 보정 모델은 끔 (속도 우선)
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        self._lock = threading.Lock()

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        # PaddleOCR은 BGR 입력을 기대함
        bgr = np.ascontiguousarray(image[:, :, ::-1])
        with self._lock:
            results = self._ocr.predict(bgr)

        lines: list[OcrLine] = []
        for res in results:
            texts = res["rec_texts"]
            scores = res["rec_scores"]
            boxes = res["rec_boxes"]  # (N, 4) [x1, y1, x2, y2]
            for text, score, box in zip(texts, scores, boxes):
                if not text.strip():
                    continue
                lines.append(
                    OcrLine(
                        text=text,
                        confidence=round(float(score), 4),
                        bbox=[float(v) for v in box],
                    )
                )
        return lines


_engine: OcrEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> OcrEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                logger.info("PaddleOCR 모델 로딩 중...")
                _engine = PaddleOcrEngine(lang=get_settings().ocr_lang)
                logger.info("PaddleOCR 모델 로딩 완료")
    return _engine


def sort_reading_order(lines: list[OcrLine]) -> list[OcrLine]:
    """위→아래, 같은 줄이면 왼→오른쪽 순서로 정렬한다.

    y 중심이 줄 높이 절반 이내로 가까우면 같은 줄로 본다.
    """
    if not lines:
        return []
    by_y = sorted(lines, key=lambda l: (l.bbox[1] + l.bbox[3]) / 2)
    rows: list[list[OcrLine]] = []
    for line in by_y:
        cy = (line.bbox[1] + line.bbox[3]) / 2
        h = line.bbox[3] - line.bbox[1]
        if rows:
            last = rows[-1][-1]
            last_cy = (last.bbox[1] + last.bbox[3]) / 2
            if abs(cy - last_cy) <= max(h, last.bbox[3] - last.bbox[1]) / 2:
                rows[-1].append(line)
                continue
        rows.append([line])
    return [l for row in rows for l in sorted(row, key=lambda l: l.bbox[0])]


def build_page(page_no: int, image: np.ndarray, lines: list[OcrLine]) -> OcrPage:
    settings = get_settings()
    lines = sort_reading_order(lines)
    avg = round(sum(l.confidence for l in lines) / len(lines), 4) if lines else 0.0
    needs_retake = len(lines) < settings.ocr_min_lines or avg < settings.ocr_min_confidence
    return OcrPage(
        page=page_no,
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        text="\n".join(l.text for l in lines),
        lines=lines,
        avg_confidence=avg,
        needs_retake=needs_retake,
    )
