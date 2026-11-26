"""OCR 결과를 정답 텍스트와 비교하는 지표.

- CER (Character Error Rate): 편집 거리 / 정답 글자 수. 낮을수록 좋음
  - 공백 제외 CER: 띄어쓰기 차이를 빼고 글자 자체를 얼마나 틀렸는지
- 숫자 재현율: 정답에 있는 숫자 덩어리(금액·날짜·면적 등)를 OCR이 그대로 찾은 비율.
  계약 요약(보증금·월세·관리비·기간)이 숫자에 달려 있어서 따로 본다.
  쉼표·점에서 끊어 연속된 숫자만 비교한다. `123, 101동`이 `123,101동`으로 읽히면
  천 단위 쉼표와 구분할 수 없어서, 금액 단위로 묶으면 띄어쓰기 차이가 숫자 오류로 잡힌다.
"""

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

PAGE_SEPARATOR = "====="
_NUMBER = re.compile(r"\d+")


def parse_ground_truth(raw: str) -> list[str]:
    """정답 파일을 페이지별 텍스트로 나눈다. 페이지 구분은 `=====`만 있는 줄."""
    pages, cur = [], []
    for line in raw.splitlines():
        if line.strip() == PAGE_SEPARATOR:
            pages.append(cur)
            cur = []
        else:
            cur.append(line)
    pages.append(cur)
    return [normalize(p) for p in pages]


def normalize(lines: list[str] | str) -> str:
    """빈 줄을 빼고 줄 끝 공백을 정리한다. 비교 전에 정답·OCR 양쪽에 똑같이 적용."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    return "\n".join(l.strip() for l in lines if l.strip())


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _strip_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def extract_numbers(s: str) -> list[str]:
    """연속된 숫자 덩어리를 뽑는다. `5,000,000` → 5, 000, 000"""
    return _NUMBER.findall(s)


@dataclass
class TextScore:
    ref_chars: int
    errors: int
    ref_chars_no_space: int
    errors_no_space: int
    ref_numbers: int
    matched_numbers: int
    missing_numbers: list[str] = field(default_factory=list)
    diffs: list[str] = field(default_factory=list)

    @property
    def cer(self) -> float:
        return self.errors / self.ref_chars if self.ref_chars else 0.0

    @property
    def cer_no_space(self) -> float:
        return self.errors_no_space / self.ref_chars_no_space if self.ref_chars_no_space else 0.0

    @property
    def number_recall(self) -> float:
        return self.matched_numbers / self.ref_numbers if self.ref_numbers else 1.0

    def __add__(self, other: "TextScore") -> "TextScore":
        return TextScore(
            self.ref_chars + other.ref_chars,
            self.errors + other.errors,
            self.ref_chars_no_space + other.ref_chars_no_space,
            self.errors_no_space + other.errors_no_space,
            self.ref_numbers + other.ref_numbers,
            self.matched_numbers + other.matched_numbers,
            self.missing_numbers + other.missing_numbers,
            self.diffs + other.diffs,
        )


EMPTY_SCORE = TextScore(0, 0, 0, 0, 0, 0)


def diff_snippets(ref: str, hyp: str, context: int = 4) -> list[str]:
    """공백을 뺀 텍스트에서 틀린 부분을 앞뒤 몇 글자와 함께 보여 준다."""
    r, h = _strip_ws(ref), _strip_ws(hyp)
    out = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, r, h, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        out.append(f"{r[max(0, a1 - context):a2 + context]!r} -> {h[max(0, b1 - context):b2 + context]!r}")
    return out


def score_text(ref: str, hyp: str) -> TextScore:
    ref, hyp = normalize(ref), normalize(hyp)
    r_ns, h_ns = _strip_ws(ref), _strip_ws(hyp)
    ref_nums, hyp_nums = Counter(extract_numbers(ref)), Counter(extract_numbers(hyp))
    missing = ref_nums - hyp_nums
    return TextScore(
        ref_chars=len(ref),
        errors=edit_distance(ref, hyp),
        ref_chars_no_space=len(r_ns),
        errors_no_space=edit_distance(r_ns, h_ns),
        ref_numbers=sum(ref_nums.values()),
        matched_numbers=sum((ref_nums & hyp_nums).values()),
        missing_numbers=sorted(missing.elements()),
        diffs=diff_snippets(ref, hyp),
    )


def score_pages(ref_pages: list[str], hyp_pages: list[str]) -> list[TextScore]:
    """페이지별로 비교한다. 페이지 수가 다르면 없는 쪽을 빈 텍스트로 본다."""
    n = max(len(ref_pages), len(hyp_pages))
    ref_pages = ref_pages + [""] * (n - len(ref_pages))
    hyp_pages = hyp_pages + [""] * (n - len(hyp_pages))
    return [score_text(r, h) for r, h in zip(ref_pages, hyp_pages)]
