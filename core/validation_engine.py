def validate_result(analysis: dict, decision: dict, retrieved: list[dict]) -> list[str]:
    warnings = []
    if analysis.get("possible_agency") == "UNKNOWN":
        warnings.append("소관기관이 확정되지 않았습니다.")
    if decision.get("status") != "OK":
        warnings.append("사건 정보가 부족하거나 국세청 소관이 아닙니다. 국세청 권리구제 수단을 확정하지 마세요.")
    if any("불복" in x or "기한" in x for x in decision.get("primary_routes", [])):
        facts = analysis.get("known_facts") or {}
        if not facts.get("notice_date"):
            warnings.append("통지일이 확인되지 않았습니다. 불복기한을 확정하지 마세요.")
    if not retrieved:
        warnings.append("PDF 검색 근거가 없습니다. 문서 근거가 필요한 안내는 공식 자료로 재확인하세요.")
    return warnings


def validate_evidence_for_route(selected_route: str, retrieved: list[dict]) -> list[str]:
    """선택된 세부 권리보호 유형과 검색 근거가 직접 일치하는지 확인합니다."""
    if not any(term in (selected_route or "") for term in ("권리보호", "납세자보호담당관", "권리침해")):
        return []
    normalized_route = (selected_route or "").replace(" ", "")
    exact_hits = []
    generic_hits = []
    for item in retrieved or []:
        body = str(item.get("text", "")).replace(" ", "")
        filename = str(item.get("filename", "")).replace(" ", "")
        if normalized_route and (normalized_route in body or normalized_route in filename):
            exact_hits.append(item)
        elif "권리보호" in body or "납세자보호" in body or "권리보호" in filename:
            generic_hits.append(item)
    if exact_hits:
        return []
    if generic_hits:
        return ["권리보호 관련 참고자료는 검색됐지만 선택된 세부 유형과 직접 일치하는 근거는 확인되지 않았습니다. 해당 자료의 일반 내용을 세부 유형의 요건으로 단정하지 마세요."]
    return ["선택된 세부 권리보호 유형을 뒷받침하는 참고자료가 검색되지 않았습니다. 대상·요건·서류는 추정하지 말고 담당 기관에서 확인하세요."]
