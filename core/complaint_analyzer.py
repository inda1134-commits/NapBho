import json
import re
from typing import Any

def analyze_fallback(text: str) -> dict[str, Any]:
    """API가 없을 때 사용할 보수적인 키워드 기반 분석."""
    t = text or ""
    lower = t.lower()
    tax_types = {
        "소득세": ["소득세", "종합소득"],
        "법인세": ["법인세"],
        "부가가치세": ["부가가치세", "부가세"],
        "상속세": ["상속세"],
        "증여세": ["증여세"],
        "취득세": ["취득세"],
        "재산세": ["재산세"],
        "자동차세": ["자동차세"],
        "지방소득세": ["지방소득세"],
    }
    tax_type = next((name for name, terms in tax_types.items() if any(x in t for x in terms)), None)
    other_tax = tax_type in {"취득세", "재산세", "자동차세", "지방소득세"}
    issues = []
    if any(x in t for x in ["고지서", "세금이 나왔", "부과"]):
        issues.append("과세처분")
    if any(x in t for x in ["근거", "자료를 알려", "설명도 없이", "안 알려"]):
        issues.append("과세근거 안내 부족")
    if any(x in t for x in ["세무조사", "조사 담당", "조사범위"]):
        issues.append("부당한 세무조사 행위")
    if any(x in t for x in ["자료를 제출", "소명자료", "자료 제출 요구"]):
        issues.append("신고 후 자료 제출 요구")
    if any(x in t for x in ["압류", "체납", "독촉", "낼 돈이 없", "납부할 돈이 부족"]):
        issues.append("징수·체납")
    if any(x in t for x in ["불복기간", "기간이 지났", "늦게 알", "기한이 지났"]):
        issues.append("불복기한 경과 주장")
    if any(x in t for x in ["신고를 잘못", "많이 신고", "과다 신고"]):
        issues.append("신고 오류")
    if any(x in t for x in ["신고하지 못", "신고 안 했", "미신고"]):
        issues.append("미신고")
    if not issues:
        issues.append("일반 문의")
    if other_tax:
        agency = "OTHER"
        rationale = f"{tax_type}는 일반적으로 지방자치단체 소관이므로 관할 기관 확인이 필요합니다."
    elif tax_type:
        agency = "NTS"
        rationale = f"{tax_type} 관련 내용으로 국세청 소관 가능성이 있습니다."
    elif any(x in t for x in ["세무서", "국세청", "세무조사", "소득세", "법인세", "부가세", "상속세", "증여세"]):
        agency = "NTS"
        rationale = "국세청 관련 표현이 있어 국세청 소관 가능성이 있습니다."
    else:
        agency = "UNKNOWN"
        rationale = "입력 내용만으로 담당 기관을 확정하기 어렵습니다."
    inquiry_type = "SIMPLE_TAX_QUESTION"
    if any(x in t for x in ["고지서", "부과", "세무조사", "압류", "체납", "권리", "자료를 제출", "불복"]):
        inquiry_type = "TAXPAYER_RIGHTS"
    return {
        "summary": t[:300],
        "possible_agency": agency,
        "agency_rationale": rationale,
        "inquiry_type": inquiry_type,
        "tax_type": tax_type,
        "issue_types": issues,
        "known_facts": {
            "notice_kind": "과세예고" if "과세예고" in t else ("고지" if "고지서" in t else None),
            "notice_date": None,
            "prior_explanation": None,
            "tax_audit_status": "종결" if any(x in t for x in ["조사 끝", "조사 종결", "조사가 끝"]) else ("진행" if "세무조사" in t else None),
            "appeal_status": "기한 경과 주장" if "불복기간" in t or "기간이 지났" in t else None,
            "filing_status": "신고 완료" if "이미 신고" in t or "신고했" in t else None,
            "collection_status": "압류" if "압류" in t else ("체납" if "체납" in t else ("납부 곤란" if "돈이 부족" in t or "낼 돈이 없" in t else None)),
        },
        "missing_facts": [],
        "questions": [],
        "confidence": 0.45
    }

def normalize_analysis(data: dict[str, Any], original: str) -> dict[str, Any]:
    defaults = analyze_fallback(original)
    out = {**defaults, **(data or {})}
    for key in ("issue_types", "missing_facts", "questions"):
        if not isinstance(out.get(key), list):
            out[key] = defaults[key]
    if not isinstance(out.get("known_facts"), dict):
        out["known_facts"] = defaults["known_facts"]
    out["summary"] = str(out.get("summary") or original[:300])
    out["possible_agency"] = str(out.get("possible_agency") or "UNKNOWN").upper()
    if out["possible_agency"] not in {"NTS", "OTHER", "UNKNOWN"}:
        out["possible_agency"] = "UNKNOWN"
    return out
