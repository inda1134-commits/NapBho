def decide(analysis: dict, stage_info: dict) -> dict:
    """보수적인 규칙 엔진. 후보 안내이며 법적 요건을 확정하지 않는다."""
    agency = analysis.get("possible_agency", "UNKNOWN")
    if agency == "OTHER":
        return {"status":"OUT_OF_SCOPE","primary_routes":[],"secondary_routes":[],
                "cautions":["국세청 권리구제 절차를 적용하지 않고 소관기관을 확인합니다."]}
    if agency == "UNKNOWN":
        return {"status":"NEED_INFO","primary_routes":[],"secondary_routes":[],
                "cautions":["소관기관을 확인한 뒤 절차를 판단합니다."]}
    issues = analysis.get("issue_types") or []
    facts = stage_info.get("facts") or {}
    stage = stage_info.get("stage", "")
    primary, secondary, cautions = [], [], []
    inquiry = analysis.get("inquiry_type")
    if inquiry == "SIMPLE_TAX_QUESTION" and not any(x in str(issues) for x in ["과세처분","세무조사","징수"]):
        primary.append("국세상담센터 등 공식 세법 상담")
    if "신고 오류" in issues:
        primary.append("경정청구 등 신고 정정 절차 검토")
        cautions.append("세목·신고 내용·기간 및 요건을 확인해야 합니다.")
    if "미신고" in issues:
        primary.append("기한후신고 등 검토")
    if "신고 후 자료 제출 요구" in issues:
        primary.append("담당자에게 자료 요구의 취지·근거·제출기한 확인")
        secondary.append("신고내용 확인 절차인지 확인")
        cautions.append("고지·처분 전이라는 이유만으로 경정청구나 불복을 확정 추천하지 않습니다.")
    if facts.get("notice_kind") == "과세예고" or stage == "과세예고":
        primary.append("과세전적부심사 등 검토")
        cautions.append("청구 대상·예외·기간을 현행 규정으로 확인합니다.")
    if facts.get("notice_kind") == "고지" or stage == "고지 후":
        primary.append("과세처분 불복절차 검토")
        secondary.append("과세 근거 확인")
        cautions.append("처분 종류와 통지일에 따라 기한을 확인합니다.")
    if any(x in issues for x in ["과세근거 안내 부족", "절차상 권리침해"]):
        primary.append("납세자보호담당관에게 권리보호요청 대상 여부 상담")
        if facts.get("notice_kind") == "고지":
            secondary.append("과세처분 불복 가능성 별도 확인")
        cautions.append("권리보호요청이 불복절차나 불복기한을 자동으로 대체하지 않습니다.")
    if "부당한 세무조사 행위" in issues or stage == "세무조사 진행":
        primary.append("세무조사 관련 권리보호 절차 검토")
        secondary.append("조사 범위·자료 요구의 취지와 근거를 담당자 또는 납세자보호담당관에 확인")
    if stage.startswith("세무조사 종결") or facts.get("tax_audit_status") in ("종결", "종결됨"):
        primary.append("과세예고통지 여부 또는 고지 여부를 먼저 확인")
        cautions.append("조사 종결만으로 과세전적부심사나 조기결정신청을 자동 추천하지 않습니다.")
    if stage == "징수·체납" or "징수·체납" in issues:
        primary.append("징수유예 등 징수 관련 제도 검토")
        cautions.append("체납 단계·압류 상태·신청 요건을 확인합니다.")
    if facts.get("appeal_status") == "기한 경과 주장" or "불복기한 경과 주장" in issues:
        primary.append("처분일·통지일·처분 종류 및 기간 계산 확인")
        secondary.append("요건에 따라 고충민원 등 후속 절차 검토")
        cautions.append("고충민원이 일반 불복절차를 대체하거나 처분 취소를 보장하지 않습니다.")
    if not primary:
        primary.append("사실관계 확인 후 적절한 절차 판단")
        cautions.append("현재 정보만으로 특정 절차를 확정하기 어렵습니다.")
    # deduplicate, preserving order
    primary = list(dict.fromkeys(primary))
    secondary = list(dict.fromkeys(secondary))
    return {"status":"OK","stage":stage,"primary_routes":primary,"secondary_routes":secondary,
            "cautions":list(dict.fromkeys(cautions)),
            "next_steps":["고지서·안내문에서 세목, 문서 종류, 발급일을 확인합니다.",
                          "담당 세무서 또는 납세자보호담당관에 적용 대상과 신청기한을 확인합니다."],
            "rule_note":"본 결과는 초기 규칙에 따른 후보 안내이며 공식 법률 판단이 아닙니다."}
