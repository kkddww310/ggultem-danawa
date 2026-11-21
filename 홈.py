import streamlit as st
import json, os, re, urllib.request
from urllib.parse import urlparse, parse_qs, quote
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

DEFAULT_API_KEY = ""
DB_FILE = "items.json"
KEY_FILE = "api_key.txt"

# 대표 유튜버 목록 (전체 자동 수집 및 초기 데이터용)
FEATURED_YOUTUBERS = [
    "오늘의 주우재",
    "ITSub잇섭",
    "테크몽 Techmong",
    "가전주부",
    "디에디트 THE EDIT",
]

# 최초 접속 시 DB가 비어있을 때 자동 탑재되는 실제 유튜버 추천템 데이터
INITIAL_SEED_ITEMS = [
    {
        "name": "앤커 맥고 Qi2 3in1 맥세이프 충전기",
        "keyword": "충전기",
        "youtuber": "ITSub잇섭",
        "reason": "책상 위 아이폰·애플워치·에어팟을 15W 고속으로 한 번에 정리하는 충전 스테이션",
        "timestamp": "03:15",
        "youtube_url": "https://www.youtube.com/results?search_query=잇섭+앤커+맥고+충전기",
    },
    {
        "name": "로지텍 MX Master 3S 무선 마우스",
        "keyword": "마우스",
        "youtuber": "테크몽 Techmong",
        "reason": "저소음 클릭과 무한 휠로 장시간 작업 피로도를 줄여주는 데스크 필수 마우스",
        "timestamp": "05:40",
        "youtube_url": "https://www.youtube.com/results?search_query=테크몽+MX+Master+3S",
    },
    {
        "name": "샤오미 미지아 스마트 제습기 22L",
        "keyword": "제습기",
        "youtuber": "가전주부",
        "reason": "가성비와 앱 원격 제어, 조용한 수면 모드를 모두 갖춘 사계절 제습기",
        "timestamp": "02:10",
        "youtube_url": "https://www.youtube.com/results?search_query=가전주부+샤오미+제습기",
    },
    {
        "name": "무인양품 발이 편한 스니커즈",
        "keyword": "스니커즈",
        "youtuber": "오늘의 주우재",
        "reason": "어떤 바지에도 무난하게 어울리고 쿠션감이 좋아 매일 손이 가는 기본 운동화",
        "timestamp": "04:22",
        "youtube_url": "https://www.youtube.com/results?search_query=주우재+무인양품+스니커즈",
    },
    {
        "name": "소니 WH-1000XM5 노이즈캔슬링 헤드폰",
        "keyword": "헤드폰",
        "youtuber": "디에디트 THE EDIT",
        "reason": "가벼운 착용감과 업계 최고 수준의 소음 차단 성능을 보여주는 출퇴근·작업용 헤드폰",
        "timestamp": "06:18",
        "youtube_url": "https://www.youtube.com/results?search_query=디에디트+WH-1000XM5",
    },
]

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")

def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"].strip():
            return st.secrets["GEMINI_API_KEY"].strip()
    except Exception:
        pass
    if os.path.exists(KEY_FILE):
        saved = open(KEY_FILE, "r", encoding="utf-8").read().strip()
        if saved:
            return saved
    return DEFAULT_API_KEY

if "nav" not in st.session_state:
    st.session_state.nav = "꿀템 홈"
if "collect_mode" not in st.session_state:
    st.session_state.collect_mode = "ai" if get_api_key() else "local"

# === 토스 스타일 라이트 앱 UI (상태창/알림창 가독성 완벽 수정) ===
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    color-scheme: light !important;
    --background-color: #F2F4F6 !important;
    --secondary-background-color: #FFFFFF !important;
    --text-color: #191F28 !important;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background-color: #F2F4F6 !important;
    color: #191F28 !important;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
    background: transparent !important;
    visibility: hidden;
}

.block-container {
    max-width: 480px !important;
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
[data-testid="stCheckbox"] label span {
    color: #191F28 !important;
}

/* 알림창(st.info / st.success / st.warning / st.error) 다크배경 글씨 씹힘 해결 */
div[data-testid="stAlert"],
div[data-baseweb="notification"] {
    background-color: #E8F3FF !important;
    border: 1px solid #C9E0FF !important;
    border-radius: 14px !important;
    color: #191F28 !important;
}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] div,
div[data-testid="stAlert"] span,
div[data-baseweb="notification"] p,
div[data-baseweb="notification"] div {
    color: #191F28 !important;
    -webkit-text-fill-color: #191F28 !important;
    font-weight: 600 !important;
}
div[data-testid="stAlert"] svg {
    fill: #3182F6 !important;
}

.hero-card {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 22px 22px 20px 22px;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.04);
    margin-bottom: 16px;
}

div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background-color: #FFFFFF !important;
    border: none !important;
    outline: none !important;
    border-radius: 22px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    box-shadow: 0 2px 14px rgba(0, 0, 0, 0.04) !important;
    padding: 18px 20px !important;
    margin-bottom: 12px !important;
}

div[data-testid="stTextInputRootElement"],
div[data-testid="stTextInputRootElement"] > div,
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E5E8EB !important;
    border-radius: 14px !important;
    color: #191F28 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;
}
div[data-testid="stTextInputRootElement"]:focus-within {
    border-color: #3182F6 !important;
}
div[data-testid="stTextInputRootElement"] input,
div[data-baseweb="input"] input,
div[data-testid="stSelectbox"] span,
div[data-testid="stSelectbox"] div {
    background-color: transparent !important;
    color: #191F28 !important;
    -webkit-text-fill-color: #191F28 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stTextInputRootElement"] input::placeholder {
    color: #8B95A1 !important;
    -webkit-text-fill-color: #8B95A1 !important;
}
div[data-testid="stSelectbox"] svg {
    fill: #4E5968 !important;
}
ul[data-baseweb="menu"],
ul[data-baseweb="menu"] li {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
}

.stButton > button {
    border-radius: 13px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    border: none !important;
    min-height: 40px !important;
    transition: all 0.15s ease !important;
}

button[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"],
button[kind="primary"] {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
}
button[data-testid="stBaseButton-primary"] p,
button[kind="primary"] p {
    color: #191F28 !important;
}

button[data-testid="stBaseButton-secondary"],
button[data-testid="baseButton-secondary"],
button[kind="secondary"] {
    background-color: #E5E8EB !important;
    color: #6B7684 !important;
    box-shadow: none !important;
}
button[data-testid="stBaseButton-secondary"] p,
button[kind="secondary"] p {
    color: #6B7684 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
    box-shadow: 0 3px 10px rgba(49, 130, 246, 0.25) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"] p,
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] p {
    color: #FFFFFF !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"]:hover {
    background-color: #1B64DA !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"] {
    background-color: #F2F4F6 !important;
    color: #4
