"""납세자 고충 상담 화면의 공통 디자인 요소."""
import streamlit as st


def apply_theme():
    st.markdown("""
    <style>
    :root { --navy:#173f61; --teal:#168f83; --ink:#243b4d; --muted:#687f90; --line:#d9e8f0; --sky:#eaf6ff; --mint:#e9f8f3; }
    .stApp { background:linear-gradient(180deg,#edf7ff 0%,#f8fcff 36%,#ffffff 100%); color:var(--ink); }
    [data-testid="stMain"] .block-container { max-width:1280px; }
    [data-testid="stChatMessage"] { box-shadow:0 4px 15px #244b6410; }
    .hero { position:relative; overflow:hidden; background:linear-gradient(110deg,#e7f6ff 0%,#f7fcff 52%,#dff5ef 100%); color:#173f61; border:1px solid #cfe7f4; }
    .hero-kicker { color:#168f83; }
    .hero-title { color:#174a70!important; }
    .hero-copy { color:#34566c; }
    .hero-note { color:#5d7788; }
    .hero:after { content:"⚖️  👩🏻‍💼"; position:absolute; right:28px; bottom:12px; font-size:2.2rem; opacity:.75; }
    .question-card { border:1px solid #b9e4db; background:linear-gradient(135deg,#f0fcf8,#ffffff); border-radius:18px; padding:20px 22px; margin:12px 0 14px; box-shadow:0 7px 20px #167e7310; }
    .card-label { color:#138578; font-size:.88rem; font-weight:800; margin-bottom:12px; }
    .card-icon { display:inline-flex; align-items:center; justify-content:center; background:#d4f2e9; border-radius:9px; width:27px; height:27px; margin-right:7px; }
    .question-title { color:#173f61; font-size:1.2rem; font-weight:800; line-height:1.65; }
    .question-help { color:#617a89; font-size:.9rem; line-height:1.7; margin-top:10px; }
    .final-letter { border:1px solid #9ad9ca; border-bottom:0; border-radius:20px 20px 0 0; padding:22px 24px 14px; margin-top:16px; background:linear-gradient(115deg,#e7faf4,#f7fffc); }
    .letter-topline { color:#078574; font-weight:850; font-size:.9rem; letter-spacing:.02em; }
    .letter-topline span { display:inline-flex; width:30px; height:30px; align-items:center; justify-content:center; border-radius:50%; background:#c9f0e5; margin-right:8px; }
    .final-letter h2 { color:#116c64; margin:.6rem 0; font-size:1.5rem; }
    .letter-intro { color:#5b7778; margin:0; line-height:1.65; }
    .letter-body { border:1px solid #9ad9ca; border-top:1px dashed #b6e1d7; border-radius:0 0 20px 20px; padding:22px 24px; background:#fff; line-height:1.9; box-shadow:0 8px 24px #167e730c; }
    .infographic-heading { color:#174a70; font-weight:850; font-size:1.05rem; margin:22px 0 10px; }
    .info-step { display:flex; align-items:flex-start; gap:13px; background:#f3f9ff; border:1px solid #d8eaf7; border-radius:13px; padding:13px 15px; margin:8px 0; line-height:1.65; }
    .info-step-number { display:inline-flex; flex:0 0 34px; height:34px; align-items:center; justify-content:center; border-radius:11px; color:#fff; background:linear-gradient(145deg,#2686c2,#168f83); font-weight:850; }
    .info-chip { display:inline-block; vertical-align:top; background:#f0faf7; border:1px solid #d5eee6; border-radius:11px; padding:10px 13px; margin:4px; color:#285a58; }
    .agency-card { margin-top:15px; padding:16px 18px; border-radius:15px; background:#edf6ff; border:1px solid #d4e7f7; line-height:1.7; }
    .agency-label { color:#245f8a; font-weight:850; margin-bottom:4px; }
    [data-testid="stHeader"] { background:rgba(245,248,251,.94); }
    .block-container { max-width:1080px; padding-top:1.2rem; padding-bottom:2.5rem; }
    h1,h2,h3 { color:var(--navy); letter-spacing:-.025em; }
    h1 { font-weight:800; }
    [data-testid="stSidebar"] { background:#f0f4f7; border-right:1px solid var(--line); }
    [data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:18px; padding:.8rem 1rem; background:#fff; margin-bottom:.7rem; }
    [data-testid="stChatMessage"] [data-testid="stCaptionContainer"] { color:#237d76; font-weight:700; }
    [data-testid="stChatInput"] { border-radius:16px; }
    .hero { background:linear-gradient(118deg,#20394f 0%,#2d6077 72%,#237d76 100%); color:#fff; border-radius:22px; padding:25px 28px; margin-bottom:18px; box-shadow:0 9px 24px #20394f18; }
    .hero-kicker { color:#c9eeea; font-size:.78rem; font-weight:750; letter-spacing:.07em; }
    .hero-title { color:#fff!important; font-size:1.85rem; font-weight:850; margin:.35rem 0 .55rem; }
    .hero-copy { color:#f0f7fb; font-size:1rem; line-height:1.7; max-width:850px; }
    .hero-note { margin-top:10px; font-size:.8rem; color:#d8e8ef; }
    .progress-wrap { display:flex; align-items:center; gap:0; padding:11px 14px; margin:0 0 18px; background:#fff; border:1px solid var(--line); border-radius:14px; }
    .progress-step { display:flex; align-items:center; gap:7px; flex:1; min-width:0; color:#81909d; font-size:.84rem; }
    .progress-step:not(:last-child)::after { content:""; height:1px; background:#dbe4e9; flex:1; margin:0 9px; }
    .progress-dot { display:inline-flex; align-items:center; justify-content:center; width:25px; height:25px; flex:0 0 25px; border-radius:50%; background:#edf1f4; color:#667887; font-size:.75rem; font-weight:800; }
    .progress-step.active { color:#1e615c; font-weight:800; }
    .progress-step.active .progress-dot { background:#237d76; color:white; }
    .progress-step.done { color:#52736f; }
    .progress-step.done .progress-dot { background:#d9efeb; color:#1e615c; }
    .eyebrow { color:var(--teal); font-weight:800; font-size:.76rem; letter-spacing:.06em; margin-bottom:.25rem; }
    .answer-panel { background:#f2f9f7; border:1px solid #d3e9e4; border-radius:16px; padding:18px 20px; }
    div.stButton > button { border-radius:11px; font-weight:700; min-height:2.55rem; }
    div.stButton > button[kind="primary"] { background:#237d76; border-color:#237d76; }
    [data-testid="stAlert"] { border-radius:13px; }
    hr { border-color:var(--line); }
    @media(max-width:700px) {
      .block-container { padding:1rem .75rem 2rem; }
      .hero { padding:21px 18px; border-radius:17px; }
      .hero-title { font-size:1.45rem; }
      .progress-wrap { padding:9px 7px; }
      .progress-step { display:flex; flex-direction:column; gap:4px; text-align:center; font-size:.69rem; }
      .progress-step:not(:last-child)::after { display:none; }
      .progress-dot { width:23px; height:23px; flex-basis:23px; }
    }
    </style>""", unsafe_allow_html=True)


def render_hero():
    st.markdown("""
    <section class="hero">
      <div class="hero-kicker">납세자 고충 상담 안내</div>
      <div class="hero-title">안녕하세요. 세금 문제를 함께 살펴보겠습니다.</div>
      <div class="hero-copy">어떤 일로 걱정하고 계신지 편하게 말씀해 주세요. 어려운 세무 용어나 절차를 모르셔도 괜찮습니다. 상담 직원이 안내하듯 필요한 내용을 차근차근 확인하고, 지금 상황에서 할 수 있는 방법을 알기 쉽게 정리해 드리겠습니다.</div>
      <div class="hero-note">주민등록번호·계좌번호 등 민감한 개인정보는 입력하지 마세요. 실제 신청 가능 여부와 기한은 담당 기관에서 최종 확인해 주세요.</div>
    </section>""", unsafe_allow_html=True)


def render_steps(active=1, container=None):
    """현재 위치를 한 번만 표시하는 간결한 진행 표시줄."""
    steps = [(1, "상황 듣기"), (2, "내용 확인"), (3, "방법 검토"), (4, "안내 받기")]
    items = []
    for number, title in steps:
        state = "active" if number == active else ("done" if number < active else "")
        marker = "✓" if number < active else str(number)
        items.append(
            f'<div class="progress-step {state}"><span class="progress-dot">{marker}</span>'
            f'<span>{title}</span></div>'
        )
    target = container if container is not None else st
    target.markdown('<div class="progress-wrap">' + ''.join(items) + '</div>', unsafe_allow_html=True)


def render_section_kicker(kicker, title, description=None):
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.subheader(title)
    if description:
        st.caption(description)
