from core.question_generator import required_questions


def test_questions_are_asked_one_at_a_time_and_skip_answered_question():
    analysis = {
        "possible_agency": "NTS",
        "tax_type": "소득세",
        "issue_types": ["과세처분"],
        "known_facts": {"notice_kind": "고지", "notice_date": None, "prior_explanation": None},
    }
    questions = required_questions(analysis)
    assert len(questions) == 1
    answers = {questions[0]: "2026-10-01경 받았습니다."}
    next_questions = required_questions(analysis, answers)
    assert len(next_questions) == 1
    assert next_questions[0] != questions[0]


def test_no_questions_when_required_facts_are_known():
    analysis = {
        "possible_agency": "NTS",
        "tax_type": "소득세",
        "issue_types": ["과세처분"],
        "known_facts": {"notice_kind": "고지", "deadline_window": "60일 내", "prior_explanation": "없음", "appeal_status": "미진행"},
    }
    assert required_questions(analysis) == []
