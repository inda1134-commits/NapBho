from core.complaint_analyzer import analyze_fallback, normalize_analysis
from core.intake_classifier import classify_intake

SYSTEM = """당신은 한국 납세자 불만사항의 초기 분류 보조자입니다. 최종 법률 판단이 아니라 사용자가 검토·수정할 분류 초안을 작성하세요. JSON만 반환하세요.
반드시 다음 핵심 필드를 분류하세요.
1) responsible_agency: 불만을 유발한 행정기관의 명칭. 문서 발신기관/행위를 한 기관 기준이며, 불명확하면 '확인 필요'.
2) possible_agency: NTS(국세청), OTHER(다른 기관이 명확), UNKNOWN(불명확).
3) tax_type: 국세청 소관 세목. 사용자가 오타·약칭을 쓰더라도 문맥상 유사한 세목 후보를 찾되, 확실하지 않으면 null.
4) tax_stage: 사업자등록, 신고, 세무조사, 과세, 불복, 체납, 민원, 세법상담, 기타, 미확인 중 하나. 과세예고와 고지는 모두 과세 단계로 분류한다.
5) administrative_action: 안내, 자료제출 요구, 소명 요구, 통지, 과세예고통지, 고지, 독촉, 압류·추심, 신고 처리·환급 지연, 세무조사 착수·진행, 불복 결정, 민원 회신, 기타, 미확인 중 하나.
6) desired_outcome: 사용자가 궁극적으로 원하는 결과를 추론하되 단정하지 말 것. 과세 근거·자료 확인, 처분 취소·변경, 세액 감액·환급, 신고·등록 처리, 납부기한 연장·징수 유예, 압류 해제, 조사 절차 개선·중단, 불복·권리구제 방법 확인, 담당기관 확인·이관, 설명·사과·답변 요구, 단순 세법 문의, 기타, 미확인 중 하나.
요구목적은 사용자의 불만 자체가 아니라 원하는 최종 결과입니다. 확신이 낮은 값은 미확인으로 두세요.
국세청 소관으로 판단된 경우 문의처는 업무 성격에 따라 분기하세요: 권리보호·권리침해는 납세자보호담당관, 민원 및 사업자등록·증명 발급은 관할 세무서 민원봉사실 또는 홈택스, 세무조사는 실제 조사관서·담당 조사팀, 그 밖에 이미 이루어진 고지·통지·자료요구·처분은 이를 발신하거나 수행한 관서/부서, 일반적인 세법 안내는 국세상담센터입니다. 소관기관은 문장에 언급된 기관명만으로 판단하지 말고 사용자가 마지막으로 하려는 실질적 행위와 처리 대상 기준으로 판단하세요. 예: “시청에 제출할 국세 납세증명 발급”은 시청이 제출처일 뿐이며, 국세 납세증명 발급의 소관은 국세청(NTS)입니다. 지방세(취득세·재산세·자동차세·주민세·지방소득세 등)의 부과·납부·증명 등 최종 행위는 일반적으로 지방자치단체 소관입니다. 관세는 관세청 소관입니다.
known_facts에 모르는 값은 null로 두고 날짜를 추측하지 마세요.
JSON 스키마: summary, possible_agency, responsible_agency, agency_rationale, inquiry_type, tax_type, tax_stage, administrative_action, desired_outcome, issue_types, known_facts, missing_facts, questions, confidence.
known_facts에는 notice_kind, notice_date, prior_explanation, tax_audit_status, appeal_status, filing_status, collection_status를 포함하세요."""


def _is_simple_tax_concept_question(text: str) -> bool:
    """단어 하나(예: 부당·부인)만으로 권리보호에 보내지 않도록 개념 질문을 식별합니다."""
    raw = (text or "").strip()
    compact = raw.replace(" ", "")
    ask_cues = ("뭐야", "뭐예요", "무엇인가", "무슨뜻", "뜻이뭐", "설명해", "설명해줘", "알려줘", "알려주세요", "안내해줘", "안내해주세요", "의미가", "개념")
    if not any(cue in compact for cue in ask_cues):
        return False
    # 실제 처분·행정행위에 대한 불만/대응 요청이 있으면 개념 문의로 보지 않습니다.
    concrete_event_cues = ("세무조사중", "세무조사를받", "조사관이", "고지서를받", "세금을부과받", "압류됐", "압류되", "체납", "자료제출을요구", "자료를요구받", "불복", "취소해", "해제해", "환급이지연", "담당자가", "신고를잘못", "처분을받", "권리보호요청", "권리보호를신청")
    if any(cue in compact for cue in concrete_event_cues):
        return False
    return True


def classify(text, llm=None):
    fallback = analyze_fallback(text)
    result = fallback
    if llm and llm.available:
        try:
            raw = llm.generate_json(SYSTEM, f"민원 원문을 아래 스키마에 맞춰 분류하세요.\n민원 원문:\n{text}")
            result = normalize_analysis(raw, text)
        except Exception:
            result = fallback
    # 사업자등록 세부 유형과 실제 처리 문제를 구분합니다.
    compact_text = (text or "").replace(" ", "")
    business_registration_inquiry = any(term in compact_text for term in (
        "사업자등록", "사업자등록신청", "사업자등록방법", "사업자등록변경", "사업자등록정정",
        "사업자등록말소", "사업자등록휴폐업", "사업자등록증", "사업자등록휴업", "사업자등록폐업",
        "사업자휴업", "사업자폐업", "휴업신고", "폐업신고", "휴업신청", "폐업신청",
        "휴업 신고", "폐업 신고", "휴업 신청", "폐업 신청"
    ))
    if any(term in compact_text for term in ("휴업",)):
        business_registration_subtype = "휴업 신고"
    elif "폐업" in compact_text:
        business_registration_subtype = "폐업 신고"
    elif any(term in compact_text for term in ("정정", "변경", "주소변경", "상호변경", "업종변경")):
        business_registration_subtype = "사업자등록 정정·변경"
    elif any(term in compact_text for term in ("신청", "신규등록", "등록방법", "등록하는법")):
        business_registration_subtype = "신규 사업자등록 신청"
    else:
        business_registration_subtype = "기타 사업자등록 문의"
    business_registration_problem_cues = (
        "처리가안", "처리되지않", "처리안", "지연", "반려", "거부", "불허", "오류", "잘못처리",
        "신청했는데", "접수했는데", "등록이안", "등록되지않", "취소당", "답변이없", "회신이없",
        "담당자가", "부당하게", "민원을제기", "시정해", "문제가있", "해결해줘"
    )
    business_registration_processing_problem = business_registration_inquiry and any(
        cue in compact_text for cue in business_registration_problem_cues
    )
    business_registration_simple_inquiry = business_registration_inquiry and not business_registration_processing_problem
    # 단순 개념 질문은 '부당', '부인' 등의 단어가 포함되어도 그 단어만으로 권리보호 분류하지 않습니다.
    simple_concept_question = _is_simple_tax_concept_question(text)
    if business_registration_simple_inquiry or simple_concept_question:
        result["inquiry_type"] = "SIMPLE_TAX_QUESTION"
        result["desired_outcome"] = "단순 세법 문의"
        result["issue_types"] = []
        result["questions"] = []
    # 세목 오타·약칭은 별도 세목 사전과 유사도 비교로 재검토한다.
    intake = classify_intake(text, result)
    result.update(intake)
    # 초기 분류의 단어 매칭 결과보다 개념 질문 의도를 우선합니다.
    if business_registration_inquiry:
        result["business_registration_inquiry"] = True
        result["business_registration_subtype"] = business_registration_subtype
        result["business_registration_processing_problem"] = business_registration_processing_problem
        result["business_registration_simple_inquiry"] = business_registration_simple_inquiry
        result["summary"] = text.strip() or result.get("summary", "사업자등록 문의")
        result["possible_agency"] = "NTS"
        result["responsible_agency"] = "국세청"
        result["tax_stage"] = "사업자등록"
        result["recommended_contact"] = "관할 세무서 민원봉사실 또는 홈택스"
        if business_registration_simple_inquiry:
            result["inquiry_type"] = "SIMPLE_TAX_QUESTION"
            result["desired_outcome"] = "단순 세법 문의"
            result["issue_types"] = []
            result["questions"] = []
            result["missing_facts"] = []
            result["contact_reason"] = f"{business_registration_subtype}에 관한 일반 문의이므로 국세청 소관 단순 안내로 처리합니다."
        else:
            result["inquiry_type"] = "TAX_ADMIN_COMPLAINT"
            result["desired_outcome"] = result.get("desired_outcome") or "신고·등록 처리"
            result["questions"] = result.get("questions") or ["신청·신고한 날짜와 접수번호, 현재 처리 상태를 알려주시겠어요?"]
            result["missing_facts"] = result.get("missing_facts") or ["신청일 또는 접수번호", "현재 처리 상태"]
            result["contact_reason"] = f"{business_registration_subtype}의 실제 처리 문제로 보이므로 관할 세무서 민원봉사실 또는 홈택스에서 접수·처리 상태를 확인합니다."
    elif simple_concept_question:
        result["inquiry_type"] = "SIMPLE_TAX_QUESTION"
        result["desired_outcome"] = "단순 세법 문의"
        result["issue_types"] = []
        result["recommended_contact"] = "국세종합상담센터"
        result["contact_reason"] = "단순 세법 개념 문의이므로 간략히 안내한 뒤 국세종합상담센터로 연결합니다."
    result["intake_classification"] = {
        "responsible_agency": result.get("responsible_agency"),
        "tax_type": result.get("tax_type"),
        "tax_type_candidate": result.get("tax_type_candidate"),
        "tax_type_similarity": result.get("tax_type_similarity"),
        "tax_stage": result.get("tax_stage"),
        "administrative_action": result.get("administrative_action"),
        "desired_outcome": result.get("desired_outcome"),
    }
    return result
