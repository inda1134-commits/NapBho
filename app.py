import os
import streamlit as st
from dotenv import load_dotenv

from services.llm_factory import LLMFactory
from core.jurisdiction_classifier import classify
from core.intake_classifier import TAXONOMY, STAGES, ACTIONS, PURPOSES
from core.question_generator import required_questions, required_question_specs
from core.procedure_classifier import classify_stage
from core.remedy_rule_engine import decide
from core.deadline_checker import check_deadline
from core.answer_generator import generate_answer
from core.validation_engine import validate_result, validate_evidence_for_route
from core.solution_planner import build_solution_plan, select_best_solution
from rag.pdf_loader import extract_pdf_pages
from rag.retriever import chunk_pages, chroma_search


STAGE_SOLUTIONS = {
"사업자등록":["신규 사업자등록 신청 안내","사업자등록 정정·변경 안내","휴업 신고 안내","폐업 신고 안내","대리신청","명의도용방지"], "신고":["기한연장","수정신고","경정청구","기한후신고"],
"세무조사":["권리보호(위법부당행위)","권리보호(범위확대)","권리보호(기간연장)","권리보호(조사중지)","참관","조력","과세자문"],
"과세":["과세전적부","고지유예","조기결정신청","권리보호(미안내)","전자고지","기한연장"], "불복":["이의신청","심사청구","심판청구","행정소송"],
"체납":["권리보호(미해제)","징수유예","압류해제","공매중지","납세담보"],
"권리구제":["권리보호(위법부당행위)","권리보호(고충)","청원"], "민원":["민원증명","정보공개"]}
def choose_stage_solutions(stage_name, analysis, facts, decision):
    text = " ".join([str(analysis.get("summary","")),str(analysis.get("administrative_action","")),str(analysis.get("desired_outcome",""))," ".join(analysis.get("issue_types") or []),str(facts)])
    low=text.lower(); stage=stage_name or analysis.get("tax_stage","")
    if any(x in low for x in ["명의도용","도용된 사업자","내 명의로 사업자"]): return ["명의도용방지","대리신청"]
    if stage == "사업자등록":
        subtype = str(analysis.get("business_registration_subtype", ""))
        if "휴업" in subtype or "휴업" in low: return ["휴업 신고 안내", "관할 세무서 처리 확인"]
        if "폐업" in subtype or "폐업" in low: return ["폐업 신고 안내", "관할 세무서 처리 확인"]
        if "정정" in subtype or "변경" in subtype or "정정" in low or "변경" in low: return ["사업자등록 정정·변경 안내", "관할 세무서 처리 확인"]
        if "신청" in subtype or "등록" in low: return ["신규 사업자등록 신청 안내", "관할 세무서 처리 확인"]
    if stage in ("과세", "과세예고", "고지", "고지 후", "불복", "불복 진행/기한 확인"):
        notice_kind = facts.get("notice_kind") or analysis.get("known_facts", {}).get("notice_kind")
        deadline_window = facts.get("deadline_window") or analysis.get("known_facts", {}).get("deadline_window")
        if notice_kind == "과세예고":
            # 기간 범주는 우선 검토 순서를 보조할 뿐, 법정기한 내·외를 확정하지 않습니다.
            return ["과세전적부", "권리보호(미안내)", "조기결정신청", "고지유예", "기한연장"]
        if notice_kind == "고지" or stage in ("불복", "불복 진행/기한 확인"):
            appeal_routes = ["이의신청", "심사청구", "심판청구", "권리보호(미안내)", "권리보호(고충)"]
            if deadline_window in ("30일 내", "60일 내", "90일 내"):
                return appeal_routes + ["징수유예"]
            return appeal_routes + ["징수유예"]
    if any(x in low for x in ["압류 해제","압류를 풀","압류된 계좌"]): return ["압류해제","징수유예","권리보호(미해제)","공매중지","납세담보"]
    if any(x in low for x in ["공매","매각 예정"]): return ["공매중지","징수유예","권리보호(미해제)","압류해제","납세담보"]
    if any(x in low for x in ["조사범위","범위 확대","조사 범위"]): return ["권리보호(범위확대)","권리보호(위법부당행위)","권리보호(조사중지)","참관","조력","과세자문"]
    if any(x in low for x in ["조사기간 연장","기간 연장","조사 기간"]): return ["권리보호(기간연장)","권리보호(위법부당행위)","참관","조력","과세자문"]
    if any(x in low for x in ["위법","부당","자료를 과도하게","과도한 자료","권리 침해","설명 없이"]):
        return ["권리보호(위법부당행위)","권리보호(범위확대)","권리보호(기간연장)","권리보호(조사중지)","참관","조력","과세자문"] if "조사" in text or stage=="세무조사" else ["권리보호(미안내)","과세전적부","고지유예"]
    if any(x in low for x in ["과다 신고","더 냈","환급","잘못 신고","신고 오류"]): return ["경정청구","수정신고","기한연장","기한후신고"]
    if any(x in low for x in ["신고하지 못","미신고","신고 안 했"]): return ["기한후신고","기한연장","수정신고","경정청구"]
    if any(x in low for x in ["납부하기 어렵","납부 곤란","돈이 부족","납부할 수 없"]): return ["징수유예","기한연장","납세담보","권리보호(미해제)"]
    mapping={"사업자등록":"사업자등록","신고":"신고","신고 후 확인":"신고","세무조사 진행":"세무조사","세무조사":"세무조사","과세예고":"과세","과세예고통지":"과세","과세":"과세","고지 후":"과세","고지":"과세","불복 진행/기한 확인":"불복","불복":"불복","징수·체납":"체납","체납":"체납","민원":"민원","권리구제":"권리구제"}
    if stage in mapping: return STAGE_SOLUTIONS[mapping[stage]]
    if any(x in text for x in ["정보공개","정보 공개"]): return ["정보공개","민원증명"]
    if any(x in text for x in ["권리보호","고충","청원"]): return STAGE_SOLUTIONS["권리구제"]
    routes=decision.get("primary_routes") or []
    if routes and "경정청구" in " ".join(routes): return ["경정청구","수정신고"]
    if routes and "기한후신고" in " ".join(routes): return ["기한후신고","기한연장"]
    return ["권리보호(고충)","청원","민원증명","정보공개"]

load_dotenv()
st.set_page_config(page_title="납세자 권리보호 상담", page_icon="⚖️", layout="wide")
st.divider()
st.markdown("""
<style>
:root { --navy:#073c78; --blue:#0879df; --sky:#eaf6ff; --line:#b9dcff; --ink:#183b65; }
.stApp {background:linear-gradient(180deg,#eaf7ff 0%,#f7fbff 36%,#ffffff 100%);color:var(--ink)}
.block-container {max-width:1800px;padding:1rem 1rem 1.5rem}
.hero {background:linear-gradient(105deg,#e3f5ff 0%,#ffffff 46%,#d8f1ff 100%);border:1px solid #c5e7ff;border-radius:20px;padding:1.1rem 1.5rem;margin-bottom:1rem;box-shadow:0 5px 18px #15558b12;color:var(--navy)}
.hero h1 {color:#0756a6;font-size:2rem;font-weight:850;margin:0 0 .35rem 0;letter-spacing:-.04em}
.hero p {color:#244b75;margin:0;font-size:1rem}
h2,h3 {color:#0756a6;letter-spacing:-.025em}
.section-card {background:linear-gradient(145deg,#fff,#f4faff);border:1px solid #b8ddff;border-radius:15px;padding:1rem 1.1rem;margin:.55rem 0;box-shadow:0 3px 10px #164c7710}
.question-card {border-left:5px solid #0879df;background:linear-gradient(120deg,#eef8ff,#fff)}
.answer-card {background:linear-gradient(145deg,#fffdf8,#fff7e9);border:1px solid #ffcf8a;border-radius:16px;padding:1.2rem 1.3rem;margin-top:.75rem;box-shadow:0 4px 14px #a45c1010}
.pill {display:inline-block;background:#e1f1ff;color:#0756a6;border:1px solid #c5e5ff;border-radius:999px;padding:.25rem .7rem;font-weight:750;font-size:.85rem}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#b8dcff!important;border-radius:15px!important;background:#ffffffd9}
[data-testid="stChatMessage"] {background:white;border:1px solid #d8eaff;border-radius:14px}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#f1f9ff,#fff)}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 {color:#0756a6}
div.stButton > button,div.stFormSubmitButton > button {border-radius:11px;min-height:2.65rem;border:1px solid #acd5ff;background:linear-gradient(100deg,#0879df,#1595ed);color:white;font-weight:750}
div.stButton > button:hover,div.stFormSubmitButton > button:hover {border-color:#0756a6;color:white;filter:brightness(.97)}
[data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input {border-radius:11px;border-color:#b8dcff}
hr {border-color:#d4eaff}
@media (min-width: 1100px) { [data-testid="stHorizontalBlock"] {gap:1rem;} }
</style>
<div class="hero"><h1>🛡️ 납세자 권리 보호 AI</h1><p><b>납세자의 고민을 함께 해결합니다</b>　세금 문제로 어려움을 겪고 계신가요? 상황을 분석하고, 가장 적합한 해결 방법을 찾아 친절하게 안내해 드립니다.</p></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("LLM 설정")
    provider_options = ["openai", "google", "anthropic"]
    env_provider = os.getenv("LLM_PROVIDER", "openai").lower()
    provider = st.selectbox("공급자", provider_options, index=provider_options.index(env_provider) if env_provider in provider_options else 0)
    key_env = {"openai":"OPENAI_API_KEY", "google":"GOOGLE_API_KEY", "anthropic":"ANTHROPIC_API_KEY"}[provider]
    api_key = st.text_input("API 키 (선택)", value=os.getenv(key_env, ""), type="password")
    default_model = {"openai":"gpt-4.1-mini", "google":"gemini-2.5-flash", "anthropic":"claude-3-5-haiku-latest"}[provider]
    model = st.text_input("모델", value=os.getenv("LLM_MODEL", default_model))
    temperature = st.slider("Temperature", 0.0, 1.0, float(os.getenv("LLM_TEMPERATURE", "0.1")), 0.1)
    max_tokens = st.number_input("최대 토큰", 500, 8000, int(os.getenv("LLM_MAX_TOKENS", "2500")), 250)
    use_llm = st.checkbox("LLM 분석/답변 사용", value=bool(api_key))
    st.divider()
    st.markdown("⚠️ **개인정보 안내**")
    st.caption("주민등록번호·계좌번호 등 불필요한 개인정보는 입력하지 마세요. 외부 LLM을 사용하면 입력 일부가 API로 전송될 수 있습니다.")
    st.divider()
    st.divider()
    st.subheader("📚 과세단계별 참고자료 관리")
    st.caption("과세단계별 법령·업무 안내 PDF를 등록하면 해결 방법 판단과 상세 안내 작성 시 검색 근거로 활용합니다.")
    st.file_uploader("참고자료 PDF 업로드", type=["pdf"], accept_multiple_files=True, key="remedy_reference_pdfs")
    vector_collection = st.text_input("컬렉션 이름", value=os.getenv("CHROMA_COLLECTION", "taxpayer_rights_references"))
    vector_path = st.text_input("벡터 DB 저장 폴더", value=os.getenv("CHROMA_PATH", "data/vector_db"))
    embedding_key = os.getenv("OPENAI_API_KEY", "") or (api_key if provider == "openai" else "")
    if st.button("벡터 DB 생성 / 자료 추가", use_container_width=True):
        pdfs = st.session_state.get("remedy_reference_pdfs", [])
        if not pdfs:
            st.warning("먼저 참고자료 PDF를 업로드해 주세요.")
        elif not embedding_key:
            st.error("벡터 임베딩 생성에는 OPENAI_API_KEY가 필요합니다. .env 또는 OpenAI API 키 설정을 확인하세요.")
        else:
            try:
                all_pages = []
                for pdf in pdfs:
                    all_pages.extend(extract_pdf_pages(pdf.getvalue(), pdf.name))
                all_chunks = chunk_pages(all_pages)
                from rag.retriever import index_documents
                count = index_documents(all_chunks, embedding_key, vector_collection, vector_path)
                st.success(f"벡터 DB 저장 완료: {count}개 문서 청크")
                st.session_state["rag_collection"] = vector_collection
                st.session_state["rag_path"] = vector_path
            except Exception as exc:
                st.error(f"벡터 DB 생성에 실패했습니다: {exc}")
    st.caption("저장된 벡터 DB는 다음 상담에서도 같은 저장 폴더와 컬렉션 이름으로 검색할 수 있습니다.")

llm = LLMFactory(provider=provider, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens) if use_llm else None
if llm and not llm.available:
    st.warning("API 키가 없어 규칙 기반 분석으로 실행됩니다.")
    llm = None

for key, default in [("messages", []), ("analysis", None), ("original_complaint", ""), ("last_result", None), ("classification_confirmed", False), ("followup_answers", {}), ("selected_solution", None), ("solution_confirmed", False), ("solution_reason", ""), ("rag_collection", os.getenv("CHROMA_COLLECTION", "taxpayer_rights_references")), ("rag_path", os.getenv("CHROMA_PATH", "data/vector_db"))]:
    if key not in st.session_state:
        st.session_state[key] = default

left_col, right_col = st.columns([2.15, 1], gap="large")
with left_col:
    # st.markdown("### 🧭 납세자 고민 해결 AI")
    # 슬롯은 최종 렌더링 순서를 고정합니다: 진행 → 상담원 질문 → 답변 입력 → 결과 → 새 상담.
    progress_slot = st.container()
    question_slot = st.container()
    input_slot = st.container()
    result_slot = st.container()
    restart_slot = st.container()

    chat_prompt = ("위 질문에 답변해 주세요." if st.session_state.analysis and st.session_state.get("current_followup_question") else ("추가 설명을 입력해 주세요." if st.session_state.analysis else "겪고 계신 세금 문제나 불만사항을 편하게 입력해 주세요."))
    # 최종 해결 안내가 생성된 뒤에는 추가 상담 입력 영역을 표시하지 않습니다.
    if not st.session_state.get("last_result"):
        with input_slot:
            st.markdown("#### ✍️ 상담 하기")
            with st.form("consultation_input", clear_on_submit=True):
                current_spec = None
                current_analysis = st.session_state.get("analysis") or {}
                current_question = st.session_state.get("current_followup_question")
                if current_question:
                    current_spec = next((spec for spec in required_question_specs(current_analysis, st.session_state.get("followup_answers", {})) if spec["question"] == current_question), None)
                if current_spec and current_spec.get("key") == "기한 관련 기간":
                    st.caption("정확한 날짜를 입력하지 말고 해당하는 기간 범주를 선택해 주세요.")
                    complaint = st.selectbox("기간 범주", current_spec.get("options", ["30일 내", "60일 내", "90일 내", "잘 모르겠음"]), key="deadline_window_choice")
                else:
                    complaint = st.text_area("상담 내용 또는 답변", placeholder=chat_prompt, height=100, label_visibility="collapsed")
                submitted = st.form_submit_button("답변 보내기", use_container_width=True)
    else:
        complaint = None
        submitted = False
    if complaint:

        previous = st.session_state.analysis or {}
        was_in_conversation = bool(previous)
        if not was_in_conversation:
            st.session_state.original_complaint = complaint
            analysis = classify(complaint, llm)
            st.session_state.followup_answers = {}
            # 최초 분석 직후 다음 질문을 즉시 상태에 저장해, 한 번의 제출로
            # 질문과 입력창이 함께 갱신되고 다음 답변을 바로 입력할 수 있게 합니다.
            # 단순 세법 개념을 설명·안내·질문하는 경우에는 추가 질문 없이 바로 간단 답변으로 진행합니다.
            simple_tax_question = analysis.get("inquiry_type") == "SIMPLE_TAX_QUESTION" or analysis.get("desired_outcome") == "단순 세법 문의"
            first_specs = [] if simple_tax_question else required_question_specs(analysis, {})
            st.session_state.current_followup_question = first_specs[0]["question"] if first_specs else None
            # 최초 분석 직후 추가 질문 영역이 실제로 렌더링되도록 미확인 상태로 둡니다.
            st.session_state.classification_confirmed = False
            st.session_state.messages.append({"role":"assistant", "content":"말씀하신 내용을 바탕으로 불만사항을 정리했습니다. 해결방안에 꼭 필요한 사항이 있으면 한 번에 하나씩 여쭙겠습니다."})
        else:
            # 사용자의 자연어 답변을 현재 질문에 연결하고, 분류 항목은 대화 맥락에 따라 갱신합니다.
            current_question = st.session_state.get("current_followup_question")
            previous_answers = st.session_state.followup_answers
            if current_question:
                previous_answers[current_question] = complaint
            extra_context = "" if current_question else f"\n\n추가 설명: {complaint}"
            combined = st.session_state.original_complaint + extra_context + "\n\n추가 대화: " + "\n".join(
                f"질문: {q}\n답변: {a}" for q, a in previous_answers.items()
            )
            analysis = classify(combined, llm)
            # 후속 답변으로 자동 분류가 흔들리지 않도록 기존에 확인된 값과 알려진 사실을 보존합니다.
            for field in ("responsible_agency", "possible_agency", "tax_type", "tax_stage", "administrative_action", "desired_outcome"):
                old_value = previous.get(field)
                if old_value not in (None, "", "미확인") and analysis.get(field) in (None, "", "미확인"):
                    analysis[field] = old_value
            facts = analysis.setdefault("known_facts", {})
            old_facts = previous.get("known_facts") or {}
            for key, value in old_facts.items():
                if key == "notice_date":
                    continue  # 날짜 직접 입력은 사용하지 않고 기간 범주만 사용합니다.
                if value not in (None, "", "미확인"):
                    facts[key] = value
            # 현재 질문에 대한 답변을 구조화된 사실관계에 반영합니다.
            if current_question:
                answered_before_current = {q: a for q, a in previous_answers.items() if q != current_question}
                specs = required_question_specs(previous, answered_before_current)
                item = next((x for x in specs if x["question"] == current_question), None)
                if item:
                    answer = complaint.strip()
                    unknown = answer.lower() in ("모름", "잘 모르겠음", "잘 모르겠습니다", "기억나지 않음", "기억나지 않습니다")
                    if item["key"] == "기한 관련 기간":
                        facts["deadline_window"] = "잘 모르겠음" if unknown else answer
                    elif item["key"] == "문서 수령일":
                        facts["notice_date"] = None  # 새 흐름에서는 날짜를 직접 묻지 않습니다.
                    elif item["key"] == "사전 설명":
                        facts["prior_explanation"] = "있음" if answer.startswith(("예", "있")) else ("없음" if answer.startswith(("아니요", "없")) else "기억나지 않음")
                    elif item["key"] == "받은 문서": facts["notice_kind"] = None if unknown else answer
                    elif item["key"] == "세무조사 상태": facts["tax_audit_status"] = {"아직 시작하지 않음":"없음", "진행 중":"진행", "종결됨":"종결", "잘 모르겠음":None}.get(answer, answer)
                    elif item["key"] == "불복 진행 상태": facts["appeal_status"] = "진행" if any(term in answer for term in ("신청했", "진행", "기다리")) else ("기한 경과 주장" if "기한이 지난" in answer else "미진행")
                    elif item["key"] == "세목" and not unknown:
                        analysis["tax_type"] = answer
                    elif item["key"] == "기관":
                        if "지방자치단체" in answer or "관세청" in answer or "기타 기관" in answer:
                            analysis["possible_agency"] = "OTHER"
                        elif "세무서" in answer or "국세청" in answer:
                            analysis["possible_agency"] = "NTS"
                        else:
                            analysis["possible_agency"] = "UNKNOWN"
                        analysis["responsible_agency"] = answer
                    elif item["key"] == "문제 상황":
                        facts["problem_details"] = answer
                    elif item["key"] == "원하는 해결":
                        analysis["desired_outcome"] = answer
            st.session_state.messages.append({"role":"assistant", "content":"답변을 반영했습니다. 내용을 정리해 다음으로 꼭 필요한 사항만 확인하겠습니다."})
            # 답변을 받은 뒤에도 다음 질문/판단 단계가 다시 표시되도록 초기화합니다.
            st.session_state.classification_confirmed = False
        st.session_state.analysis = analysis
        st.session_state.last_result = None
        st.session_state.selected_solution = None
        st.session_state.solution_confirmed = False
        st.rerun()

    analysis = st.session_state.analysis
    if analysis:
        with progress_slot:
            st.markdown('<div class="section-card"><b>🧪 상담 진행</b><p>해결 방법을 결정하는 데 꼭 필요한 사실만 순서대로 확인합니다.</p></div>', unsafe_allow_html=True)

        # 국세청 소관이 아닌 것으로 확인되면 즉시 안내하고 국세청 권리구제 질문을 종료합니다.
        if analysis.get("possible_agency") == "OTHER":
            st.warning("현재 확인된 내용은 국세청 소관이 아닙니다. 국세청 권리구제 검토를 종료합니다.")
            agency_name = analysis.get("responsible_agency") or "해당 소관기관"
            st.markdown(f"**안내:** {agency_name}에 직접 문의하세요. 담당기관이 불명확하거나 기관 이관이 필요한 경우 국민신문고를 이용할 수 있습니다.")
            st.markdown("- [국민신문고에서 민원 신청·기관 안내](https://www.epeople.go.kr/)")
            st.markdown("- [국세청 공식 홈페이지](https://www.nts.go.kr/)")
            if st.button("새 상담 시작", key="restart_out_of_scope"):
                st.session_state.clear()
                st.rerun()
            st.stop()

        if st.session_state.analysis:
            st.session_state.classification_confirmed = True
            # 사업자등록 신청·변경 등은 국세청 소관 단순 문의이므로 권리구제 문진을 생략합니다.
            followup_specs = [] if analysis.get("business_registration_simple_inquiry") or analysis.get("inquiry_type") == "SIMPLE_TAX_QUESTION" else required_question_specs(analysis, st.session_state.followup_answers)
            if followup_specs:
                item = followup_specs[0]
                question = item["question"]
                st.session_state.current_followup_question = question
                with question_slot:
                    st.markdown(f'<div class="section-card question-card"><span class="pill">상담원 질문</span><h3>{question}</h3><p>예시: {item["example"]}</p></div>', unsafe_allow_html=True)
            else:
                st.session_state.current_followup_question = None
                with result_slot:
                    st.divider()
                    st.subheader("📜 선택한 해결방법으로 최종 안내")
                    st.markdown("필요한 사실 확인이 끝났습니다. 지금까지의 답변과 과세단계를 종합해 AI 상담원이 가장 적합한 해결 방법을 선정하고 안내합니다.")
                    uploaded_files = st.session_state.get("remedy_reference_pdfs", [])

                    facts = analysis.get("known_facts") or {}
                    stage_info = classify_stage(analysis, facts)
                    decision = decide(analysis, stage_info)
                    # 사업자등록 문의는 기관·권리구제 판정 결과와 관계없이 국세청 단순 안내로 고정합니다.
                    if analysis.get("business_registration_simple_inquiry"):
                        decision = {**(decision or {}), "status": "OK", "reason": "사업자등록 신청·변경 등 일반 문의는 국세청 소관 단순 안내로 처리합니다."}
                    deadline = check_deadline(facts.get("deadline_window"), facts.get("notice_kind"), analysis.get("tax_stage") or stage_info.get("stage"))
                    if decision.get("status") == "OUT_OF_SCOPE":
                        st.warning("국세청 소관이 아닌 것으로 판단되어 검토를 종료합니다.")
                        st.markdown("[국민신문고](https://www.epeople.go.kr/)에서 소관기관을 확인하세요.")
                        if st.button("새 상담 시작", key="restart_rule_out_of_scope"):
                            st.session_state.clear()
                            st.rerun()
                        st.stop()
                    if decision.get("status") == "NEED_INFO":
                        st.warning("상황과 필요한 해결 방법을 먼저 검토했지만, 최종 안내 전에 담당기관 확인이 필요합니다.")
                        st.markdown("문서의 발신기관·담당부서를 확인해 주세요. 기관이 불명확하면 [국민신문고 바로가기](https://www.epeople.go.kr/)에서 소관기관 안내를 받을 수 있습니다.")
                    else:
                        stage_name = analysis.get("tax_stage")
                        if not stage_name or stage_name == "미확인":
                            stage_name = stage_info.get("stage", "")
                        if stage_name in ("과세예고", "과세예고통지", "고지", "고지 후"):
                            stage_name = "과세"
                        if analysis.get("tax_stage") in ("과세예고", "과세예고통지", "고지", "고지 후"):
                            analysis["tax_stage"] = "과세"
                        routes = [f"{analysis.get('business_registration_subtype', '사업자등록')} 안내"] if analysis.get("business_registration_simple_inquiry") else choose_stage_solutions(stage_name, analysis, facts, decision)
                        st.markdown(f'<div class="section-card"><span class="pill">확인된 과세 단계</span><h3>{stage_name or "단계 확인 필요"}</h3><p>확인된 사실관계에 가장 적합한 해결 방법을 제안합니다.</p></div>', unsafe_allow_html=True)
                        # 사용자에게 해결 방법을 고르게 하지 않습니다. 확인된 모든 사실을 토대로 LLM이 후보 중 하나를 선정합니다.
                        # 해결방안 판단 참고자료는 지정된 영구 벡터 DB만 사용합니다.
                        # 현재 업로드 파일의 임시 키워드 검색이나 다른 자료로의 폴백은 하지 않습니다.
                        rag_query = f"{analysis.get('summary', '')} {analysis.get('tax_type', '')} {stage_name} {analysis.get('administrative_action', '')} {facts} {' '.join(routes)}"
                        retrieved_for_decision = []
                        collection_name = st.session_state.get("rag_collection", vector_collection)
                        db_path = st.session_state.get("rag_path", vector_path)
                        try:
                            if embedding_key:
                                retrieved_for_decision = chroma_search([], rag_query, embedding_key, collection_name, db_path)
                        except Exception as exc:
                            st.warning(f"지정된 벡터 DB 검색을 수행하지 못했습니다. 참고자료 없이 보수적으로 판단합니다: {exc}")

                        if analysis.get("business_registration_simple_inquiry"):
                            st.session_state.selected_solution = "사업자등록 신청·휴업·폐업 안내"
                            st.session_state.solution_reason = "사업자등록 신청·휴업·폐업·정정 등 일반 문의는 국세청 소관 단순 안내 대상입니다."
                            st.session_state.solution_confirmed = True
                        elif not st.session_state.solution_confirmed or st.session_state.selected_solution not in routes:
                            selection = select_best_solution(routes, analysis, decision, stage_info, deadline, llm, retrieved_for_decision)
                            st.session_state.selected_solution = selection["solution"]
                            st.session_state.solution_reason = selection["reason"]
                            st.session_state.solution_confirmed = True
                            st.session_state.last_result = None

                        selected_route = st.session_state.selected_solution
                        # 선택된 불복 절차는 신청요건·신청절차·처리절차·법률효과를 구분해
                        # 지정된 벡터 DB에서 절차명과 출처 메타데이터가 일치하는 근거를 다시 검색합니다.
                        appeal_terms = ("과세전적부", "이의신청", "심사청구", "심판청구")
                        if selected_route and any(term in selected_route for term in appeal_terms):
                            appeal_query = (
                                f"{selected_route} 신청요건 청구대상 청구자격 청구기간 신청절차 제출처 "
                                f"처리절차 심리 결정 통지 법률효과 결정효력 징수 집행정지 후속불복 "
                                f"서식 첨부서류 증거자료 {stage_name} {analysis.get('tax_type', '')} "
                                f"{analysis.get('summary', '')} {analysis.get('administrative_action', '')} {facts}"
                            )
                            try:
                                if embedding_key:
                                    appeal_hits = chroma_search([], appeal_query, embedding_key, collection_name, db_path, top_k=12)
                                    from rag.retriever import prioritize_route_evidence
                                    appeal_hits = prioritize_route_evidence(appeal_hits, selected_route, top_k=10)
                                    if appeal_hits:
                                        retrieved_for_decision = appeal_hits
                            except Exception as exc:
                                st.warning(f"선택된 불복 절차의 벡터 DB 근거를 검색하지 못했습니다: {exc}")
                        # 권리보호 경로는 세부 유형을 기준으로 벡터 DB 근거를 우선 검색합니다.
                        if selected_route and any(term in selected_route for term in ("권리보호", "납세자보호담당관", "권리침해")):
                            rights_query = (
                                f"{selected_route} {stage_name} {analysis.get('tax_type', '')} "
                                f"대상 요건 신청 절차 신청방법 첨부서류 제출서류 증빙자료 처리기관 "
                                f"{analysis.get('summary', '')} {analysis.get('administrative_action', '')} {facts}"
                            )
                            rights_hits = []
                            try:
                                from rag.retriever import prioritize_route_evidence
                                if embedding_key:
                                    rights_hits = chroma_search([], rights_query, embedding_key, collection_name, db_path, top_k=10)
                                rights_hits = prioritize_route_evidence(rights_hits, selected_route, top_k=8)
                            except Exception as exc:
                                st.warning(f"벡터 DB에서 권리보호 근거를 검색하지 못했습니다: {exc}")
                            if rights_hits:
                                retrieved_for_decision = rights_hits
                        if not selected_route:
                            st.warning("확인된 정보로 해결 방법을 확정하지 못했습니다. 관련 사실을 추가로 확인해 주세요.")
                            st.stop()
                        st.markdown(
                            f'<div class="section-card"><span class="pill">AI 상담원의 판단</span><h3>{selected_route}</h3><p>{st.session_state.solution_reason}</p></div>',
                            unsafe_allow_html=True,
                        )

                        # 원하는 해결은 초기 불만 접수 때 묻지 않고, 확정된 해결 방법과 누적 사실관계로 생성합니다.
                        analysis["desired_outcome"] = selected_route
                        analysis["confirmed_facts"] = {
                            "original_complaint": st.session_state.original_complaint,
                            "answers": dict(st.session_state.followup_answers),
                            "selected_solution": selected_route,
                            "selection_reason": st.session_state.solution_reason,
                        }
                        if st.session_state.last_result is None:
                            retrieved = list(retrieved_for_decision)
                            is_rights_route = any(term in selected_route for term in ("권리보호", "납세자보호담당관", "권리침해"))
                            plan = build_solution_plan(analysis, decision, deadline, selected_route, llm, retrieved)
                            warnings = validate_result(analysis, decision, retrieved)
                            warnings.extend(validate_evidence_for_route(selected_route, retrieved))
                            st.session_state.last_result = {"plan": plan, "warnings": warnings, "decision": decision, "analysis": analysis, "stage": stage_info, "deadline": deadline, "retrieved": retrieved, "selected_solution": selected_route}

                        result = st.session_state.last_result
                        plan = result["plan"]
                        st.markdown('<div class="answer-card"><span class="pill">상담 결과 안내문</span>', unsafe_allow_html=True)
                        st.markdown(f"### {plan.get('title', '해결 방법 안내')}")
                        st.markdown(plan.get("explanation", "확인된 사실과 AI 상담원이 선정한 해결 방법과 확인된 사실을 바탕으로 안내합니다."))
                        category = plan.get("category")
                        if category == "simple_info":
                            st.markdown("**추가 상담:** [국세종합상담센터 홈페이지](https://call.nts.go.kr/) · 전화 국번 없이 **126**")
                        else:
                            if plan.get("steps"):
                                st.markdown("**진행 절차**")
                                for step in plan.get("steps", []):
                                    st.markdown(f"- {step}")
                            if plan.get("documents"):
                                st.markdown("**준비·제출 서류**")
                                for document in plan["documents"]:
                                    st.markdown(f"- {document}")
                            st.markdown(f"**문의·제출 기관:** {plan.get('institution', '담당 기관에서 확인')} ")
                        if category == "submission":
                            st.markdown("**공식 연결:** [홈택스](https://hometax.go.kr/) · [국세청 홈페이지](https://www.nts.go.kr/)")
                        elif category == "remedy_procedure":
                            st.markdown("**공식 연결:** [국세청 홈페이지](https://www.nts.go.kr/) · [조세심판원](https://www.tt.go.kr/)")
                        elif category == "rights_protection":
                            st.markdown("**공식 연결:** [국세청 홈페이지(납세자 권리보호 안내)](https://www.nts.go.kr/) · [국민신문고](https://www.epeople.go.kr/)")
                        if category != "simple_info" and result.get("retrieved"):
                            source_labels = list(dict.fromkeys(
                                f"{source.get('filename', '참고자료')} · {source.get('page', '?')}쪽"
                                for source in result["retrieved"][:5]
                            ))
                            st.markdown("**안내 작성에 사용한 참고자료**")
                            for source_label in source_labels:
                                st.markdown(f"- {source_label}")
                        elif category != "simple_info":
                            st.info("이번 안내는 업로드 참고자료의 직접 근거를 찾지 못해 일반적인 확인 절차 중심으로 작성되었습니다. 구체적인 요건과 제출서류는 담당 기관에서 확인하세요.")
                        if plan.get("cautions"):
                            st.markdown("**주의사항**")
                            for caution in plan["cautions"]:
                                st.warning(caution)
                        if result.get("warnings"):
                            with st.expander("추가 확인 사항", expanded=False):
                                for warning in result["warnings"]:
                                    st.warning(warning)
                        if result.get("retrieved"):
                            with st.expander("참고자료 검색 근거(RAG)", expanded=False):
                                for source in result["retrieved"][:8]:
                                    st.markdown(f"**{source.get('filename', '참고자료')} · {source.get('page', '?')}쪽**")
                                    st.caption(str(source.get("text", ""))[:700])
                        st.markdown('</div>', unsafe_allow_html=True)
    # 최종 안내문이 같은 실행 주기에서 생성된 경우에도 입력창을 즉시 비웁니다.
    if st.session_state.get("last_result"):
        input_slot.empty()
        question_slot.empty()

    with restart_slot:
        st.divider()
        if st.button("＋ 새 상담 시작", key="restart_bottom", use_container_width=True):
            st.session_state.clear()
            st.rerun()

with right_col:
    st.markdown("### 💬 AI 상담창")
    st.caption("왼쪽 상담 진행 및 결과와 대조할 수 있도록 대화창 높이를 조절하세요. 대화 영역은 독립적으로 스크롤됩니다.")
    chat_height = st.slider("대화창 높이 조절", min_value=300, max_value=900, value=600, step=50, key="chat_pane_height")
    st.markdown("<div style='height:1px;background:#dce8f2;margin:.4rem 0 1rem'></div>", unsafe_allow_html=True)
    with st.container(height=chat_height, border=True):
      if st.session_state.get("original_complaint"):
          safe_original = str(st.session_state.original_complaint).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
          st.markdown(f"<div style='text-align:right;margin:.5rem 0'><span style='display:inline-block;background:#d8f5c8;color:#203247;padding:.65rem .8rem;border-radius:14px 14px 3px 14px;max-width:95%'>{safe_original}</span><div style='font-size:.75rem;color:#68798a;margin-top:.2rem'>나의 첫 상담</div></div>", unsafe_allow_html=True)
      for q, a in st.session_state.get("followup_answers", {}).items():
          safe_q = str(q).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
          safe_a = str(a).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
          st.markdown(f"<div style='display:flex;justify-content:flex-start;margin:.65rem 0'><div style='max-width:95%;background:#fff;border:1px solid #dce8f2;padding:.65rem .8rem;border-radius:14px 14px 14px 3px;box-shadow:0 2px 7px #163a5508'><div style='font-size:.75rem;color:#2587a8;font-weight:700;margin-bottom:.25rem'>상담원 · 질문</div>{safe_q}</div></div>", unsafe_allow_html=True)
          st.markdown(f"<div style='display:flex;justify-content:flex-end;margin:.3rem 0 .75rem'><div style='max-width:95%;background:#d8f5c8;padding:.65rem .8rem;border-radius:14px 14px 3px 14px'>{safe_a}</div></div>", unsafe_allow_html=True)
      if st.session_state.get("current_followup_question") and st.session_state.get("analysis"):
          safe_current = str(st.session_state.current_followup_question).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
          st.markdown(f"<div style='background:#fff;border:1px solid #9ed4e4;border-left:4px solid #2587a8;border-radius:12px;padding:.75rem;margin-top:.8rem'><div style='font-weight:700;color:#145a8d;font-size:.8rem'>다음 질문</div>{safe_current}</div>", unsafe_allow_html=True)
      if st.session_state.get("last_result"):
          st.markdown("<div style='background:#f5fbf7;border:1px solid #cce9d7;border-radius:12px;padding:.75rem;margin-top:1rem'><b>상담 결과</b><p style='margin:.4rem 0 0'>왼쪽 창에서 최종 안내문을 확인하세요.</p></div>", unsafe_allow_html=True)
