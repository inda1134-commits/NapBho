def classify_stage(analysis: dict, answers: dict | None = None) -> dict:
    answers = answers or {}
    facts = dict(analysis.get("known_facts") or {})
    facts.update({k:v for k,v in answers.items() if v not in (None, "")})
    notice_kind = facts.get("notice_kind")
    audit = facts.get("tax_audit_status")
    appeal = facts.get("appeal_status")
    collection = facts.get("collection_status")
    if appeal in ("진행", "기한 경과 주장"):
        stage = "불복 진행/기한 확인"
    elif collection in ("압류", "체납", "납부 곤란"):
        stage = "징수·체납"
    elif notice_kind in ("과세예고", "고지"):
        stage = "과세"
    elif audit == "종결":
        stage = "세무조사 종결(후속 통지 확인 필요)"
    elif audit in ("착수", "진행"):
        stage = "세무조사 진행"
    elif facts.get("filing_status") == "신고 완료":
        stage = "신고 후 확인"
    else:
        stage = "단계 미확인"
    return {"stage": stage, "facts": facts, "last_disposition": facts.get("last_disposition")}
