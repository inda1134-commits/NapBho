def required_question_specs(analysis: dict, user_answers: dict | None = None) -> list[dict]:
    """해결 경로 판단에 필요한 미확인 사실만 우선순위대로 한 번에 하나씩 반환."""
    answers = user_answers or {}
    agency = analysis.get("possible_agency", "UNKNOWN")
    facts = analysis.get("known_facts") or {}
    issues = analysis.get("issue_types") or []
    candidates = []
    # 소관기관 확인은 최초 질문으로 묻지 않습니다. 문제 상황·문서·처분 단계와
    # 필요한 사실을 먼저 파악한 뒤, 최종 해결 경로를 정할 때 함께 판단합니다.
    if analysis.get("tax_type") is None and agency != "OTHER":
        candidates.append({"key":"세목","question":"어떤 세금에 관한 문제인가요?","kind":"select",
          "options":["소득세","법인세","부가가치세","상속세","증여세","종합부동산세","기타 국세","잘 모르겠음"],
          "example":"예: 종합소득세 고지서에 관한 문제"})
    # 기한 검토는 정확한 날짜를 받지 않고 기간 범주만 확인합니다.
    stage_text = str(analysis.get("tax_stage", "")) + " " + str(analysis.get("administrative_action", "")) + " " + str(issues)
    deadline_relevant = any(term in stage_text for term in ("세무조사", "과세예고", "과세처분", "고지", "불복", "권리보호", "권리침해")) or facts.get("notice_kind")
    if deadline_relevant and not facts.get("deadline_window"):
        candidates.append({"key":"기한 관련 기간","question":"관련 통지나 처분을 받은 뒤 어느 정도의 기간이 지났나요? 정확한 날짜 대신 가장 가까운 범주를 선택해 주세요.","kind":"select",
          "options":["30일 내", "60일 내", "90일 내", "잘 모르겠음"],
          "example":"과세예고·불복·권리보호 절차의 기한 검토용 범주입니다. 이 선택만으로 법정기한 내·외를 확정하지 않습니다."})
    if any(x in str(issues) for x in ["과세처분", "과세근거 안내 부족"]) or facts.get("notice_kind"):
        if facts.get("prior_explanation") is None:
            candidates.append({"key":"사전 설명","question":"고지서가 오기 전에 세무서에서 설명을 하거나 자료 제출을 요청했나요?","kind":"select",
              "options":["예, 설명 또는 자료 요청이 있었음","아니요, 없었음","기억나지 않음"],
              "example":"예: 고지서 전에 소명자료 제출 안내를 받았습니다."})
    if "신고 후 자료 제출 요구" in issues and not facts.get("notice_kind"):
        candidates.append({"key":"받은 문서","question":"받으신 문서는 어떤 종류인가요?","kind":"select",
          "options":["자료 제출 요청","과세예고통지","세금 고지서","독촉·압류 관련 문서","기타 문서","잘 모르겠음"],
          "example":"예: 세무서에서 소명자료 제출 안내문을 받았습니다."})
    if "부당한 세무조사 행위" in issues and not facts.get("tax_audit_status"):
        candidates.append({"key":"세무조사 상태","question":"세무조사는 현재 어떤 상태인가요?","kind":"select",
          "options":["아직 시작하지 않음","진행 중","종결됨","잘 모르겠음"],
          "example":"예: 조사 담당자가 자료를 요청해 현재 조사 중입니다."})

    # 2단계 사실관계 보완도 선택 목록이 아니라 자연어 대화로 한 항목씩 확인합니다.
    # 사건 유형과 기존 답변을 바탕으로 해결 경로에 영향을 주는 사실만 묻습니다.
    if agency != "OTHER" and any(x in str(issues) for x in ["과세처분", "과세근거 안내 부족", "신고 후 자료 제출 요구"]) and not facts.get("notice_kind"):
        candidates.append({"key":"받은 문서","question":"세무서에서 받은 문서나 안내는 어떤 내용이었나요? 문서 제목을 모르시면 내용을 설명해 주세요.","kind":"text",
          "example":"예: 세금 고지서가 왔습니다 / 자료 제출 안내를 받았습니다 / 아직 문서는 받지 않았습니다."})
    if agency != "OTHER" and not facts.get("appeal_status") and any(x in str(issues) for x in ["과세처분", "불복", "과세근거 안내 부족"]):
        candidates.append({"key":"불복 진행 상태","question":"이 문제와 관련해 이의신청·심사청구·심판청구 같은 불복 절차를 이미 진행하셨나요? 진행하셨다면 현재 상태도 알려주세요.","kind":"text",
          "example":"예: 아직 신청하지 않았습니다 / 심판청구를 했고 결과를 기다리고 있습니다 / 신청 기한이 지난 것 같습니다."})
    if agency != "OTHER" and not facts.get("collection_status") and any(x in str(issues) for x in ["징수", "체납", "압류", "납부 곤란"]):
        candidates.append({"key":"징수 상태","question":"현재 납부나 징수는 어떤 상황인가요? 납부했는지, 납부 기한이 남았는지, 체납·압류가 있는지 알려주세요.","kind":"text",
          "example":"예: 아직 납부 전이고 기한이 다음 달입니다 / 체납으로 계좌 압류 통지를 받았습니다 / 한 번에 납부하기 어렵습니다."})
    if agency != "OTHER" and not facts.get("tax_audit_status") and any(x in str(issues) for x in ["세무조사", "부당한 세무조사 행위"]):
        candidates.append({"key":"세무조사 상태","question":"세무조사는 현재 어느 단계인가요? 시작 전인지, 진행 중인지, 종결되었는지와 최근 연락 내용을 알려주세요.","kind":"text",
          "example":"예: 조사 통지를 받았고 다음 주 시작 예정입니다 / 현재 조사 중입니다 / 조사가 끝났습니다."})

    # 자동 분류만으로 해결 경로가 분명하지 않으면, 구체적 상황과 원하는 결과를 대화로 확인합니다.
    if agency != "OTHER" and not facts.get("problem_details") and not any(x not in ("일반 문의",) for x in issues):
        candidates.append({"key":"문제 상황","question":"현재 겪고 계신 문제를 조금 더 구체적으로 설명해 주시겠어요?","kind":"text",
          "example":"예: 신고한 금액과 다른 금액으로 고지되었는데, 어떤 자료를 근거로 계산했는지 설명을 듣지 못했습니다."})
    return [item for item in candidates if item["question"] not in answers][:1]


def required_questions(analysis: dict, user_answers: dict | None = None) -> list[str]:
    """기존 호출부 및 테스트와의 호환성을 위한 질문 문구 목록."""
    return [item["question"] for item in required_question_specs(analysis, user_answers)]
