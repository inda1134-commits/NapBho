from core.remedy_rule_engine import decide
from core.procedure_classifier import classify_stage

def test_out_of_scope_does_not_recommend_nts_routes():
    a = {"possible_agency":"OTHER","issue_types":["과세처분"],"known_facts":{}}
    d = decide(a, classify_stage(a))
    assert d["status"] == "OUT_OF_SCOPE"
    assert not d["primary_routes"]

def test_notice_after_tax_assessment_includes_appeal_review():
    a = {"possible_agency":"NTS","inquiry_type":"TAXPAYER_RIGHTS",
         "issue_types":["과세처분"],"known_facts":{"notice_kind":"고지"}}
    d = decide(a, classify_stage(a))
    assert any("불복" in x for x in d["primary_routes"])

def test_audit_closed_does_not_auto_recommend_preassessment():
    a = {"possible_agency":"NTS","issue_types":["부당한 세무조사 행위"],
         "known_facts":{"tax_audit_status":"종결"}}
    d = decide(a, classify_stage(a))
    assert any("통지 여부" in x for x in d["primary_routes"])
    assert not any("과세전적부심사 등 검토" == x for x in d["primary_routes"])
