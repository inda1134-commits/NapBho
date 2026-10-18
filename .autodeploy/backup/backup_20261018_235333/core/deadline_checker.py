"""기한 판단을 위해 사용자가 선택한 기간 범주를 기록합니다. 날짜로 법정기한을 계산하지 않습니다."""

VALID_WINDOWS = {"30일 내", "60일 내", "90일 내", "잘 모르겠음"}

def check_deadline(window: str | None, notice_kind: str | None, stage: str | None = None) -> dict:
    """30/60/90일 범주를 바탕으로 확인 우선순위와 해결 경로를 보조합니다.

    이 함수는 법정기한을 확정하지 않으며, 입력된 범주를 실제 경과일수로 간주하지 않습니다.
    """
    if not window or window not in VALID_WINDOWS:
        return {"status": "UNKNOWN", "window": None, "message": "기한 관련 기간 범주가 확인되지 않았습니다. 30일 내·60일 내·90일 내 중 하나를 확인해 주세요.", "priority": "확인 필요"}
    kind = (notice_kind or "").strip()
    stage = (stage or "").strip()
    if window == "잘 모르겠음":
        return {"status": "CHECK_REQUIRED", "window": window, "message": "기간을 확실히 모르는 경우에는 기한이 임박했을 가능성을 고려해 처분 문서와 적용 절차를 담당 기관에 즉시 확인하세요.", "priority": "즉시 확인"}
    route = "일반적인 기한 관련 절차를 신속히 확인"
    if "세무조사" in stage or "조사" in kind:
        route = "세무조사 진행 상태와 권리보호 요청 등 조사 관련 절차 확인"
    elif "과세예고" in kind or "과세전적부" in stage:
        route = "과세전적부심사 대상 여부와 신청기한 확인"
    elif "고지" in kind or "불복" in stage:
        route = "불복 절차의 대상·기산점·신청기한 확인"
    elif "권리보호" in stage or "권리침해" in kind:
        route = "권리보호 요청 대상 및 접수 절차 확인"
    return {"status": "CHECK_REQUIRED", "window": window, "message": f"사용자가 선택한 기간 범주: {window}. {route}가 우선 검토 대상입니다. 이 선택만으로 법정기한 내·외를 확정하지 말고, 문서 종류와 공식 규정은 담당 기관에서 확인하세요.", "priority": "신속 확인", "suggested_focus": route}
