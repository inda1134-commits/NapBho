import unittest
from core.intake_classifier import match_tax_type, classify_intake
from core.jurisdiction_classifier import classify

class IntakeClassifierTests(unittest.TestCase):
    def test_tax_type_typo_matches_vat(self):
        result = match_tax_type("부가가치새 고지서가 왔습니다")
        self.assertEqual(result["tax_type"], "부가가치세")
        self.assertGreaterEqual(result["tax_type_similarity"], 0.80)

    def test_tax_type_abbreviation_matches_corporate_tax(self):
        result = match_tax_type("법인쎄가 많이 나왔어요")
        self.assertEqual(result["tax_type"], "법인세")

    def test_local_tax_not_misclassified_as_national_tax(self):
        result = classify_intake("구청에서 취득세 고지서를 보냈습니다", {"possible_agency": "OTHER", "tax_type": "취득세"})
        self.assertEqual(result["possible_agency"], "OTHER")
        self.assertIn("지방자치단체", result["responsible_agency"])

    def test_destination_city_hall_does_not_override_national_tax_certificate_action(self):
        result = classify_intake("시청에 제출할 국세 납세증명 발급")
        self.assertEqual(result["possible_agency"], "NTS")
        self.assertEqual(result["responsible_agency"], "국세청")

    def test_local_tax_action_remains_local_government(self):
        result = classify_intake("시청에 재산세 납부 확인을 요청합니다", {"possible_agency": "UNKNOWN"})
        self.assertEqual(result["possible_agency"], "OTHER")
        self.assertIn("지방자치단체", result["responsible_agency"])

    def test_five_fields_exist(self):
        result = classify("세무서에서 과세자료를 설명하지 않고 고지서를 보냈습니다.")
        for key in ("responsible_agency", "tax_type", "tax_stage", "administrative_action", "desired_outcome"):
            self.assertIn(key, result)

if __name__ == "__main__":
    unittest.main()

class ContactRecommendationTests(unittest.TestCase):
    def test_rights_protection_goes_to_taxpayer_protection_officer(self):
        result = classify_intake("세무조사 중 위법부당행위에 대한 권리보호 요청", {"possible_agency": "NTS"})
        self.assertIn("납세자보호담당관", result["recommended_contact"])

    def test_business_registration_goes_to_civil_service_or_hometax(self):
        result = classify_intake("사업자등록 신청 방법을 알려주세요", {"possible_agency": "NTS"})
        self.assertTrue("민원봉사실" in result["recommended_contact"] or "홈택스" in result["recommended_contact"])

    def test_audit_goes_to_investigating_office(self):
        result = classify_intake("세무조사 자료제출 요구에 대한 문의", {"possible_agency": "NTS"})
        self.assertIn("조사관서", result["recommended_contact"])

    def test_notice_or_action_goes_to_issuing_office(self):
        result = classify_intake("세무서에서 고지서를 받았는데 산출 근거를 모르겠습니다", {"possible_agency": "NTS"})
        self.assertIn("행위를 한 관서", result["recommended_contact"])

    def test_general_tax_question_goes_to_comprehensive_counseling_center(self):
        result = classify_intake("소득세 공제 기준이 궁금합니다", {"possible_agency": "NTS"})
        self.assertIn("국세상담센터", result["recommended_contact"])

class SimpleTaxConceptQuestionTests(unittest.TestCase):
    def test_unfair_tax_term_definition_is_simple_info_not_rights_protection(self):
        result = classify("세법에서 부당행위계산부인이 뭐야?")
        self.assertEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")
        self.assertEqual(result["desired_outcome"], "단순 세법 문의")
        self.assertEqual(result["issue_types"], [])
        self.assertEqual(result["recommended_contact"], "국세종합상담센터")

    def test_disallowance_concept_explanation_is_simple_info(self):
        result = classify("손금불산입이 무슨 뜻인지 설명해줘")
        self.assertEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")
        self.assertEqual(result["desired_outcome"], "단순 세법 문의")

    def test_actual_unfair_tax_audit_complaint_is_not_simple_question(self):
        result = classify("세무조사 중 조사관이 부당하게 자료를 과도하게 요구하고 있어 권리보호를 요청하고 싶습니다")
        self.assertNotEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")

class BusinessRegistrationSimpleInquiryTests(unittest.TestCase):

    def test_business_registration_application_overrides_llm_other_agency_result(self):
        class FakeLLM:
            available = True
            def generate_json(self, system, prompt):
                return {
                    "summary": "신청 절차 문의",
                    "possible_agency": "OTHER",
                    "responsible_agency": "지방자치단체",
                    "inquiry_type": "TAXPAYER_RIGHTS",
                    "desired_outcome": "신고·등록 처리",
                    "issue_types": ["등록 신청"],
                    "questions": ["어떤 처분을 받으셨나요?"],
                    "missing_facts": ["기관"],
                }
        result = classify("사업자등록 신청", FakeLLM())
        self.assertEqual(result["possible_agency"], "NTS")
        self.assertEqual(result["responsible_agency"], "국세청")
        self.assertEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")
        self.assertEqual(result["desired_outcome"], "단순 세법 문의")
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["missing_facts"], [])
        self.assertTrue(result["business_registration_inquiry"])

    def test_business_registration_question_is_national_tax_simple_inquiry(self):
        result = classify("사업자등록 신청 방법이 궁금합니다")
        self.assertEqual(result["possible_agency"], "NTS")
        self.assertEqual(result["responsible_agency"], "국세청")
        self.assertEqual(result["tax_stage"], "사업자등록")
        self.assertEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")
        self.assertEqual(result["desired_outcome"], "단순 세법 문의")
        self.assertEqual(result["questions"], [])
        self.assertIn("홈택스", result["recommended_contact"])


def test_business_registration_stage_includes_suspension_and_closure():
    from core.jurisdiction_classifier import classify
    for question in ("사업자등록 신청", "사업자 휴업 신고", "사업자 폐업 신고", "휴업신고 방법", "폐업신고 방법"):
        result = classify(question)
        assert result["possible_agency"] == "NTS", question
        assert result["tax_stage"] == "사업자등록", question
        assert result["inquiry_type"] == "SIMPLE_TAX_QUESTION", question
        assert result["questions"] == [], question

class BusinessRegistrationSubtypeTests(unittest.TestCase):
    def test_business_registration_subtypes_are_distinguished(self):
        cases = {
            "사업자등록 신청 방법을 알려주세요": "신규 사업자등록 신청",
            "사업자 휴업 신고 방법": "휴업 신고",
            "사업자 폐업 신고 방법": "폐업 신고",
            "사업자등록 주소 변경 방법": "사업자등록 정정·변경",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                result = classify(question)
                self.assertEqual(result["business_registration_subtype"], expected)
                self.assertTrue(result["business_registration_simple_inquiry"])
                self.assertEqual(result["tax_stage"], "사업자등록")
                self.assertEqual(result["possible_agency"], "NTS")
                self.assertEqual(result["questions"], [])

    def test_actual_business_registration_processing_problem_is_not_simple_inquiry(self):
        result = classify("사업자등록 신청했는데 처리가 안 되고 있어요")
        self.assertTrue(result["business_registration_inquiry"])
        self.assertTrue(result["business_registration_processing_problem"])
        self.assertFalse(result["business_registration_simple_inquiry"])
        self.assertEqual(result["possible_agency"], "NTS")
        self.assertEqual(result["tax_stage"], "사업자등록")
        self.assertNotEqual(result["inquiry_type"], "SIMPLE_TAX_QUESTION")
        self.assertTrue(result["questions"])
