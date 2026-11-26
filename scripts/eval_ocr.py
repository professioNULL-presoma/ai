"""OCR 정확도를 정답 텍스트와 비교해 평가하고, 결과를 eval/ocr_history.csv에 기록한다.

정답 파일: 문서와 같은 이름에 `.gt.txt`를 붙인 텍스트 파일
    samples/sample_contract.pdf  ->  samples/sample_contract.gt.txt
    페이지는 `=====`만 있는 줄로 구분. 빈 줄과 줄 앞뒤 공백은 비교에서 무시한다.

사용:
    python scripts/eval_ocr.py                       # samples/ 안의 정답 있는 문서 전부
    python scripts/eval_ocr.py samples/a.jpg samples/b.pdf --note "det 1600으로 변경"
    python scripts/eval_ocr.py --json result.json --gt samples/a.gt.txt   # Swagger 응답 JSON 평가
    python scripts/eval_ocr.py --no-record           # 기록 안 남기고 보기만
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.evaluation.ocr_metrics import EMPTY_SCORE, TextScore, parse_ground_truth, score_pages  # noqa: E402

DOC_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
HISTORY = ROOT / "eval" / "ocr_history.csv"
HISTORY_FIELDS = [
    "timestamp", "commit", "file", "pages", "ref_chars", "cer", "cer_no_space",
    "number_recall", "seconds", "det_model", "rec_model", "det_max_side", "pdf_dpi", "note",
]


def gt_path(doc: Path) -> Path:
    return doc.with_name(doc.stem + ".gt.txt")


def find_docs(args_docs: list[str]) -> list[Path]:
    if args_docs:
        return [Path(d) for d in args_docs]
    return sorted(p for p in (ROOT / "samples").iterdir() if p.suffix.lower() in DOC_SUFFIXES and gt_path(p).exists())


def run_ocr(doc: Path) -> tuple[list[str], float]:
    """API와 같은 경로(documents → engine → build_page)로 OCR을 돌린다."""
    from app.services import documents
    from app.services.ocr import build_page, get_engine

    s = get_settings()
    data = doc.read_bytes()
    ctype = documents.guess_content_type(doc.name, None, data)
    images = documents.to_page_images(data, ctype, s.pdf_dpi, s.max_pages)
    engine = get_engine()  # 모델 로딩 시간은 측정에서 뺀다
    t = time.perf_counter()
    pages = [build_page(i, img, engine.recognize(img)).text for i, img in enumerate(images, 1)]
    return pages, time.perf_counter() - t


def git_commit() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "app"], cwd=ROOT, text=True).strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def report(name: str, scores: list[TextScore], seconds: float | None) -> TextScore:
    total = sum(scores, EMPTY_SCORE)
    t = f"  {seconds:.1f}s" if seconds is not None else ""
    print(f"\n■ {name}  ({len(scores)}쪽, {total.ref_chars_no_space}자){t}")
    print(f"  CER {total.cer:.2%}  공백 제외 CER {total.cer_no_space:.2%}  "
          f"숫자 재현율 {total.number_recall:.1%} ({total.matched_numbers}/{total.ref_numbers})")
    for i, s in enumerate(scores, 1):
        for d in s.diffs:
            print(f"    p{i}  {d}")
    if total.missing_numbers:
        print(f"  ⚠ 놓친 숫자: {', '.join(total.missing_numbers)}")
    return total


def record(rows: list[dict]) -> None:
    HISTORY.parent.mkdir(exist_ok=True)
    new = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    print(f"\n기록: {HISTORY.relative_to(ROOT)} (+{len(rows)}줄)")


def main() -> None:
    ap = argparse.ArgumentParser(description="OCR 정확도 평가")
    ap.add_argument("docs", nargs="*", help="평가할 문서 (생략하면 samples/ 안의 정답 있는 문서 전부)")
    ap.add_argument("--json", help="OCR을 다시 돌리지 않고 /ocr 응답 JSON을 평가")
    ap.add_argument("--gt", help="--json과 함께 쓸 정답 파일")
    ap.add_argument("--note", default="", help="이번 실행 메모 (무엇을 바꿨는지)")
    ap.add_argument("--no-record", action="store_true", help="기록 파일에 남기지 않음")
    args = ap.parse_args()

    s = get_settings()
    base = {
        "timestamp": datetime.now().isoformat(timespec="seconds"), "commit": git_commit(),
        "det_model": s.ocr_det_model, "rec_model": s.ocr_rec_model,
        "det_max_side": s.ocr_det_max_side, "pdf_dpi": s.pdf_dpi, "note": args.note,
    }

    jobs = []  # (이름, 정답 페이지, OCR 페이지, 초)
    if args.json:
        if not args.gt:
            ap.error("--json에는 --gt가 필요합니다")
        hyp = [p["text"] for p in json.loads(Path(args.json).read_text(encoding="utf-8"))["pages"]]
        jobs.append((Path(args.gt).name, parse_ground_truth(Path(args.gt).read_text(encoding="utf-8")), hyp, None))
        base["commit"] = "json"  # 어떤 코드로 만든 결과인지 알 수 없음
    else:
        docs = find_docs(args.docs)
        if not docs:
            sys.exit("평가할 문서가 없습니다. 먼저 python scripts/make_sample_contract.py 를 실행하세요.")
        for doc in docs:
            if not gt_path(doc).exists():
                print(f"건너뜀 (정답 파일 없음): {gt_path(doc)}")
                continue
            hyp, sec = run_ocr(doc)
            jobs.append((doc.name, parse_ground_truth(gt_path(doc).read_text(encoding="utf-8")), hyp, sec))

    rows, overall = [], EMPTY_SCORE
    for name, ref, hyp, sec in jobs:
        if len(ref) != len(hyp):
            print(f"\n⚠ {name}: 페이지 수가 다릅니다 (정답 {len(ref)}쪽, OCR {len(hyp)}쪽)")
        total = report(name, score_pages(ref, hyp), sec)
        overall = overall + total
        rows.append({**base, "file": name, "pages": len(hyp), "ref_chars": total.ref_chars,
                     "cer": f"{total.cer:.4f}", "cer_no_space": f"{total.cer_no_space:.4f}",
                     "number_recall": f"{total.number_recall:.4f}",
                     "seconds": f"{sec:.1f}" if sec is not None else ""})

    if len(jobs) > 1:
        print(f"\n■ 전체 {len(jobs)}개: CER {overall.cer:.2%}  공백 제외 CER {overall.cer_no_space:.2%}  "
              f"숫자 재현율 {overall.number_recall:.1%}")
    if rows and not args.no_record:
        record(rows)


if __name__ == "__main__":
    main()
