"""OCR 테스트용 가상 원룸 임대차 계약서 PDF를 만든다.

내용은 전부 가짜다. 실제 계약서는 레포에 두지 않는다.
사용: python scripts/make_sample_contract.py [출력경로]  (기본: samples/sample_contract.pdf)
"""

import sys
from pathlib import Path

import pymupdf as fitz

PAGES = [
    [
        "부동산(주택) 월세 계약서",
        "",
        "임대인과 임차인 쌍방은 아래 표시 부동산에 관하여 다음 계약 내용과 같이 임대차계약을 체결한다.",
        "",
        "1. 부동산의 표시",
        "소재지: 부산광역시 금정구 가상로 123, 101동 202호",
        "임대할 부분: 원룸 전체  면적: 23.1㎡",
        "",
        "2. 계약내용",
        "제1조 (보증금과 차임) 보증금 금 오백만원정 (₩5,000,000)",
        "차임(월세) 금 사십오만원정 (₩450,000)은 매월 25일에 지불한다.",
        "관리비 금 오만원정 (₩50,000) (정액, 포함 항목: 별도 협의)",
        "제2조 (존속기간) 임대인은 2027년 1월 1일까지 임차 목적물을 인도하며,",
        "임대차 기간은 인도일로부터 2028년 12월 31일까지(24개월)로 한다.",
        "제3조 (용도변경 및 전대 등) 임차인은 임대인의 동의 없이 용도나 구조를 변경하거나",
        "전대·임차권 양도 또는 담보제공을 하지 못한다.",
        "제4조 (계약의 해지) 임차인이 차임을 2기 이상 연체하면 임대인은 계약을 해지할 수 있다.",
    ],
    [
        "제5조 (계약의 종료) 임대차계약이 종료된 경우 임차인은 목적물을 원상으로 회복하여",
        "임대인에게 반환하고, 임대인은 보증금을 임차인에게 반환한다.",
        "",
        "[특약사항]",
        "1. 현 시설 상태에서의 계약이다.",
        "2. 퇴실 시 청소비 15만원은 보증금에서 공제한다.",
        "3. 계약기간 내 중도 퇴실 시 임차인이 새 임차인을 구하고 중개수수료를 부담한다.",
        "4. 벽에 못을 박거나 도배를 훼손한 경우 원상복구 비용은 임차인이 부담한다.",
        "5. 반려동물은 키울 수 없다.",
        "",
        "2026년 12월 1일",
        "임대인  성명: 김가상   (인)",
        "임차인  성명: 이예시   (인)",
    ],
]


# macOS 기본 한글 폰트. 없으면 PyMuPDF 내장 CJK 폰트(숫자가 전각으로 넓게 찍힘)를 쓴다.
SYSTEM_FONT = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")


def main(out: Path) -> None:
    font = {"fontname": "kr", "fontfile": str(SYSTEM_FONT)} if SYSTEM_FONT.exists() else {"fontname": "korea"}
    doc = fitz.open()
    for p, lines in enumerate(PAGES):
        page = doc.new_page(width=595, height=842)  # A4
        y = 60
        for i, line in enumerate(lines):
            size = 18 if (p == 0 and i == 0) else 11
            if line:
                rect = fitz.Rect(60, y, 535, y + 100)
                # 칸을 넘는 긴 문장은 줄바꿈되고, 남은 높이(음수 아님)로 실제 쓴 줄 수를 계산
                left = page.insert_textbox(rect, line, fontsize=size, **font)
                y += rect.height - left
            y += 8 if line else size
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"저장: {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples/sample_contract.pdf"))
