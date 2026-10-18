from core.deadline_checker import check_deadline

def test_deadline_uses_window_category_without_exact_dates():
    result = check_deadline("30일 내", "고지", "불복")
    assert result["window"] == "30일 내"
    assert "법정기한 내·외를 확정하지 말고" in result["message"]
    assert "불복 절차" in result["suggested_focus"]

def test_unknown_window_requests_immediate_official_check():
    result = check_deadline("잘 모르겠음", "과세예고", "과세")
    assert result["priority"] == "즉시 확인"

