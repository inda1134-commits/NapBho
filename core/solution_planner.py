"""AI가 선정한 해결 경로를 안내 유형으로 정리하고, LLM으로 안내문 초안을 작성합니다."""
from __future__ import annotations

CATEGORIES = {"simple_info", "submission", "remedy_procedure", "rights_protection"}


def classify_solution_category(route: str, analysis: dict) -> str:
    summary = str(analysis.get("summary", ""))
    text = f"{route} {analysis.get('desired_outcome', '')} {' '.join(analysis.get('issue_types') or [])} {analysis.get('administrative_action', '')}"
    compact_summary = (summary + " " + str(route)).replace(" ", "")
    # 명시적 분류 플래그를 최우선 적용합니다. LLM이 요약에서 키워드를 생략해도 단순 안내로 유지합니다.
    if analysis.get("business_registration_simple_inquiry") or (analysis.get("business_registration_inquiry") and not analysis.get("business_registration_processing_problem")):
        return "simple_info"
    if (not analysis.get("business_registration_processing_problem") and any(term in compact_summary for term in ("사업자등록", "사업자등록신청", "사업자등록방법", "사업자등록변경", "사업자등록정정", "사업자등록증", "사업자등록휴업", "사업자등록폐업", "사업자휴업", "사업자폐업", "휴업신고", "폐업신고", "휴업신청", "폐업신청"))):
        return "simple_info"
    # 단순 개념 질문의 분류를 우선합니다. '부당', '부인'은 세법 용어 설명에도 쓰일 수 있어
    # 그 단어 자체만으로 권리보호 경로를 선택하지 않습니다.
    simple_question_cues = ("뭐야", "뭐예요", "무엇인가", "무슨뜻", "설명해", "알려줘", "알려주세요", "안내해줘", "안내해주세요", "의미가", "개념")
    concrete_event_cues = ("세무조사중", "세무조사를받", "조사관이", "고지서를받", "세금을부과받", "압류됐", "압류되", "체납", "자료제출을요구", "자료를요구받", "불복", "취소해", "해제해", "환급이지연", "담당자가", "처분을받", "권리보호요청")
    if (analysis.get("inquiry_type") == "SIMPLE_TAX_QUESTION" or analysis.get("desired_outcome") == "단순 세법 문의") and not any(cue in compact_summary for cue in concrete_event_cues):
        return "simple_info"
    if any(cue in compact_summary for cue in simple_question_cues) and not any(cue in compact_summary for cue in concrete_event_cues):
        return "simple_info"
    rights_terms = ("권리보호", "납세자보호담당관", "부당한 세무조사", "절차상 권리침해", "권리 보호")
    remedy_terms = ("이의신청", "심사청구", "심판청구", "불복", "과세전적부", "과세전적부심사", "고충민원", "행정소송")
    submission_terms = ("제출", "신고", "경정청구", "기한후신고", "등록 처리", "자료 요구", "징수유예", "분납", "압류 해제")
    if any(term in text for term in rights_terms):
        return "rights_protection"
    if any(term in text for term in remedy_terms):
        return "remedy_procedure"
    if any(term in text for term in submission_terms):
        return "submission"
    if "상담" in text or "문의" in text or (analysis.get("inquiry_type") == "SIMPLE_TAX_QUESTION"):
        return "simple_info"
    # 분류가 불분명하면 서류 제출을 권고하지 않고 일반 상담으로 연결
    return "simple_info"


def _fallback_plan(category: str, route: str, analysis: dict, deadline: dict) -> dict:
    facts = analysis.get("known_facts") or {}
    if category == "simple_info":
        business_registration = bool(analysis.get("business_registration_simple_inquiry")) or (bool(analysis.get("business_registration_inquiry")) and not analysis.get("business_registration_processing_problem")) or (not analysis.get("business_registration_processing_problem") and any(term in (str(analysis.get("summary", "")) + str(route)).replace(" ", "") for term in ("사업자등록", "사업자등록신청", "사업자등록방법", "사업자등록변경", "사업자등록정정", "사업자등록증", "사업자등록휴업", "사업자등록폐업", "사업자휴업", "사업자폐업", "휴업신고", "폐업신고", "휴업신청", "폐업신청")))
        contact = "관할 세무서 민원봉사실 또는 홈택스" if business_registration else "국세종합상담센터"
        business_subtype = analysis.get("business_registration_subtype", "사업자등록")
        business_guidance = {
            "신규 사업자등록 신청": "신규 사업자등록 신청은 홈택스에서 신청 가능 여부와 업종별 제출서류를 확인하거나 관할 세무서 민원봉사실에 문의하세요.",
            "휴업 신고": "사업을 일시적으로 쉬는 경우 휴업 신고 대상과 처리 방법을 홈택스에서 확인하거나 관할 세무서 민원봉사실에 문의하세요.",
            "폐업 신고": "사업을 종료하는 경우 폐업 신고 방법과 관련 세금 신고 여부를 홈택스에서 확인하거나 관할 세무서 민원봉사실에 문의하세요.",
            "사업자등록 정정·변경": "상호·주소·업종 등 등록사항 변경은 사업자등록 정정 대상과 필요한 자료를 홈택스에서 확인하거나 관할 세무서 민원봉사실에 문의하세요.",
        }
        explanation = ("사업자등록은 국세청 소관 업무입니다. " + business_guidance.get(business_subtype, "사업자등록 관련 신청·신고는 홈택스에서 확인하거나 관할 세무서 민원봉사실에 문의하세요.")) if business_registration else f"{route}에 관한 일반적인 안내입니다. 개인별 세액이나 적용 여부는 구체적인 사실관계에 따라 달라질 수 있으므로, 정확한 내용은 국세종합상담센터에서 확인해 주세요."
        return {
            "category": category,
            "title": "사업자등록 간단 안내" if business_registration else "간단한 세법 안내",
            "explanation": explanation,
            "steps": [],
            "documents": [],
            "institution": contact,
            "cautions": [],
        }
    if category == "submission":
        return {
            "category": category,
            "title": "홈택스 또는 담당 세무서를 통한 신고·서류 제출",
            "explanation": f"{route} 진행에 필요한 제출 방식과 요건을 담당 세무서 또는 홈택스에서 확인해야 합니다.",
            "steps": ["제출 대상 신고·과세기간과 제출기한을 확인합니다.", "홈택스에서 해당 신고·신청 메뉴를 확인하거나 담당 세무서에 제출 방법을 문의합니다."],
            "documents": ["관련 신고서·신청서", "사실관계를 뒷받침하는 증빙자료", "고지서·안내문(관련된 경우)"],
            "institution": "국세청 홈택스 또는 관할 세무서",
            "cautions": ["정확한 서식과 첨부서류는 신청 유형·세목에 따라 달라집니다."],
        }
    if category == "remedy_procedure":
        return {
            "category": category,
            "title": "국세 불복·권리구제 절차 검토",
            "explanation": f"{route}의 대상 처분인지, 신청 자격 및 기한을 먼저 확인해야 합니다.",
            "steps": ["처분서의 처분 종류, 처분일·송달일 및 불복기한을 확인합니다.", "관할 세무서 또는 국세청에서 신청 요건을 확인하고, 절차에 맞는 기관에 제출합니다."],
            "documents": ["불복 신청서 등 해당 절차의 서식", "처분서·고지서 및 송달 관련 자료", "주장 내용을 뒷받침하는 증빙자료", "대리 신청 시 위임 관련 서류(해당하는 경우)"],
            "institution": "절차에 따라 관할 세무서·국세청 또는 조세심판원",
            "cautions": [deadline.get("message", "신청기한은 처분 종류와 송달일에 따라 달라질 수 있으므로 즉시 확인하세요.")],
        }
    return {
        "category": "rights_protection",
        "title": "납세자 권리보호 제도 안내",
        "explanation": f"AI 상담원이 선정한 해결 방법은 **{route}**입니다. 세무행정 과정에서 납세자의 권리가 침해되었거나 부당한 절차가 있었다고 생각되는 경우, 납세자보호담당관을 통해 해당 제도의 적용 대상인지 확인하고 시정·보호를 요청할 수 있습니다. 실제 적용 여부는 사건 내용과 진행 단계에 따라 담당 기관이 판단합니다.",
        "steps": [
            f"1. 선택한 제도와 문제 유형을 확인합니다: {route}.",
            "2. 문제 행위의 날짜, 담당 부서, 요구·통지 내용, 이미 진행된 조치와 납세자에게 미친 영향을 시간순으로 정리합니다.",
            "3. 관할 세무서 납세자보호담당관 또는 지방국세청 납세자보호담당관에게 대상 여부와 접수 방법을 문의합니다.",
            "4. 권리보호 요청서 또는 기관에서 안내하는 신청서에 사실관계와 요청 사항을 작성하고 증빙자료를 첨부합니다.",
            "5. 접수 후 보완 요청이나 처리 결과 통지를 확인합니다. 별도의 불복기한이 있다면 그 기한도 별도로 관리합니다.",
            "6. 세법·절차가 복잡하거나 청구서 작성에 도움이 필요한 경우 국세청의 국선대리인 지원 대상과 신청 요건을 담당 기관에 문의합니다. 지원 대상·범위는 제도별 요건 및 사건 유형에 따라 달라질 수 있습니다."
        ],
        "documents": [
            "권리보호 요청서 또는 담당 기관이 안내하는 신청서",
            "고지서·과세예고통지서·자료제출 요구서·조사 관련 통지 등 관련 문서",
            "문제 경위서(날짜, 담당 부서, 요청·답변 내용, 피해 또는 불편 사항)",
            "문자·이메일·공문·통화 기록 등 사실관계 확인 자료",
            "주장을 뒷받침하는 회계자료·신고서·영수증 등 관련 증빙",
            "대리인이 신청하는 경우 위임장 등 기관이 요구하는 서류"
        ],
        "institution": "관할 세무서 또는 지방국세청 납세자보호담당관",
        "cautions": [
            "권리보호 요청은 이의신청·심사청구·심판청구·행정소송과 별개의 제도일 수 있으며, 불복기한을 자동으로 연장하거나 대체하지 않습니다.",
            "국선대리인 지원은 모든 사건에 자동 적용되지 않습니다. 사건 종류, 청구 금액, 소득·재산 등 현행 지원 요건과 지원 범위를 공식 기관에서 확인하세요.",
            "위법·부당 여부나 권리보호 대상 해당 여부를 이 안내만으로 확정할 수 없습니다."
        ],
    }



def select_best_solution(
    candidates: list[str], analysis: dict, decision: dict, stage_info: dict, deadline: dict, llm=None, retrieved: list[dict] | None = None
) -> dict:
    """확정된 상담 사실을 바탕으로 가장 적합한 해결 방법 하나를 선정한다."""
    if not candidates:
        return {"solution": "국세상담센터 상담", "reason": "확인된 정보만으로 세부 절차를 확정하기 어려워 담당 기관의 확인이 필요합니다."}

    fallback = {
        "solution": candidates[0],
        "reason": "확인된 과세 단계와 사실관계를 기준으로 우선 검토할 해결 방법입니다. 구체적인 신청 가능 여부와 기한은 담당 기관에서 확인해야 합니다.",
    }
    if not (llm and llm.available):
        return fallback

    system = """당신은 한국 국세 민원 상담의 해결방법 판단 보조자입니다. 이전 단계에서 확인된 사실만 근거로 후보 중 가장 적합한 해결방법을 정확히 하나 선택하세요. 후보에 없는 방법을 만들지 마세요. 단순히 후보를 나열하거나 사용자에게 선택을 요청하지 마세요. 절차의 단계, 문제의 핵심, 이미 받은 문서, 진행 상태, 기한 위험을 고려하세요. 사실이 부족하면 되묻기보다 후보 중 가장 안전하고 직접적으로 맞는 방법을 고르고 불확실성을 reason에 밝히세요. JSON만 반환하세요."""
    retrieved = retrieved or []
    evidence = "\n".join(f"[{x.get('filename', '참고자료')} p.{x.get('page', '?')}] {x.get('text', '')[:1200]}" for x in retrieved[:6]) or "관련 벡터 DB 근거 없음"
    prompt = f"""확인된 과세 단계: {stage_info}
검색된 참고자료(RAG 근거; 아래 내용만 보조 근거로 활용):
{evidence}
초기 불만 및 LLM 분석: {analysis}
누적 답변/확정 사실: {analysis.get('confirmed_facts', {})}
규칙 엔진 판단: {decision}
기한 확인: {deadline}
선택 가능한 후보(이 중 하나만 선택): {candidates}
반환 형식: {{"solution": "후보 중 정확히 하나", "reason": "선정 이유와 주의할 불확실성"}}
가장 적합한 후보 하나를 선정하세요."""
    try:
        result = llm.generate_json(system, prompt)
        chosen = str(result.get("solution", "")).strip()
        reason = str(result.get("reason", "")).strip()
        if chosen not in candidates:
            return fallback
        return {"solution": chosen, "reason": reason or fallback["reason"]}
    except Exception:
        return fallback



def _appeal_detail_plan(route: str, deadline: dict, retrieved: list[dict] | None = None) -> dict:
    """4개 주요 국세 권리구제 절차의 상세 구조화 안내. 법률상 세부요건은 RAG 근거로 보완한다."""
    retrieved = retrieved or []
    evidence_names = list(dict.fromkeys(
        f"{x.get('filename', '참고자료')} · {x.get('page', '?')}쪽" for x in retrieved[:8]
    ))
    common_docs = [
        "과세예고통지서·세무조사결과통지서 또는 납세고지서 등 대상 문서",
        "통지·송달 사실과 날짜를 확인할 수 있는 자료",
        "청구서 및 처분의 사실관계·법률상 이유를 뒷받침하는 증빙자료",
        "앞선 불복절차의 결정서(이미 신청한 경우)",
        "대리인 선임 시 위임장 등 접수기관이 요구하는 자료"
    ]
    details = {
        "과세전적부": {
            "title": "과세전적부심사청구 상세 안내", "institution": "과세예고·세무조사결과 통지서에 표시된 관서 및 현행 공식 접수처",
            "eligibility": "과세가 고지되기 전 과세예고통지 또는 세무조사결과통지 등 법정 청구대상 통지를 받았는지, 청구인 적격·제외 사유·청구기간을 확인합니다. 이미 납세고지서를 받은 경우에는 사후 불복절차인지 구분해야 합니다.",
            "steps": ["통지서의 종류, 발신기관, 통지일, 과세예정 세목·과세기간·세액을 확인합니다.", "다투는 쟁점과 사실관계, 과세예정 내용이 잘못되었다고 보는 이유를 항목별로 정리합니다.", "현행 공식 서식·접수처·제출방법을 확인하고 청구서와 증빙을 제출합니다.", "접수증, 보완요구 및 결과 통지를 확인합니다."],
            "processing": "일반적으로 접수·형식요건 확인, 필요한 경우 보완, 심의·사실 확인, 결정 및 결과 통지 순서로 진행됩니다. 실제 결정유형과 처리기간은 등록된 최신 공식 참고자료에서 확인합니다.",
            "effects": "채택되는 범위에서는 과세 전 시정으로 이어질 수 있습니다. 불채택·심사제외·재조사 등 결정의 의미는 실제 결정서와 적용 규정에 따라 확인합니다. 이후 고지서를 받으면 사후 불복기한을 별도로 관리해야 합니다."},
        "이의신청": {
            "title": "이의신청 상세 안내", "institution": "처분서에 표시된 관서 및 국세기본법상 관할 접수기관(현행 공식 자료로 확인)",
            "eligibility": "이미 이루어진 국세 처분에 대해 위법·부당함을 다투는 절차입니다. 처분 대상성, 청구인 적격, 법정기간, 제외 사유와 심사청구·심판청구를 바로 할 수 있는지 확인합니다.",
            "steps": ["고지서·처분서와 송달자료를 확보하고 다투는 처분·세액·과세기간을 특정합니다.", "청구 취지와 이유를 사실관계·법률 쟁점별로 작성하고 증빙을 정리합니다.", "현행 서식과 접수기관을 확인한 뒤 이의신청서 및 증빙을 제출합니다.", "보정 요구와 결정서 송달을 확인하고, 후속 불복 여부 및 기한을 바로 확인합니다."],
            "processing": "일반적으로 접수, 청구요건·기간 검토, 사실·증거 검토, 필요한 보완 또는 추가 확인, 결정 및 결정서 송달 순으로 진행됩니다. 결정기간과 가능한 결정유형은 공식 참고자료에서 확인합니다.",
            "effects": "결정 내용에 따라 처분이 유지되거나 전부·일부 취소·경정 또는 재처리될 수 있습니다. 신청 자체가 징수·집행을 자동 정지한다고 볼 수 없으며, 불복 결정 이후 후속 절차와 기간을 확인해야 합니다."},
        "심사청구": {
            "title": "심사청구 상세 안내", "institution": "국세기본법상 심사청구 접수기관(현행 국세청 공식 안내에서 확인)",
            "eligibility": "국세 처분에 대한 사후 불복절차입니다. 처분 대상성, 청구인 적격, 청구기간, 이의신청 선행 여부 또는 선택 관계, 제외·중복 사유를 확인합니다.",
            "steps": ["처분서·고지서, 송달자료 및 앞선 이의신청 결정서(해당 시)를 준비합니다.", "처분의 위법·부당 사유, 청구 취지와 이유, 쟁점별 증거를 정리합니다.", "현행 공식 서식·접수방법을 확인하고 심사청구서와 증빙을 제출합니다.", "보정·추가 자료 요청 및 결정서 송달을 확인하고 후속 절차의 기간을 관리합니다."],
            "processing": "일반적으로 접수, 기간·청구요건 검토, 기록과 증거 검토, 필요한 사실 확인, 심리·결정 및 결정서 통지 순으로 진행됩니다. 세부 처리기간과 결정유형은 현행 참고자료에서 확인합니다.",
            "effects": "결정에 따라 처분의 전부·일부 취소·경정 또는 재처리 등의 효과가 발생할 수 있습니다. 청구만으로 징수·집행이 자동 정지된다고 안내하지 않으며, 결정 후 행정소송 등 가능 절차와 기간을 확인합니다."},
        "심판청구": {
            "title": "심판청구 상세 안내", "institution": "조세심판원(현행 공식 접수·전자청구 안내 확인)",
            "eligibility": "국세 처분에 대해 조세심판원의 판단을 구하는 사후 불복절차입니다. 처분 대상성, 청구인 적격, 법정기간, 앞선 불복절차, 제외 사유 및 중복 청구 여부를 확인합니다.",
            "steps": ["처분서·고지서, 송달자료, 앞선 불복 결정서(해당 시)와 쟁점별 증거를 준비합니다.", "청구 취지·이유, 처분 내용, 사실관계와 증거를 심판청구서에 정리합니다.", "조세심판원의 현행 서식과 전자·서면 접수 방법을 확인해 제출합니다.", "접수 확인, 보정 요구, 의견 제출·심리 관련 안내 및 결정서 송달을 확인합니다."],
            "processing": "일반적으로 접수, 청구요건·기간 검토, 과세관청 의견과 청구인 주장·증거 검토, 필요시 추가 자료 또는 심리, 결정 및 결정서 통지 순으로 진행됩니다. 실제 처리기간과 심리방식은 공식 참고자료에서 확인합니다.",
            "effects": "결정의 주문과 이유에 따라 처분 취소·경정 또는 재처리 등 효과가 달라집니다. 결정만으로 환급이 자동 완료된다고 단정하지 않으며, 징수·집행 정지 여부와 후속 행정소송 가능성·기간을 별도로 확인합니다."}
    }
    key = "과세전적부" if "과세전적부" in route else next((k for k in ("이의신청", "심사청구", "심판청구") if k in route), None)
    if not key:
        return {}
    d = details[key]
    source_note = ("\n\n**검색된 참고자료:** " + "、".join(evidence_names)) if evidence_names else "\n\n**참고자료 확인:** 지정된 벡터 DB에서 이 절차의 직접 근거가 검색되지 않았습니다. 아래는 진행을 위한 일반적인 구조이며, 구체적인 요건·기한·효과는 공식 참고자료 확인이 필요합니다."
    explanation = (
        f"**신청요건**\n\n{d['eligibility']}\n\n"
        f"**처리절차**\n\n{d['processing']}\n\n"
        f"**법률 효과**\n\n{d['effects']}\n\n"
        f"**기한 관련 주의**\n\n{deadline.get('message', '선택한 30일·60일·90일 범주는 위험 신호일 뿐, 법정기한 준수 여부를 확정하지 않습니다.')}"
        f"{source_note}"
    )
    cautions = [
        "30일 내·60일 내·90일 내 선택만으로 법정기한 준수 여부를 확정하지 않습니다. 실제 기산점·기간·예외는 처분 종류와 공식 자료로 확인하세요.",
        "불복을 제기했다고 해서 세금 징수나 집행이 자동으로 정지된다고 단정하지 마세요.",
        "구체적인 법률 효과와 처리기간은 현재 등록된 공식 참고자료와 실제 결정서에 따라 확인해야 합니다."
    ]
    if not retrieved:
        cautions.append("지정된 벡터 DB에서 직접 근거가 검색되지 않아 신청요건·기한·법률효과는 확정 안내가 아닙니다.")
    return {"category": "remedy_procedure", "title": d["title"], "explanation": explanation, "steps": d["steps"], "documents": common_docs, "institution": d["institution"], "cautions": cautions}

def build_solution_plan(analysis: dict, decision: dict, deadline: dict, selected_route: str, llm=None, retrieved: list[dict] | None = None) -> dict:
    category = classify_solution_category(selected_route, analysis)
    fallback = _fallback_plan(category, selected_route, analysis, deadline)
    appeal_fallback = _appeal_detail_plan(selected_route, deadline, retrieved) if category == "remedy_procedure" else {}
    if appeal_fallback:
        fallback = appeal_fallback
    # 단순 세법 설명·안내 요청은 LLM이 핵심만 짧게 설명하고 상담센터로 연결합니다.
    # 신고/불복/권리보호처럼 실제 행정 조치가 필요한 사안은 이 분기로 들어오지 않습니다.
    if category == "simple_info":
        if not (llm and llm.available):
            return fallback
        business_registration = bool(analysis.get("business_registration_simple_inquiry")) or (bool(analysis.get("business_registration_inquiry")) and not analysis.get("business_registration_processing_problem")) or (not analysis.get("business_registration_processing_problem") and any(term in (str(analysis.get("summary", "")) + str(selected_route)).replace(" ", "") for term in ("사업자등록", "사업자등록신청", "사업자등록방법", "사업자등록변경", "사업자등록정정", "사업자등록증", "사업자등록휴업", "사업자등록폐업", "사업자휴업", "사업자폐업", "휴업신고", "폐업신고", "휴업신청", "폐업신청")))
        simple_system = """당신은 한국의 일반적인 국세·세법 질문에 짧고 쉽게 답하는 상담 도우미입니다. 사용자가 '설명해줘', '안내해줘', '알려줘', '무엇이야/뭐야'라고 묻는 단순 개념 질문에 직접 답하세요. 검색된 참고자료가 제공되면 우선 근거로 사용하고, 자료에 없는 법조문·세율·기한을 지어내지 마세요. 근거가 불충분하거나 최신 여부가 중요한 내용은 단정하지 말고 국세종합상담센터 확인을 권하세요. 복잡한 절차, 제출서류 목록, 장황한 배경 설명은 하지 마세요. 한국어로 2~4문장 이내로 간단히 작성하고, 개별 사실관계에 따라 달라질 수 있음을 필요한 경우에만 덧붙이세요. JSON만 반환하세요."""
        simple_evidence = "\n".join(
            f"[{x.get('filename', '참고자료')} p.{x.get('page', '?')}] {x.get('text', '')[:1200]}"
            for x in (retrieved or [])[:4]
        ) or "관련 업로드 참고자료 검색 결과 없음. 일반적인 설명만 제공하고 불확실한 세부사항은 단정하지 말 것."
        contact = "관할 세무서 민원봉사실 또는 홈택스" if business_registration else "국세종합상담센터"
        simple_prompt = f"""사용자의 질문/세목: {analysis.get('summary', '')}
분류된 세목: {analysis.get('tax_type', '미확인')}
선택 경로: {selected_route}
검색된 참고자료:
{simple_evidence}

짧고 이해하기 쉬운 핵심 답변을 작성하세요. 질문에 바로 답하세요. 사업자등록 신청·휴업·폐업 문의라면 국세청 소관의 단순 문의로 처리하고 홈택스 또는 관할 세무서 민원봉사실을 안내하세요. 그 외 일반 세법 문의는 국세종합상담센터를 안내하세요.
반환 JSON: {{"category":"simple_info","title":"짧은 제목","explanation":"2~4문장 이내 핵심 답변","steps":[],"documents":[],"institution":"{contact}","cautions":[]}}"""
        try:
            result = llm.generate_json(simple_system, simple_prompt)
            explanation = result.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                return fallback
            # 상담센터 연결 정보는 항상 고정해 누락되거나 다른 기관으로 바뀌지 않게 합니다.
            return {
                "category": "simple_info",
                "title": str(result.get("title") or "간단한 세법 안내"),
                "explanation": explanation.strip(),
                "steps": [],
                "documents": [],
                "institution": contact,
                "cautions": [],
            }
        except Exception:
            return fallback
    if not (llm and llm.available):
        return fallback
    system = """당신은 한국 국세 민원 안내문 작성 보조자입니다. AI가 선정한 해결 경로와 확정된 사실관계를 바탕으로 JSON만 반환하세요. category는 simple_info, submission, remedy_procedure, rights_protection 중 하나로 선택하세요. 단순 세법 설명·상담은 simple_info, 신고서·자료·신청서 제출이 핵심이면 submission, 이의신청·심사청구·심판청구·과세전적부심사 등 공식 불복절차이면 remedy_procedure, 세무공무원의 권리침해·부당한 조사 등 납세자 권리보호 요청이 핵심이면 rights_protection으로 분류하세요.

과세전적부심사청구·이의신청·심사청구·심판청구 중 하나가 선택되면 explanation을 반드시 다음 소제목으로 상세 작성하세요: 신청요건, 신청절차, 처리절차, 법률 효과, 기한 관련 주의. steps는 사용자가 실제로 수행할 순서만, documents는 준비할 자료만 작성합니다. 각 항목은 검색된 벡터 DB 근거에 있는 내용으로 구체화하되, 근거가 없으면 '등록된 참고자료에서 확인되지 않음'이라고 표시합니다. 과세전적부심사는 고지 전인지, 나머지는 처분 후 불복인지 먼저 구분하세요. 청구만으로 징수·집행이 자동 정지된다고 단정하지 마세요.

중복 방지 규칙은 반드시 지키세요.
- steps(진행 절차)에는 사용자가 순서대로 수행할 행동만 작성합니다. 서류 이름이나 준비물 목록을 절차 항목으로 반복하지 마세요.
- documents(준비·제출 서류)에는 실제로 준비할 문서·증빙의 이름만 작성합니다. 신청 방법, 문의 행동, 제출 순서를 절차처럼 설명하지 마세요.
- 같은 내용이나 표현만 바꾼 항목을 두 목록 안팎에서 반복하지 마세요. 예를 들어 '사실관계를 시간순으로 정리'는 절차에만, '경위서'는 서류 목록에만 둡니다.
- 권리보호 유형에서도 진행 절차와 준비서류를 명확히 구분하고, 각 목록은 서로 다른 정보를 제공해야 합니다.

법률 판단을 단정하지 말고, 확인되지 않은 제출기한·법조문·URL·서식명을 만들지 마세요. documents, steps, cautions는 한국어 문자열 배열로 작성하세요. 불확실하면 '담당 기관에서 확인'이라고 명시하세요. 권리보호 경로이면 RAG 검색자료를 먼저 검토해 선택된 세부 유형과 일치하는 자료가 있는지 판별하세요. 일치하는 자료가 있으면 자료에 명시된 대상·적용 요건, 신청 절차, 첨부서류, 담당 기관을 우선 반영하세요. 자료에 없는 요건이나 서류를 만들지 말고 확인이 필요하다고 표시하세요. 일반적인 권리보호 자료만 검색되면 특정 유형의 요건처럼 서술하지 마세요. 각 사실은 검색자료에 실제로 적힌 내용만 사용하세요. 자료에서 확인되지 않은 내용은 사실처럼 쓰지 말고 '업로드된 참고자료에서 확인되지 않음'으로 구분하세요. 자료가 서로 다르면 임의로 합치지 말고 상충 사실과 공식 확인 필요성을 cautions에 적으세요."""
    retrieved = retrieved or []
    evidence = "\n".join(f"[{x.get('filename', '참고자료')} p.{x.get('page', '?')}] {x.get('text', '')[:1500]}" for x in retrieved[:8]) or "관련 참고자료를 찾지 못했습니다. 근거 없는 요건은 단정하지 마세요."
    prompt = f"""아래 확정 자료와 검색된 RAG 근거를 사용해 실행 가능한 안내를 작성하세요.
검색된 참고자료(RAG):
{evidence}
규칙 기반 예상 category: {category}
category 선택 기준: simple_info=간단한 세법 안내 및 국세상담센터 연결, submission=신고서·신청서·증빙서류 제출 및 홈택스 연결, remedy_procedure=불복 등 구제절차·제출기관 안내, rights_protection=권리보호 대상·절차·서류·공식 사이트 안내. 과세전적부심사청구·이의신청·심사청구·심판청구는 신청요건·신청절차·처리절차·법률 효과를 각각 구분해 상세히 작성하세요.
AI가 선정한 해결 경로(최종 안내의 중심): {selected_route}
초기 불만 및 대화로 확정된 사실관계: {analysis}
규칙 엔진 검토 결과: {decision}
기한 확인 결과: {deadline}
기본 안내 초안: {fallback}
반환 JSON 스키마: {{"category":"simple_info|submission|remedy_procedure|rights_protection","title":"짧은 제목","explanation":"간단한 설명","steps":["실행 단계"],"documents":["제출 서류"],"institution":"제출/문의 기관","cautions":["주의사항"]}}
선택된 해결 경로와 확정된 사실관계에 가장 적합한 category를 선택하세요. 권리보호 경로라면 검색된 참고자료에서 해당 세부 유형이 실제로 확인되는지 먼저 판단하고, 확인되는 경우 대상·절차·첨부서류·담당 기관을 해당 자료에 근거해 작성하세요. 각 항목이 근거 문서에 명시되어 있지 않으면 추측하지 말고 '참고자료에서 확인되지 않음—담당 기관 확인 필요'라고 표시하세요. 특히 권리보호 유형이 정확히 일치하지 않는 일반 자료를 세부 유형의 요건으로 간주하지 마세요. 문서에 날짜·기한·조문·서식·URL이 없으면 새로 만들지 마세요. 자료가 서로 상충하면 하나를 임의로 선택하지 말고 cautions에 상충 내용을 표시하세요. 해당 유형 자료가 없으면 자료가 없음을 설명하고 일반적인 확인 절차만 안내하세요. steps에는 순서가 있는 행동만, documents에는 준비할 문서명만 적으세요. 두 목록에서 동일·유사 내용을 반복하지 마세요. 정확한 요건은 공식 기관에서 확인하도록 하세요."""
    try:
        result = llm.generate_json(system, prompt)
        if result.get("category") not in CATEGORIES:
            result["category"] = category
        for key in ("steps", "documents", "cautions"):
            if not isinstance(result.get(key), list):
                result[key] = fallback[key]
        for key in ("title", "explanation", "institution"):
            if not isinstance(result.get(key), str) or not result[key].strip():
                result[key] = fallback[key]
        # 권리보호 유형은 고정 안내의 상세한 제도 설명·국선대리인 주의사항을 유지하되,
        # 절차·서류 목록은 LLM 결과와 기본 목록을 합치지 않아 유사 항목이 중복되지 않게 합니다.
        if category == "rights_protection":
            result["title"] = result.get("title") or fallback["title"]
            result["steps"] = result["steps"] or fallback["steps"]
            result["documents"] = result["documents"] or fallback["documents"]
            result["cautions"] = list(dict.fromkeys((result.get("cautions") or []) + fallback["cautions"]))
            # 참고자료가 없으면 검색자료로 검증한 것처럼 보이지 않도록 명시합니다.
            if not retrieved:
                result["explanation"] = "선택된 해결 경로는 **" + selected_route + "**입니다. 현재 검색된 참고자료에서 이 세부 유형의 구체적인 요건을 확인하지 못했습니다. 아래 절차는 담당 기관에 대상 여부와 제출 방법을 확인하기 위한 일반 안내이며, 구체적인 요건·서류는 관할 납세자보호담당관에게 확인해야 합니다."
                result["institution"] = result.get("institution") or fallback["institution"]
                result["cautions"] = list(dict.fromkeys(result["cautions"] + ["선택된 세부 유형과 직접 일치하는 참고자료가 검색되지 않았습니다. 아래 요건·서류를 확정 정보로 간주하지 말고 담당 기관에서 확인하세요."]))
        return result
    except Exception:
        return fallback
