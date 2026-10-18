"""초기 접수단계의 5개 핵심 항목 분류 및 세목 유사도 보정."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from typing import Any

# 국세청 소관 세목과 현장에서 자주 쓰는 약칭·오타·유사 표현.
TAXONOMY: dict[str, list[str]] = {
    "소득세": ["소득세", "종합소득세", "개인소득세", "양도소득세", "근로소득세", "사업소득세", "원천세", "원천징수", "근로장려금", "종소세", "소득새", "소득쎄"],
    "법인세": ["법인세", "법인 소득세", "법인새", "법인쎄"],
    "부가가치세": ["부가가치세", "부가세", "부가 가치세", "부가가치새", "부가가치쎄", "부가세금"],
    "상속세": ["상속세", "상속세금", "상속새", "상속쎄"],
    "증여세": ["증여세", "증여세금", "증여새", "증여쎄"],
    "종합부동산세": ["종합부동산세", "종부세", "종합 부동산세", "종합부동산새", "종부새"],
    "개별소비세": ["개별소비세", "개소세", "개별 소비세"],
    "주세": ["주세", "술 세금", "주류세"],
    "인지세": ["인지세", "인지 세금"],
    "증권거래세": ["증권거래세", "증권 거래세", "주식거래세"],
    "교육세": ["교육세"],
    "교통·에너지·환경세": ["교통에너지환경세", "교통·에너지·환경세", "교통세", "에너지환경세"],
    "농어촌특별세": ["농어촌특별세", "농특세", "농어촌 특별세"],
    "국제조세": ["국제조세", "이전가격", "국외소득 과세", "국제거래 세금"],
    "기타 국세": ["국세", "세무서 세금", "국세청 세금"],
}

STAGES = ["사업자등록", "신고", "세무조사", "과세", "불복", "체납", "민원", "세법상담", "기타", "미확인"]
ACTIONS = ["안내", "자료제출 요구", "소명 요구", "통지", "과세예고통지", "고지", "독촉", "압류·추심", "신고 처리·환급 지연", "세무조사 착수·진행", "불복 결정", "민원 회신", "기타", "미확인"]
PURPOSES = ["과세 근거·자료 확인", "처분 취소·변경", "세액 감액·환급", "신고·등록 처리", "납부기한 연장·징수 유예", "압류 해제", "조사 절차 개선·중단", "불복·권리구제 방법 확인", "담당기관 확인·이관", "설명·사과·답변 요구", "단순 세법 문의", "기타", "미확인"]

OTHER_AGENCY_TERMS = {
    "지방자치단체": ["취득세", "재산세", "자동차세", "주민세", "지방소득세", "등록면허세", "구청", "시청", "군청"],
    "관세청": ["관세", "수입 통관", "관세청", "세관"],
    "근로복지공단": ["산재보험", "고용보험료"],
    "국민연금공단": ["국민연금 보험료"],
    "건강보험공단": ["건강보험료", "장기요양보험료"],
}


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[\s·ㆍ.,!?:;()\[\]{}\-_]", "", s)
    return s


def match_tax_type(text: str, llm_tax_type: str | None = None) -> dict[str, Any]:
    """원문과 LLM 후보를 함께 비교. 확신이 낮으면 억지로 세목을 확정하지 않는다."""
    candidates: list[tuple[float, str, str]] = []
    source = (text or "") + " " + (llm_tax_type or "")
    norm_source = _norm(source)
    for canonical, aliases in TAXONOMY.items():
        for alias in [canonical, *aliases]:
            na = _norm(alias)
            if not na:
                continue
            if na in norm_source:
                # 긴 표현 및 명시적 일치를 우선한다.
                score = 0.99 + min(len(na), 20) / 1000
                candidates.append((score, canonical, alias))
            else:
                # 원문을 토큰처럼 나누어 오타 유사도 확인
                words = re.findall(r"[가-힣A-Za-z0-9]{2,}", source)
                for word in words:
                    nw = _norm(word)
                    if len(nw) >= 2:
                        ratio = SequenceMatcher(None, nw, na).ratio()
                        if ratio >= 0.72:
                            candidates.append((ratio, canonical, alias))
    if not candidates:
        return {"tax_type": None, "tax_type_candidate": None, "tax_type_similarity": 0.0, "tax_type_match_reason": "국세 세목 사전에서 유사한 표현을 찾지 못했습니다."}
    candidates.sort(key=lambda x: (x[0], len(_norm(x[2]))), reverse=True)
    score, canonical, alias = candidates[0]
    # 약칭/오타 매칭은 검토 대상으로 표시. 직접 일치가 아니면 점수 보정.
    similarity = min(score, 1.0)
    if similarity >= 0.99:
        reason = f"입력 문구에서 '{alias}'와 일치하는 표현을 찾아 '{canonical}'로 분류했습니다."
        result = canonical
    elif similarity >= 0.80:
        reason = f"입력 표현과 '{alias}'의 문자열 유사도가 높아 '{canonical}' 후보로 제시합니다. 사용자 확인이 필요합니다."
        result = canonical
    else:
        reason = f"'{alias}'와 유사한 표현이 있으나 확신도가 낮아 세목을 확정하지 않았습니다."
        result = None
    return {"tax_type": result, "tax_type_candidate": canonical, "tax_type_similarity": round(similarity, 3), "tax_type_match_reason": reason}


def classify_stage_from_text(text: str) -> str:
    t = text or ""
    patterns = [
        ("사업자등록", ["사업자등록", "사업자 등록", "등록 신청", "사업자등록 신청", "사업자등록신청", "사업자등록 휴업", "사업자등록폐업", "사업자 휴업", "사업자 폐업", "휴업신고", "폐업신고", "휴업 신고", "폐업 신고"]),
        ("불복", ["불복", "이의신청", "심사청구", "심판청구", "행정소송"]),
        ("체납", ["체납", "압류", "독촉", "징수유예", "납부할 돈이 없", "납부하기 어렵"]),
        ("과세", ["과세예고", "과세 예정", "과세할 예정", "고지서", "납부고지", "세금이 부과", "고지 받"]),
        ("세무조사", ["세무조사", "조사팀", "조사 착수", "조사 종결"]),
        ("신고", ["신고", "경정청구", "기한후신고", "환급신고"]),
        ("민원", ["민원", "불만", "답변을 안", "담당자가", "권리보호"]),
        ("세법상담", ["무엇인가요", "어떻게 계산", "세율", "공제", "세법 문의"]),
    ]
    for stage, terms in patterns:
        if any(term in t for term in terms):
            return stage
    return "미확인"


def classify_action_from_text(text: str) -> str:
    t = text or ""
    patterns = [
        ("과세예고통지", ["과세예고통지", "과세예고"]),
        ("자료제출 요구", ["자료 제출", "자료제출", "증빙 제출", "자료를 내라"]),
        ("소명 요구", ["소명", "해명하", "설명하라"]),
        ("압류·추심", ["압류", "추심"]),
        ("독촉", ["독촉장", "독촉"]),
        ("고지", ["고지서", "고지했다", "세금을 부과", "납부고지"]),
        ("통지", ["통지", "통보", "문자를 받", "공문을 받"]),
        ("세무조사 착수·진행", ["세무조사", "조사 착수", "조사팀"]),
        ("신고 처리·환급 지연", ["환급이 늦", "환급 지연", "신고 처리가 늦"]),
        ("안내", ["안내", "설명 없이", "알려주지", "안 알려"]),
        ("민원 회신", ["민원 답변", "회신", "답변을 받"]),
    ]
    for action, terms in patterns:
        if any(term in t for term in terms):
            return action
    return "미확인"


def classify_purpose_from_text(text: str) -> str:
    t = text or ""
    patterns = [
        ("과세 근거·자료 확인", ["과세자료", "과세 근거", "근거를 알려", "왜 부과", "어떤 자료"]),
        ("처분 취소·변경", ["취소", "철회", "부과를 없", "잘못된 처분"]),
        ("세액 감액·환급", ["세금을 줄", "감액", "환급", "돌려받", "과다 납부"]),
        ("납부기한 연장·징수 유예", ["납부기한", "징수유예", "분납", "납부할 돈이 부족", "돈이 없어"]),
        ("압류 해제", ["압류 해제", "압류를 풀", "압류 취소"]),
        ("조사 절차 개선·중단", ["조사를 중단", "조사범위", "조사 절차", "세무조사 부당"]),
        ("불복·권리구제 방법 확인", ["권리구제", "불복 방법", "이의신청", "어떻게 대응", "어디에 신청"]),
        ("담당기관 확인·이관", ["어느 기관", "담당기관", "소관기관", "기관을 잘못"]),
        ("설명·사과·답변 요구", ["설명해", "답변해", "사과", "이유를 알려", "납득할 수 있게"]),
        ("단순 세법 문의", ["세율", "공제", "계산 방법", "세금이 얼마", "세법 문의"]),
    ]
    for purpose, terms in patterns:
        if any(term in t for term in terms):
            return purpose
    return "미확인"


def _final_action_agency(text: str) -> tuple[str | None, str | None, str | None]:
    """문장 끝의 목적/최종 행위를 우선해 실제 처리기관을 판단한다.

    '시청에 제출할 국세 납세증명 발급'에서 시청은 제출처이고,
    증명 발급 행위의 담당기관은 국세청이므로 제출처 단어만으로 OTHER로 분류하지 않는다.
    """
    t = _norm(text)
    nts_action_patterns = [
        (r"국세납세증명|납세증명서|납세증명발급|국세완납증명", "국세청", "NTS"),
        (r"사업자등록증명|소득금액증명|부가가치세과세표준증명|표준재무제표증명", "국세청", "NTS"),
        (r"국세환급|종합소득세신고|부가가치세신고|법인세신고|원천징수영수증", "국세청", "NTS"),
    ]
    for pattern, name, code in nts_action_patterns:
        if re.search(pattern, t):
            return code, name, "최종 행위가 국세 증명 발급 또는 국세 신고·처리이므로 국세청 소관으로 판단했습니다."
    # 지방세 자체의 부과·납부·증명 등 최종 행위가 명시된 경우에만 지방자치단체로 분류한다.
    local_tax_actions = ["취득세", "재산세", "자동차세", "주민세", "지방소득세", "등록면허세"]
    if any(_norm(term) in t for term in local_tax_actions):
        return "OTHER", "지방자치단체(시·군·구 등)", "최종 처리 대상이 지방세이므로 지방자치단체 소관으로 판단했습니다."
    return None, None, None



def recommend_nts_contact(text: str, stage: str | None = None, action: str | None = None, purpose: str | None = None) -> dict[str, str]:
    """국세청 소관으로 판별된 사안의 업무 성격별 우선 문의처를 정한다."""
    raw = text or ""
    t = _norm(raw)
    stage = stage or classify_stage_from_text(raw)
    action = action or classify_action_from_text(raw)
    purpose = purpose or classify_purpose_from_text(raw)

    rights_terms = ("권리보호", "권리침해", "위법부당행위", "부당한세무조사", "조사절차개선", "권리보호요청")
    if any(_norm(term) in t for term in rights_terms) or "권리보호" in purpose:
        return {"recommended_contact": "관할 세무서 또는 지방국세청 납세자보호담당관", "contact_reason": "국세 행정상 권리보호 사안은 납세자보호담당관이 우선 문의처입니다."}
    if stage == "세무조사" or action == "세무조사 착수·진행" or any(_norm(x) in t for x in ("조사관서", "조사팀", "세무조사")):
        return {"recommended_contact": "해당 세무조사를 수행하는 조사관서(담당 조사팀)", "contact_reason": "조사 진행·자료 요구 등 조사 관련 사항은 해당 조사관서가 우선 문의처입니다."}
    if stage == "사업자등록" or any(_norm(x) in t for x in ("사업자등록", "사업자등록증명", "사업자등록신청")):
        return {"recommended_contact": "관할 세무서 민원봉사실 또는 홈택스", "contact_reason": "사업자등록 신청·변경·증명은 민원봉사실 또는 홈택스 경로를 우선 안내합니다."}
    if stage == "민원" or any(_norm(x) in t for x in ("민원", "민원회신", "증명발급", "납세증명", "소득금액증명")):
        return {"recommended_contact": "관할 세무서 민원봉사실 또는 홈택스", "contact_reason": "증명 발급과 일반 민원 처리는 민원봉사실 또는 홈택스를 우선 안내합니다."}
    if action in ("고지", "통지", "과세예고통지", "독촉", "압류·추심", "자료제출 요구", "소명 요구"):
        return {"recommended_contact": "해당 안내·통지·처분 또는 행위를 한 관서·담당 부서", "contact_reason": "이미 이루어진 통지·처분·요구는 해당 문서 발신 관서 또는 실제 행위를 한 부서가 우선 문의처입니다."}
    return {"recommended_contact": "국세상담센터 또는 해당 안내·행위를 한 관서", "contact_reason": "그 밖의 국세 문의는 국세상담센터에 문의하고, 특정 통지·행위가 있다면 해당 관서에도 확인합니다."}

def classify_intake(text: str, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = analysis or {}
    tax_match = match_tax_type(text, analysis.get("tax_type"))
    agency = analysis.get("possible_agency", "UNKNOWN")
    agency_name = "국세청" if agency == "NTS" else ("확인 필요" if agency == "UNKNOWN" else "다른 행정기관(확인 필요)")
    # 기관명(예: 시청)이 단순 제출처로 등장할 수 있으므로, 최종 행위/처리 대상을 먼저 판별한다.
    final_agency, final_agency_name, final_rationale = _final_action_agency(text or "")
    if final_agency:
        agency, agency_name = final_agency, final_agency_name
    else:
        for name, terms in OTHER_AGENCY_TERMS.items():
            if any(term in (text or "") for term in terms):
                if name == "지방자치단체":
                    agency, agency_name = "OTHER", "지방자치단체(시·군·구 등)"
                elif name == "관세청":
                    agency, agency_name = "OTHER", name
                break
    if agency == "UNKNOWN" and any(x in (text or "") for x in ["세무서", "국세청", "세무조사"]):
        agency, agency_name = "NTS", "국세청"
    if tax_match["tax_type"] and tax_match["tax_type"] != "기타 국세" and agency != "OTHER":
        agency, agency_name = "NTS", "국세청"
    stage = classify_stage_from_text(text)
    action = classify_action_from_text(text)
    purpose = classify_purpose_from_text(text)
    contact = recommend_nts_contact(text, stage, action, purpose) if agency == "NTS" else {}
    return {
        "responsible_agency": agency_name,
        "possible_agency": agency,
        **({"agency_rationale": final_rationale} if final_rationale else {}),
        **tax_match,
        "tax_stage": stage,
        "administrative_action": action,
        "desired_outcome": purpose,
        **contact,
    }
