def build_fallback_answer(analysis: dict, decision: dict, deadline: dict, retrieved: list[dict] | None = None) -> str:
    retrieved = retrieved or []
    lines = []
    lines.append("### 1. 현재 상황")
    lines.append(analysis.get("summary") or "입력하신 내용을 바탕으로 검토했습니다.")
    lines.append("")
    lines.append("### 2. 검토 결과")
    if decision.get("status") == "OUT_OF_SCOPE":
        lines.append("입력 내용은 국세청 소관이 아닐 가능성이 있습니다. 해당 세목의 담당 기관을 먼저 확인하세요.")
    elif decision.get("status") == "NEED_INFO":
        lines.append("담당 기관이 명확하지 않아 국세청 절차를 확정할 수 없습니다.")
    else:
        lines.append(f"현재 파악된 절차 단계: **{decision.get('stage', '미확인')}**")
        lines.append("**우선 검토할 방법**")
        for route in decision.get("primary_routes", []):
            lines.append(f"- {route}")
        if decision.get("secondary_routes"):
            lines.append("\n**함께 확인할 사항**")
            for route in decision["secondary_routes"]:
                lines.append(f"- {route}")
    lines.append("\n### 3. 기한 관련 주의")
    lines.append(deadline.get("message", "신청기한은 공식 규정으로 확인해야 합니다."))
    lines.append("\n### 4. 주의사항")
    for caution in decision.get("cautions", []):
        lines.append(f"- {caution}")
    lines.append("- 이 안내는 초기 규칙에 따른 참고 정보이며, 권리구제 가능성이나 결과를 보장하지 않습니다.")
    lines.append("- 고지서·통지서의 종류와 받은 날짜를 확인하고 관할 세무서 또는 납세자보호담당관에 구체적인 적용 요건을 확인하세요.")
    lines.append("\n### 5. 업로드 문서 검색 결과")
    if retrieved:
        for item in retrieved:
            lines.append(f"- **{item.get('filename')}**, p.{item.get('page')}: {item.get('text','')[:450]}...")
    else:
        lines.append("업로드 문서에서 직접 인용할 수 있는 관련 근거를 찾지 못했습니다. 현행 공식 자료를 확인해야 합니다.")
    return "\n".join(lines)

def generate_answer(analysis, decision, deadline, retrieved, llm=None):
    base = build_fallback_answer(analysis, decision, deadline, retrieved)
    if llm and llm.available and decision.get("status") == "OK":
        try:
            prompt = f"""아래 자료만 사용해 일반 납세자가 이해할 한국어 안내문을 작성하세요.
법률적 결론을 단정하지 말고, 기한은 제공된 내용보다 더 확정적으로 쓰지 마세요.
근거가 없는 조문·URL·기한을 만들지 마세요.
분석 결과: {analysis}
규칙 엔진 결과: {decision}
기한 확인: {deadline}
검색된 PDF 근거: {retrieved}
초안: {base}
구성: 현재 상황 / 검토 결과 / 권장 행동 / 기한 주의 / 근거 / 공식 확인 경로."""
            return llm.generate_text("당신은 납세자 권리 안내문 작성 보조자입니다. 근거와 불확실성을 명확히 표시합니다.", prompt)
        except Exception:
            pass
    return base
