from app.evaluation.ocr_metrics import extract_numbers, parse_ground_truth, score_pages, score_text


def test_parse_ground_truth_splits_pages_and_drops_blank_lines():
    raw = "제목\n\n  본문  \n=====\n둘째 쪽\n"
    assert parse_ground_truth(raw) == ["제목\n본문", "둘째 쪽"]


def test_perfect_match():
    s = score_text("보증금 5,000,000원", "보증금 5,000,000원")
    assert s.cer == 0 and s.cer_no_space == 0 and s.number_recall == 1 and s.diffs == []


def test_space_only_difference_counts_only_with_spaces():
    s = score_text("1. 부동산의 표시", "1.부동산의 표시")
    assert s.errors == 1 and s.errors_no_space == 0


def test_substitution_and_missing_number():
    s = score_text("월세 450,000원 매월 25일", "윌세 45O,000원 매월 25일")
    assert s.errors_no_space == 2
    assert s.number_recall == 2 / 3 and s.missing_numbers == ["450"]
    assert len(s.diffs) == 2


def test_extract_numbers_splits_on_separators():
    assert extract_numbers("₩5,000,000 / 23.1㎡ / 2028년 12월") == ["5", "000", "000", "23", "1", "2028", "12"]


def test_dropped_space_between_numbers_is_not_a_number_error():
    s = score_text("가상로 123, 101동", "가상로 123,101동")
    assert s.number_recall == 1


def test_missing_page_counts_as_all_errors():
    scores = score_pages(["가나다", "라마"], ["가나다"])
    assert scores[1].errors == 2 and scores[1].cer == 1
