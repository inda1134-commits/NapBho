from core.solution_planner import classify_solution_category, build_solution_plan


def test_simple_tax_question_routes_to_simple_info():
    analysis = {"desired_outcome": "단순 세법 문의", "inquiry_type": "SIMPLE_TAX_QUESTION", "issue_types": []}
    assert classify_solution_category("국세상담센터 등 공식 세법 상담", analysis) == "simple_info"


def test_submission_route_is_classified_as_submission():
    analysis = {"desired_outcome": "신고·등록 처리", "issue_types": ["신고 오류"]}
    assert classify_solution_category("경정청구 등 신고 정정 절차 검토", analysis) == "submission"


def test_appeal_route_is_classified_as_remedy_procedure():
    analysis = {"desired_outcome": "불복·권리구제 방법 확인", "issue_types": ["과세처분"]}
    assert classify_solution_category("과세처분 불복절차 검토", analysis) == "remedy_procedure"


def test_rights_protection_route_is_classified_as_rights_protection():
    analysis = {"desired_outcome": "조사 절차 개선·중단", "issue_types": ["부당한 세무조사 행위"]}
    assert classify_solution_category("세무조사 관련 권리보호 절차 검토", analysis) == "rights_protection"


def test_plan_uses_fallback_without_llm():
    plan = build_solution_plan(
        {"known_facts": {}, "issue_types": [], "desired_outcome": "단순 세법 문의"},
        {"primary_routes": ["국세상담센터 등 공식 세법 상담"]},
        {"message": "기한 확인 필요"},
        "국세상담센터 등 공식 세법 상담",
    )
    assert plan["category"] == "simple_info"
    assert plan["documents"] == []
    assert plan["steps"] == []
    assert plan["institution"] == "국세종합상담센터"
    assert "126" not in plan["explanation"]


def test_llm_uses_selected_route_and_can_choose_category():
    class FakeLLM:
        available = True
        captured = ""

        def generate_json(self, system, prompt):
            self.captured = prompt
            return {
                "category": "rights_protection",
                "title": "권리보호 안내",
                "explanation": "권리보호 대상 여부를 확인하세요.",
                "steps": ["담당관에게 문의"],
                "documents": ["관련 통지서"],
                "institution": "납세자보호담당관",
                "cautions": [],
            }

    fake = FakeLLM()
    plan = build_solution_plan(
        {"known_facts": {"notice_kind": "자료요구"}, "issue_types": ["절차상 권리침해"]},
        {"primary_routes": ["납세자보호담당관에게 권리보호요청 대상 여부 상담"]},
        {"message": "기한 확인 필요"},
        "납세자보호담당관에게 권리보호요청 대상 여부 상담",
        fake,
    )
    assert plan["category"] == "rights_protection"
    assert "납세자보호담당관에게 권리보호요청 대상 여부 상담" in fake.captured
    assert "notice_kind" in fake.captured


def test_llm_selects_one_best_solution_from_candidates():
    from core.solution_planner import select_best_solution

    class FakeLLM:
        available = True
        def generate_json(self, system, prompt):
            assert "JSON만 반환" in system
            assert "세무조사" in prompt
            return {"solution": "권리보호(범위확대)", "reason": "확인된 조사범위 확대 문제와 직접 관련됩니다."}

    result = select_best_solution(
        ["권리보호(범위확대)", "참관", "조력"],
        {"summary": "조사 범위가 확대됨", "confirmed_facts": {"answers": {"조사범위": "확대"}}},
        {"status": "OK"}, {"stage": "세무조사"}, {"message": "기한 확인 필요"}, FakeLLM()
    )
    assert result["solution"] == "권리보호(범위확대)"
    assert "조사범위 확대" in result["reason"]


def test_solution_selector_falls_back_to_first_candidate_without_llm():
    from core.solution_planner import select_best_solution
    result = select_best_solution(["기한후신고", "경정청구"], {}, {}, {"stage": "신고"}, {}, None)
    assert result["solution"] == "기한후신고"


def test_simple_tax_question_uses_llm_for_brief_explanation_and_center_guidance():
    class FakeLLM:
        available = True
        called = False
        def generate_json(self, system, prompt):
            self.called = True
            assert "2~4문장" in system
            assert "세법자료.pdf" in prompt
            return {"category": "simple_info", "title": "부가가치세란?", "explanation": "부가가치세는 재화나 용역의 공급 등에 부과되는 세금입니다. 구체적인 적용 여부는 국세종합상담센터에서 확인하세요."}

    fake = FakeLLM()
    plan = build_solution_plan(
        {"summary": "부가가치세가 뭐야? 설명해줘", "tax_type": "부가가치세", "inquiry_type": "SIMPLE_TAX_QUESTION", "issue_types": [], "desired_outcome": "단순 세법 문의"},
        {}, {}, "단순 세법 문의", fake,
        [{"filename": "세법자료.pdf", "page": 2, "text": "상세 참고 내용"}],
    )
    assert fake.called
    assert plan["category"] == "simple_info"
    assert "부가가치세는" in plan["explanation"]
    assert plan["steps"] == [] and plan["documents"] == []
    assert plan["institution"] == "국세종합상담센터"


def test_tax_term_with_unfair_or_disallowance_word_stays_simple_info():
    analysis = {
        "summary": "세법에서 부당행위계산부인이 뭐야?",
        "desired_outcome": "단순 세법 문의",
        "inquiry_type": "SIMPLE_TAX_QUESTION",
        "issue_types": ["부당한 세무조사 행위"],  # 초기 LLM의 오분류가 있어도 단순 질문 의도를 우선
    }
    assert classify_solution_category("권리보호 안내", analysis) == "simple_info"


def test_business_registration_inquiry_is_simple_guidance_with_hometax_contact():
    analysis = {"summary": "사업자등록 신청 방법이 궁금합니다", "desired_outcome": "신고·등록 처리", "issue_types": ["등록 신청"]}
    assert classify_solution_category("사업자등록 신청 절차", analysis) == "simple_info"
    plan = build_solution_plan(analysis, {}, {}, "사업자등록 신청 절차")
    assert plan["category"] == "simple_info"
    assert plan["institution"] == "관할 세무서 민원봉사실 또는 홈택스"
    assert plan["steps"] == [] and plan["documents"] == []


def test_business_registration_flag_forces_simple_info_even_if_summary_omits_keyword():
    analysis = {"summary": "신청 절차 문의", "business_registration_inquiry": True,
                "desired_outcome": "신고·등록 처리", "issue_types": ["등록 신청"]}
    assert classify_solution_category("등록 신청", analysis) == "simple_info"
    plan = build_solution_plan(analysis, {}, {}, "사업자등록 신청 방법 안내")
    assert plan["category"] == "simple_info"
    assert plan["steps"] == []
    assert plan["documents"] == []
    assert "홈택스" in plan["institution"]


def test_business_registration_processing_delay_is_not_classified_as_simple_info():
    analysis = {
        "summary": "사업자등록 신청했는데 처리가 안 되고 있어요",
        "business_registration_inquiry": True,
        "business_registration_simple_inquiry": False,
        "business_registration_processing_problem": True,
        "desired_outcome": "신고·등록 처리",
        "issue_types": ["등록 처리 지연"],
    }
    assert classify_solution_category("사업자등록 처리 확인", analysis) != "simple_info"


def test_appeal_routes_include_detailed_eligibility_procedure_processing_and_legal_effects():
    from core.solution_planner import build_solution_plan
    for route in ("과세전적부", "이의신청", "심사청구", "심판청구"):
        plan = build_solution_plan(
            {"summary": "과세처분에 이의가 있음", "issue_types": ["과세처분"], "desired_outcome": "불복·권리구제 방법 확인"},
            {"status": "OK", "primary_routes": [route]},
            {"message": "30일·60일·90일 선택은 법정기한을 확정하지 않습니다."},
            route,
            llm=None,
            retrieved=[{"filename": "국세기본법_참고자료.pdf", "page": 4, "text": "절차 참고 근거"}],
        )
        assert plan["category"] == "remedy_procedure"
        assert "신청요건" in plan["explanation"]
        assert "처리절차" in plan["explanation"]
        assert "법률 효과" in plan["explanation"]
        assert any("국세기본법_참고자료.pdf" in str(x) for x in [plan["explanation"]])
        assert plan["steps"]
        assert plan["documents"]
        assert plan["institution"]


def test_appeal_plan_marks_missing_vector_evidence_as_unconfirmed():
    from core.solution_planner import build_solution_plan
    plan = build_solution_plan(
        {"summary": "과세처분에 이의가 있음", "issue_types": ["과세처분"]},
        {"status": "OK"}, {"message": "기한 범주 확인 필요"}, "심판청구", None, []
    )
    assert "지정된 벡터 DB에서 이 절차의 직접 근거가 검색되지 않았습니다" in plan["explanation"]
    assert any("직접 근거가 검색되지 않아" in x for x in plan["cautions"])
