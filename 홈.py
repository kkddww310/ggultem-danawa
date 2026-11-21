import streamlit as st
import json, os, re, urllib.request
from urllib.parse import urlparse, parse_qs, quote
from youtube_transcript_api import YouTubeTranscriptApi

DEFAULT_OPENROUTER_KEY = ""
DB_FILE = "items.json"
KEY_FILE = "openrouter_key.txt"

# === 100만+ 대형 유튜버 10인 목록 ===
FEATURED_1M_YOUTUBERS = [
    "ITSub잇섭",
    "테크몽 Techmong",
    "오늘의 주우재",
    "원지의하루",
    "이사배 RISABAE",
    "레오제이 LeoJ Makeup",
    "귀곰",
    "자취남",
    "승우아빠",
    "주연 ZUYONI",
]

# === 초기 기본 탑재 데이터 (최초 접속 시 즉시 화면 구성용) ===
INITIAL_SEED_DB = [
    {"name": "앤커 맥고 Qi2 3in1 맥세이프 충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "아이폰·애플워치·에어팟을 15W 고속으로 한 번에 정리하는 접이식 충전 스테이션", "timestamp": "03:15", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+앤커+맥고+충전기"},
    {"name": "유그린 넥소드 100W GaN 멀티 고속충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "맥북과 스마트폰을 동시에 고속 충전할 수 있는 작고 발열 적은 GaN 충전기", "timestamp": "05:10", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+유그린+100W+충전기"},
    {"name": "삼성전자 포터블 SSD T7 Shield 2TB", "keyword": "외장SSD", "youtuber": "ITSub잇섭", "reason": "고화질 영상 데이터도 빠르게 전송하고 충격·방수에 강한 실사용 외장 SSD", "timestamp": "07:42", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+삼성+T7+Shield"},
    {"name": "로지텍 MX Master 3S 무선 마우스", "keyword": "마우스", "youtuber": "테크몽 Techmong", "reason": "저소음 클릭과 초고속 무한 휠로 장시간 편집·업무 피로도를 줄여주는 마우스", "timestamp": "05:40", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+MX+Master+3S"},
    {"name": "베이스어스 블레이드 100W 슬림 보조배터리", "keyword": "보조배터리", "youtuber": "테크몽 Techmong", "reason": "노트북 파우치에 쏙 들어가는 얇은 두께에 100W 고출력을 지원하는 보조배터리", "timestamp": "02:50", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+베이스어스+블레이드+100W"},
    {"name": "앤커 사운드코어 리버티 4 NC 무선 이어폰", "keyword": "이어폰", "youtuber": "테크몽 Techmong", "reason": "10만 원 이하 가격대에서 압도적인 노이즈캔슬링 성능을 보여주는 가성비 이어폰", "timestamp": "04:33", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+리버티+4+NC"},
    {"name": "포터 탱커 숄더백 블랙", "keyword": "가방", "youtuber": "오늘의 주우재", "reason": "가벼운 나일론 소재와 넉넉한 수납 포켓으로 데일리 캐주얼 룩에 잘 어울리는 가방", "timestamp": "05:07", "youtube_url": "https://www.youtube.com/results?search_query=주우재+포터+탱커+숄더백"},
    {"name": "무인양품 발이 편한 발수 스니커즈", "keyword": "스니커즈", "youtuber": "오늘의 주우재", "reason": "어떤 바지에도 무난하게 어울리고 인솔 쿠션감이 좋아 매일 손이 가는 기본 운동화", "timestamp": "06:54", "youtube_url": "https://www.youtube.com/results?search_query=주우재+무인양품+스니커즈"},
    {"name": "아식스 젤 카야노 14 운동화", "keyword": "운동화", "youtuber": "오늘의 주우재", "reason": "메탈릭 실버 포인트와 푹신한 젤 쿠셔닝으로 코디 포인트와 착화감을 잡은 슈즈", "timestamp": "07:15", "youtube_url": "https://www.youtube.com/results?search_query=주우재+젤+카야노+14"},
    {"name": "홀롤롤로 여행용 카드 동전지갑", "keyword": "지갑", "youtuber": "원지의하루", "reason": "해외여행 시 지폐·동전·카드를 가볍고 직관적으로 분리 수납하는 여행 필수 지갑", "timestamp": "03:10", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+홀롤롤로+여행지갑"},
    {"name": "로젤 쿠보 30인치 확장형 캐리어", "keyword": "캐리어", "youtuber": "원지의하루", "reason": "좁은 숙소에서도 세운 채로 앞뚜껑만 열어 짐을 꺼낼 수 있는 수납 천재 캐리어", "timestamp": "04:45", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+로젤+쿠보+캐리어"},
    {"name": "DJI 오즈모 포켓 3 크리에이터 콤보", "keyword": "카메라", "youtuber": "원지의하루", "reason": "1인치 센서와 3축 짐벌이 결합되어 흔들림 없는 여행 브이로그를 담아주는 카메라", "timestamp": "08:30", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+오즈모+포켓+3"},
    {"name": "정샘물 에센셜 스킨 누더 쿠션", "keyword": "쿠션", "youtuber": "이사배 RISABAE", "reason": "피부 본연의 윤기를 살리면서 자연스럽고 화사하게 밀착되는 베이스 쿠션", "timestamp": "03:40", "youtube_url": "https://www.youtube.com/results?search_query=이사배+정샘물+스킨+누더+쿠션"},
    {"name": "마녀공장 퓨어 클렌징 오일", "keyword": "클렌징오일", "youtuber": "이사배 RISABAE", "reason": "진한 메이크업과 블랙헤드까지 자극 없이 부드럽게 녹여내는 국민 클렌징 오일", "timestamp": "02:30", "youtube_url": "https://www.youtube.com/results?search_query=이사배+마녀공장+클렌징+오일"},
    {"name": "더샘 커버 퍼펙션 트리플 팟 컨실러", "keyword": "컨실러", "youtuber": "레오제이 LeoJ Makeup", "reason": "홍조 커버부터 다크서클·잡티 보정까지 3가지 컬러로 해결하는 올리브영 1등 컨실러", "timestamp": "04:10", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+더샘+트리플+팟+컨실러"},
    {"name": "힌스 무드인핸서 워터 리퀴드 글로우", "keyword": "틴트", "youtuber": "레오제이 LeoJ Makeup", "reason": "끈적임 없이 투명한 수분 광택이 올라오는 물먹립 대표 리퀴드 틴트", "timestamp": "13:22", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+힌스+틴트"},
    {"name": "매직캔 히포 크롬 냄새차단 쓰레기통 27L", "keyword": "쓰레기통", "youtuber": "귀곰", "reason": "이중 밀폐 구조로 여름철 음식물·기저귀 냄새까지 완벽하게 막아주는 휴지통", "timestamp": "02:39", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+매직캔+쓰레기통"},
    {"name": "샤오미 미지아 스마트 제습기 22L", "keyword": "제습기", "youtuber": "귀곰", "reason": "가성비와 앱 원격 제어, 조용한 수면 모드를 모두 갖춘 사계절 강력 제습기", "timestamp": "03:15", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+샤오미+제습기"},
    {"name": "이케아 로스코그 이동식 트롤리 카트", "keyword": "트롤리", "youtuber": "자취남", "reason": "원룸 주방·책상·침대 옆 자투리 공간을 3단 수납장으로 바꿔주는 자취 필수 트롤리", "timestamp": "01:40", "youtube_url": "https://www.youtube.com/results?search_query=자취남+이케아+로스코그"},
    {"name": "다이슨 에어랩 멀티 스타일러 컴플리트", "keyword": "헤어드라이기", "youtuber": "자취남", "reason": "과도한 열 손상 없이 바람만으로 빠르게 건조와 스타일링을 끝내는 헤어 기기", "timestamp": "04:15", "youtube_url": "https://www.youtube.com/results?search_query=다이슨+에어랩+멀티+스타일러"},
    {"name": "헹켈 트윈 폴룩스 산도쿠 식칼 18cm", "keyword": "식칼", "youtuber": "승우아빠", "reason": "가벼운 무게와 뛰어난 절삭력으로 집밥 요리 입문자부터 숙련자까지 쓰기 좋은 식칼", "timestamp": "03:10", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+헹켈+식칼"},
    {"name": "브리타 마렐라 XL 정수기 3.5L", "keyword": "정수기", "youtuber": "승우아빠", "reason": "생수 페트병 분리수거 번거로움 없이 물맛을 깔끔하게 잡아주는 자연여과 정수기", "timestamp": "02:20", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+브리타+정수기"},
    {"name": "애플 에어팟 프로 2세대 USB-C", "keyword": "이어폰", "youtuber": "주연 ZUYONI", "reason": "아이폰·맥북 간 매끄러운 기기 전환과 강력한 적응형 노이즈캔슬링을 지원하는 이어폰", "timestamp": "03:20", "youtube_url": "https://www.youtube.com/results?search_query=주연+에어팟+프로+2"},
    {"name": "소니 WH-1000XM5 노이즈캔슬링 헤드폰", "keyword": "헤드폰", "youtuber": "주연 ZUYONI", "reason": "가벼운 착용감과 업계 최고 수준의 소음 차단 성능을 보여주는 출퇴근·작업용 헤드폰", "timestamp": "05:18", "youtube_url": "https://www.youtube.com/results?search_query=주연+소니+WH-1000XM5"},
]

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")

def get_openrouter_key():
    try:
        if "OPENROUTER_API_KEY" in st.secrets and st.secrets["OPENROUTER_API_KEY"].strip():
            return st.secrets["OPENROUTER_API_KEY"].strip()
    except Exception:
        pass
    if os.path.exists(KEY_FILE):
        saved = open(KEY_FILE, "r", encoding="utf-8").read().strip()
        if saved:
            return saved
    return DEFAULT_OPENROUTER_KEY

if "nav" not in st.session_state:
    st.session_state.nav = "꿀템 홈"

# === 토스 스타일 라이트 앱 UI ===
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

.stButton > button,
.stDownloadButton > button {
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
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"],
div[data-testid="stVerticalBlockBorderWrapper"] .stDownloadButton > button {
    background-color: #F2F4F6 !important;
    color: #4E5968 !important;
    min-height: 36px !important;
    padding: 4px 10px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"] p,
div[data-testid="stVerticalBlockBorderWrapper"] .stDownloadButton > button p {
    color: #4E5968 !important;
}

.stLinkButton > a {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    text-decoration: none !important;
    border: none !important;
    width: 100% !important;
    min-height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 8px !important;
    white-space: nowrap !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"],
.stLinkButton > a[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] p,
.stLinkButton > a[kind="primary"] p {
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"],
.stLinkButton > a[kind="secondary"] {
    background-color: #E8F3FF !important;
    color: #3182F6 !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] p,
.stLinkButton > a[kind="secondary"] p {
    color: #3182F6 !important;
}

div[data-testid="stSlider"] div[role="slider"] {
    background-color: #3182F6 !important;
    border: 2px solid #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(49, 130, 246, 0.4) !important;
}
div[data-testid="stSliderThumbValue"] {
    color: #3182F6 !important;
    font-weight: 700 !important;
}
div[data-testid="stSliderTickBarMin"],
div[data-testid="stSliderTickBarMax"] {
    color: #8B95A1 !important;
}

.app-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 4px 12px 4px;
}
.app-title {
    font-size: 20px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.4px;
}
.hero-label {
    font-size: 13px;
    font-weight: 600;
    color: #8B95A1;
    margin-bottom: 4px;
}
.hero-big {
    font-size: 32px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.8px;
    line-height: 1.2;
    margin-bottom: 10px;
}
.hero-dots {
    display: flex;
    gap: 14px;
    font-size: 13px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 14px;
}
.dot-blue { color: #3182F6; margin-right: 4px; }
.dot-green { color: #00C471; margin-right: 4px; }
.hero-bar-box {
    background-color: #F4F6F8;
    border-radius: 14px;
    padding: 12px 14px;
}
.hero-bar-top {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 7px;
}
.hero-bar-track {
    width: 100%;
    height: 7px;
    background-color: #E5E8EB;
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 6px;
}
.hero-bar-fill {
    height: 100%;
    background-color: #3182F6;
    border-radius: 99px;
}
.hero-bar-sub {
    font-size: 11.5px;
    color: #8B95A1;
}
.field-label {
    font-size: 13px;
    font-weight: 700;
    color: #4E5968;
    margin: 12px 0 6px 2px;
}
.item-meta {
    font-size: 12px;
    font-weight: 600;
    color: #8B95A1;
    padding-top: 4px;
}
.shorts-badge {
    display: inline-block;
    background-color: #FFEFEF;
    color: #E11D48;
    font-size: 10.5px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 6px;
    margin-left: 5px;
}
.item-row {
    display: flex;
    align-items: center;
    gap: 13px;
    margin: 6px 0 14px 0;
}
.item-icon {
    width: 46px;
    height: 46px;
    min-width: 46px;
    border-radius: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
}
.item-info {
    flex: 1;
    min-width: 0;
}
.item-name {
    font-size: 15.5px;
    font-weight: 700;
    color: #191F28;
    line-height: 1.35;
    margin-bottom: 3px;
    word-break: keep-all;
}
.item-reason {
    font-size: 12.5px;
    color: #6B7684;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

def render_banner(target, text, kind="info"):
    palettes = {
        "info": ("#E8F3FF", "#1B64DA", "#C9E0FF"),
        "success": ("#E8F8F0", "#0B7A4B", "#BCEAD5"),
        "warning": ("#FFF6E5", "#9A5B00", "#FFE0A3"),
        "error": ("#FFEFEF", "#C92A2A", "#FFC9C9"),
    }
    bg, fg, bd = palettes.get(kind, palettes["info"])
    html = (
        f'<div style="background-color:{bg}; color:{fg}; border:1px solid {bd}; '
        f'border-radius:14px; padding:13px 15px; margin-top:10px; '
        f'font-size:13.5px; font-weight:700; line-height:1.45;">{text}</div>'
    )
    if target is not None:
        target.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown(html, unsafe_allow_html=True)

NON_PRODUCT_KEYWORDS = (
    "인트로", "오프닝", "마무리", "아웃트로", "총평", "결론", "구독", "이벤트",
    "당첨", "발표", "공지", "커뮤니티", "종료", "마감", "쿠키", "예고", "목차",
    "할인코드", "쿠폰", "최종가", "할인가", "혜택가", "정상가", "체감가",
    "진행기간", "한국시간", "항공권", "숙박", "예약", "배송", "소요",
    "챌린지", "장바구니", "신규회원", "원딜", "광군제", "블프", "세일",
    "free download", "watch more", "ncs", "stream", "download"
)

def is_non_product(text):
    t = (text or "").strip()
    t_low = t.lower()
    if not t or len(t) < 2 or len(t) > 48:
        return True
    if t[0] in ("=", "👉", "※", "→", "▶", "|", "-", "•", "🎉", "🔥", "✈️", "⚠️") or "?" in t or "!" in t:
        return True
    if re.search(r"(?:합니다|입니다|됩니다|있습니다|없습니다|않습니다|하세요|주세요|구매하세요|바랍니다|해요|예요|이에요|에요|가요|네요|같아요|되네|안해|소요)$", t):
        return True
    if t.endswith((" 제품", " 상품", " 아이템", " 추천", " 후기", " 리뷰", " 소개", " 챌린지", " 원딜", " 딜")):
        return True
    if any(w in t_low for w in NON_PRODUCT_KEYWORDS):
        return True
    return False

def pick_icon_style(name, keyword):
    text = f"{name} {keyword}".lower()
    if any(k in text for k in ("헤드폰", "이어폰", "airpods", "스피커", "오디오", "마이크")):
        return "🎧", "#EEF4FF"
    if any(k in text for k in ("배터리", "충전", "케이블", "어댑터", "멀티탭")):
        return "🔋", "#E8F8F0"
    if any(k in text for k in ("키보드", "마우스", "노트북", "모니터", "태블릿", "맥북", "거치대", "책상", "데스크", "ssd")):
        return "💻", "#F3EEFF"
    if any(k in text for k in ("카메라", "액션캠", "고프로", "삼각대", "조명", "오즈모", "미러리스", "뷰러")):
        return "📷", "#FFF4E5"
    if any(k in text for k in ("쿠션", "블러셔", "틴트", "컨실러", "클렌징", "치약", "미스트", "토너", "핸드", "크림", "세럼", "립")):
        return "💄", "#FFEFF4"
    if any(k in text for k in ("가습", "청소기", "매트", "담요", "난로", "히터", "제습", "토스터", "에어랩", "쓰레기통", "트롤리", "선풍기", "식칼", "프라이팬", "정수기", "침구")):
        return "🏠", "#EBF8FF"
    if any(k in text for k in ("지갑", "케이스", "백팩", "가방", "캐리어", "여행", "스니커즈", "신발", "운동화", "구두", "티셔츠", "선글라스", "모자")):
        return "🎒", "#F0F4FF"
    return "🛍️", "#F2F4F6"

def save_items(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def load_items():
    if not os.path.exists(DB_FILE):
        save_items(list(INITIAL_SEED_DB))
        return list(INITIAL_SEED_DB)
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def add_unique_items(new_items):
    db = load_items()
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in db}
    added = []
    for item in new_items:
        key = (item.get("name", "").strip().lower(), item.get("youtuber", "").strip().lower())
        if key[0] and key not in seen and not is_non_product(item.get("name", "")):
            db.append(item)
            seen.add(key)
            added.append(item)
    save_items(db)
    return added

def extract_video_id(url):
    if not url:
        return None
    p = urlparse(url)
    if p.hostname in ("youtu.be", "www.youtu.be"):
        return p.path.lstrip("/").split("/")[0]
    if p.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if p.path == "/watch":
            return parse_qs(p.query).get("v", [None])[0]
        if p.path.startswith(("/shorts/", "/embed/")):
            parts = p.path.split("/")
            return parts[2] if len(parts) > 2 else None
    return None

def _fetch_yt_initial_data(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        },
    )
    html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html) or re.search(r"ytInitialData\s*=\s*(\{.*?\});", html)
    return json.loads(m.group(1)) if m else {}

def _normalize_name(s):
    return re.sub(r"[\s\(\)\[\]\-_]+", "", (s or "").lower())

def _is_channel_match(query, channel_name):
    q_norm = _normalize_name(query)
    c_norm = _normalize_name(channel_name)
    if not q_norm or not c_norm or c_norm == "유튜버":
        return False
    q_core = re.sub(r"(추천템|꿀템|필수템|가성비템|리뷰|내돈내산|하울|영상|쇼츠|숏츠)", "", q_norm).strip()
    if len(q_core) >= 2 and (q_core in c_norm or c_norm in q_core):
        return True
    return q_norm in c_norm or c_norm in q_norm

def _extract_items_from_yt_data(data, default_youtuber="유튜버", default_channel_id="", force_shorts=False):
    items, seen = [], set()

    def walk(node):
        if isinstance(node, dict):
            if "videoRenderer" in node:
                vr = node["videoRenderer"]
                vid = vr.get("videoId", "")
                if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    t_runs = vr.get("title", {}).get("runs", [])
                    o_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                    cid = o_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "") if o_runs else ""
                    nav_url = vr.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
                    items.append({
                        "video_id": vid,
                        "title": t_runs[0].get("text", "제목 없음") if t_runs else "제목 없음",
                        "youtuber": o_runs[0].get("text", default_youtuber) if o_runs else default_youtuber,
                        "channel_id": cid or default_channel_id,
                        "is_shorts": force_shorts or ("/shorts/" in nav_url),
                    })
            if "reelItemRenderer" in node:
                rr = node["reelItemRenderer"]
                vid = rr.get("videoId") or rr.get("navigationEndpoint", {}).get("reelWatchEndpoint", {}).get("videoId", "")
                if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    hl = rr.get("headline", {})
                    title = hl.get("simpleText") or (hl.get("runs", [{}])[0].get("text") if hl.get("runs") else "Shorts 영상")
                    items.append({
                        "video_id": vid,
                        "title": title,
                        "youtuber": default_youtuber,
                        "channel_id": default_channel_id,
                        "is_shorts": True,
                    })
            if "shortsLockupViewModel" in node:
                sl = node["shortsLockupViewModel"]
                vid = sl.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {}).get("videoId", "")
                if not vid:
                    m_id = re.search(r"([A-Za-z0-9_-]{11})$", sl.get("entityId", ""))
                    vid = m_id.group(1) if m_id else ""
                if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    title = sl.get("overlayMetadata", {}).get("primaryText", {}).get("content", "Shorts 영상")
                    items.append({
                        "video_id": vid,
                        "title": title,
                        "youtuber": default_youtuber,
                        "channel_id": default_channel_id,
                        "is_shorts": True,
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for elem in node:
                walk(elem)

    walk(data)
    return items

def search_youtube_videos(query, limit=6, only_official=True):
    search_data = _fetch_yt_initial_data(f"https://www.youtube.com/results?search_query={quote(query)}")
    if not search_data:
        return []

    official_channel_id = ""
    official_channel_name = ""

    def find_channel(node):
        nonlocal official_channel_id, official_channel_name
        if official_channel_id:
            return
        if isinstance(node, dict):
            if "channelRenderer" in node:
                cr = node["channelRenderer"]
                cid = cr.get("channelId", "")
                t_obj = cr.get("title", {})
                cname = t_obj.get("simpleText") or (t_obj.get("runs", [{}])[0].get("text") if t_obj.get("runs") else "")
                if cid and cname and _is_channel_match(query, cname):
                    official_channel_id = cid
                    official_channel_name = cname
                    return
            for v in node.values():
                find_channel(v)
        elif isinstance(node, list):
            for elem in node:
                find_channel(elem)

    find_channel(search_data)

    if only_official and official_channel_id:
        combined = []
        seen_ids = set()
        try:
            v_data = _fetch_yt_initial_data(f"https://www.youtube.com/channel/{official_channel_id}/videos")
            v_list = _extract_items_from_yt_data(v_data, official_channel_name, official_channel_id, force_shorts=False)
        except Exception:
            v_list = []
        try:
            s_data = _fetch_yt_initial_data(f"https://www.youtube.com/channel/{official_channel_id}/shorts")
            s_list = _extract_items_from_yt_data(s_data, official_channel_name, official_channel_id, force_shorts=True)
        except Exception:
            s_list = []

        max_len = max(len(v_list), len(s_list))
        for idx in range(max_len):
            for src in (v_list, s_list):
                if idx < len(src) and src[idx]["video_id"] not in seen_ids:
                    seen_ids.add(src[idx]["video_id"])
                    combined.append(src[idx])
                    if len(combined) >= limit:
                        return combined
        if combined:
            return combined

    raw_items = _extract_items_from_yt_data(search_data)
    if only_official:
        matched_cids = {x["channel_id"] for x in raw_items if x["channel_id"] and _is_channel_match(query, x["youtuber"])}
        matched_names = {x["youtuber"] for x in raw_items if _is_channel_match(query, x["youtuber"])}
        if matched_cids or matched_names:
            filtered = [
                x for x in raw_items
                if (x["channel_id"] and x["channel_id"] in matched_cids)
                or (x["youtuber"] in matched_names)
                or (x["is_shorts"] and x["youtuber"] == "유튜버")
            ]
            return filtered[:limit]

    return raw_items[:limit]

def _find_desc_in_json(node):
    if isinstance(node, dict):
        if "attributedDescriptionBodyText" in node:
            c = node["attributedDescriptionBodyText"].get("content", "")
            if c:
                return c
        if "descriptionBodyText" in node:
            runs = node["descriptionBodyText"].get("runs", [])
            if runs:
                return "".join(r.get("text", "") for r in runs)
        for v in node.values():
            found = _find_desc_in_json(v)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_desc_in_json(item)
            if found:
                return found
    return ""

def fetch_transcript_text(video_id):
    try:
        ytt = YouTubeTranscriptApi()
        if hasattr(ytt, "fetch"):
            fetched = ytt.fetch(video_id, languages=["ko", "en"])
            return "\n".join([f"[{int(s.start)//60:02d}:{int(s.start)%60:02d}] {s.text}" for s in fetched])
    except Exception:
        pass
    try:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return "\n".join([f"[{int(s['start'])//60:02d}:{int(s['start'])%60:02d}] {s['text']}" for s in raw])
    except Exception:
        return ""

def fetch_video_bundle(video_id, youtuber_hint="유튜버", title_hint="", is_shorts=False):
    title, desc, youtuber, channel_id = title_hint, "", youtuber_hint, ""

    try:
        payload = json.dumps({
            "context": {
                "client": {
                    "clientName": "IOS",
                    "clientVersion": "19.45.4",
                    "deviceMake": "Apple",
                    "deviceModel": "iPhone16,2",
                    "hl": "ko",
                    "gl": "KR",
                }
            },
            "videoId": video_id,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/player",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)",
                "X-YouTube-Client-Name": "5",
                "X-YouTube-Client-Version": "19.45.4",
            },
        )
        res_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
        details = res_data.get("videoDetails", {})
        if details:
            title = details.get("title") or title
            desc = details.get("shortDescription", "") or desc
            youtuber = details.get("author") or youtuber
            channel_id = details.get("channelId", "")
    except Exception:
        pass

    if not desc:
        try:
            payload = json.dumps({
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20261101.00.00",
                        "hl": "ko",
                        "gl": "KR",
                    }
                },
                "videoId": video_id,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://www.youtube.com/youtubei/v1/next",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "X-YouTube-Client-Name": "1",
                    "X-YouTube-Client-Version": "2.20261101.00.00",
                },
            )
            next_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
            desc = _find_desc_in_json(next_data)
        except Exception:
            pass

    transcript = fetch_transcript_text(video_id)

    return {
        "video_id": video_id,
        "youtuber": youtuber,
        "channel_id": channel_id,
        "title": title,
        "desc": desc,
        "transcript": transcript[:4000],
        "is_shorts": is_shorts,
    }

# === OpenRouter 무료 AI 모델 기반 실제 제품명 정밀 추출 ===
def analyze_batch_with_openrouter(bundles):
    api_key = get_openrouter_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("OpenRouter API 키가 설정되지 않았습니다. [설정] 탭에서 sk-or- 키를 먼저 저장해 주세요.")

    shorts_map = {b["video_id"]: b.get("is_shorts", False) for b in bundles}
    blocks = []
    for b in bundles:
        kind = "유튜브 숏츠(Shorts)" if b.get("is_shorts") else "일반 영상"
        blocks.append(
            f"=== VIDEO_ID: {b['video_id']} | TYPE: {kind} | YOUTUBER: {b['youtuber']} ===\n"
            f"[영상 제목] {b['title']}\n"
            f"[설명란]\n{b['desc'][:1800]}\n"
            f"[영상 자막(대본)]\n{b['transcript']}"
        )

    prompt = f"""너는 유튜브 쇼핑 큐레이터야. 아래 영상(일반 영상 및 Shorts 포함)의 [설명란]과 [영상 자막]을 모두 읽고, 실제로 네이버 쇼핑이나 쿠팡에서 검색해 구매할 수 있는 **'진짜 제품명(브랜드명 + 정확한 상품명)'**만 골라서 아래 JSON 형식으로만 답해줘. 다른 설명이나 인사말은 절대 쓰지 마.

{{"items": [
  {{"video_id": "영상ID", "youtuber": "유튜버명", "name": "브랜드명 + 정확한 제품명", "keyword": "품목명", "reason": "추천 이유 한 줄 요약", "start_sec": 0}}
]}}

절대 규칙:
1. 이벤트·챌린지·프로모션·배송안내 문구("11초 장바구니 챌린지", "신규회원 전용 1000원딜", "그래서 얼마에요", "배송 10-14일 소요", "Free Download/Stream")는 절대 넣지 마.
2. 자막과 설명란을 대조해 실제 소개된 **브랜드와 정확한 제품명**만 적어줘. 브랜드·모델명이 불분명하면 과감히 버려.
3. 실제 구매 가능한 상품이 없으면 {{"items": []}} 만 반환해.

{chr(10).join(blocks)}"""

    last_err = None
    content_text = None
    for model_name in (
        "openrouter/free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ):
        try:
            body = json.dumps({
                "model": model_name,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ggultem-danawa.streamlit.app",
                    "X-Title": "Ggultem Danawa",
                },
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
            if "error" in resp:
                raise RuntimeError(resp["error"].get("message", str(resp["error"])))
            content_text = resp["choices"][0]["message"]["content"]
            break
        except Exception as e:
            last_err = e

    if content_text is None:
        raise RuntimeError(f"OpenRouter API 호출 실패: {last_err}")

    m_json = re.search(r"(\{.*\}|\[.*\])", content_text, re.DOTALL)
    if not m_json:
        return []
    parsed = json.loads(m_json.group(1))
    raw_list = parsed.get("items", []) if isinstance(parsed, dict) else parsed

    out = []
    for item in raw_list:
        vid = item.get("video_id") or bundles[0]["video_id"]
        is_shorts = shorts_map.get(vid, False)
        sec = int(item.get("start_sec", 0))
        mm, ss = divmod(sec, 60)
        name = item.get("name", "").strip()
        yt = item.get("youtuber", bundles[0]["youtuber"]).strip()
        if name and not is_non_product(name):
            video_url = f"https://www.youtube.com/shorts/{vid}" if is_shorts else f"https://youtu.be/{vid}?t={sec}"
            out.append({
                "name": name,
                "keyword": item.get("keyword", "").strip(),
                "youtuber": yt,
                "reason": item.get("reason", "").strip(),
                "timestamp": "Shorts" if is_shorts else f"{mm:02d}:{ss:02d}",
                "youtube_url": video_url,
                "is_shorts": is_shorts,
            })
    return out

def collect_for_query(query, limit, only_official=True):
    videos = search_youtube_videos(query, limit=int(limit), only_official=only_official)
    analyzed = {extract_video_id(i.get("youtube_url", "")) for i in load_items()}
    targets = [v for v in videos if v["video_id"] not in analyzed]
    if not targets:
        return [], 0

    bundles = []
    for v in targets:
        b = fetch_video_bundle(
            v["video_id"],
            v["youtuber"],
            v["title"],
            is_shorts=v.get("is_shorts", False),
        )
        if only_official and not _is_channel_match(query, b["youtuber"]):
            continue
        bundles.append(b)

    if not bundles:
        return [], 0

    items = analyze_batch_with_openrouter(bundles)
    added = add_unique_items(items)
    return added, len(bundles)

def render_toss_card(item, idx):
    icon, bg_color = pick_icon_style(item.get("name", ""), item.get("keyword", ""))
    is_shorts = item.get("is_shorts") or item.get("timestamp") == "Shorts" or "/shorts/" in item.get("youtube_url", "")
    badge_html = "<span class='shorts-badge'>Shorts</span>" if is_shorts else ""
    meta_text = f"{item['youtuber']} · {'쇼츠 추천' if is_shorts else item['timestamp'] + ' 추천'}"

    with st.container(border=True):
        top_l, top_r = st.columns([6.5, 1])
        with top_l:
            st.markdown(f"<div class='item-meta'>{meta_text}{badge_html}</div>", unsafe_allow_html=True)
        with top_r:
            if st.button("✕", key=f"del_{idx}_{item['name']}", help="목록에서 삭제"):
                db = [x for x in load_items() if not (x.get("name") == item.get("name") and x.get("youtuber") == item.get("youtuber"))]
                save_items(db)
                st.rerun()

        st.markdown(f"""
        <div class="item-row">
            <div class="item-icon" style="background-color: {bg_color};">{icon}</div>
            <div class="item-info">
                <div class="item-name">{item['name']}</div>
                <div class="item-reason">{item['reason']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        q = quote(item["name"])
        b1, b2, b3 = st.columns(3)
        b1.link_button("네이버 최저가", f"https://search.shopping.naver.com/search/all?query={q}&sort=price_asc", type="primary", use_container_width=True)
        b2.link_button("쿠팡 최저가", f"https://www.coupang.com/np/search?q={q}&sorter=salePriceAsc", use_container_width=True)
        b3.link_button("▶️ 영상보기", item["youtube_url"], use_container_width=True)

# === 상단 앱 헤더 ===
db = load_items()
yt_count = len({i.get("youtuber", "") for i in db if i.get("youtuber")})

st.markdown("""
<div class="app-topbar">
    <div class="app-title">‹ &nbsp; 꿀템 다나와</div>
    <div style="font-size:13px; font-weight:600; color:#8B95A1;">100만+ 대형 유튜버 큐레이션</div>
</div>
""", unsafe_allow_html=True)

# === 상단 요약 대시보드 카드 ===
fill_pct = min(100, int((len(db) / 200) * 100)) if db else 0
st.markdown(f"""
<div class="hero-card">
    <div class="hero-label">모아둔 유튜버 검증 꿀템</div>
    <div class="hero-big">{len(db):,}개</div>
    <div class="hero-dots">
        <div><span class="dot-blue">●</span>유튜버 <b>{yt_count}명</b></div>
        <div><span class="dot-green">●</span>최저가 비교 <b style="color:#3182F6;">실시간 연동</b></div>
    </div>
    <div class="hero-bar-box">
        <div class="hero-bar-top">
            <span>목표 DB 200개</span>
            <span style="color:#3182F6;">{fill_pct}%</span>
        </div>
        <div class="hero-bar-track">
            <div class="hero-bar-fill" style="width: {fill_pct}%;"></div>
        </div>
        <div class="hero-bar-sub">버튼을 누르면 네이버·쿠팡 낮은가격순으로 바로 연결돼요</div>
    </div>
</div>
""", unsafe_allow_html=True)

# === 상단 3개 탭 버튼 ===
t1, t2, t3 = st.columns(3)
for col, label in zip([t1, t2, t3], ["꿀템 홈", "자동 수집", "설정"]):
    is_active = (st.session_state.nav == label)
    if col.button(label, key=f"nav_{label}", type="primary" if is_active else "secondary", use_container_width=True):
        st.session_state.nav = label
        st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

if st.session_state.nav == "꿀템 홈":
    yts = ["전체 유튜버"] + sorted(list({i.get("youtuber", "") for i in db if i.get("youtuber")}))
    c_search, c_filter = st.columns([1.55, 1.1])
    kw = c_search.text_input("검색", placeholder="🔍 물건 검색 (예: 쿠션, 충전기, 캐리어)", label_visibility="collapsed")
    sel_yt = c_filter.selectbox("유튜버", yts, label_visibility="collapsed")

    filtered = [i for i in db if sel_yt == "전체 유튜버" or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "") + i.get("youtuber", "")).lower()]

    if filtered:
        st.markdown(f"<div style='font-size:13px; font-weight:700; color:#4E5968; margin: 12px 4px 8px 4px;'>추천템 목록 ({len(filtered)}건)</div>", unsafe_allow_html=True)
        for idx, item in enumerate(reversed(filtered)):
            render_toss_card(item, idx)
    elif kw:
        with st.container(border=True):
            st.markdown(f"<div class='item-name'>'{kw}' 추천템이 아직 없어요</div><div class='item-reason' style='margin:6px 0 12px 0;'>네이버 쇼핑에서 바로 최저가를 확인해 보세요.</div>", unsafe_allow_html=True)
            st.link_button(f"네이버 쇼핑에서 '{kw}' 최저가 보기", f"https://search.shopping.naver.com/search/all?query={quote(kw)}&sort=price_asc", type="primary", use_container_width=True)
    else:
        with st.container(border=True):
            st.markdown("<div class='item-name'>저장된 추천템이 없어요</div><div class='item-reason'>'자동 수집' 탭에서 유튜버 영상을 분석하거나 '설정'에서 기본 DB를 복원해 보세요.</div>", unsafe_allow_html=True)

elif st.session_state.nav == "자동 수집":
    if not get_openrouter_key():
        render_banner(None, "💡 OpenRouter 무료 API 키(깃허브 1초 로그인 발급)를 [설정] 탭에 저장하면 100만+ 유튜버 전체를 한 번에 수집할 수 있어요.", "warning")

    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:4px;'>🌐 100만+ 대형 유튜버 10인 전체 일괄 수집</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='item-reason' style='margin-bottom:12px;'>{', '.join(FEATURED_1M_YOUTUBERS)}의 최신 영상·숏츠를 OpenRouter 무료 AI로 한 번에 추출해요.</div>", unsafe_allow_html=True)

        if st.button("✨ 대형 유튜버 10명 전체 일괄 수집 실행", type="primary", use_container_width=True):
            status_all = st.empty()
            if not get_openrouter_key():
                render_banner(status_all, "⚠️ OpenRouter API 키가 설정되지 않았습니다. [설정] 탭에서 sk-or- 키를 먼저 입력해 주세요.", "error")
            else:
                total_added = []
                for idx_yt, yt_name in enumerate(FEATURED_1M_YOUTUBERS, start=1):
                    render_banner(status_all, f"[{idx_yt}/{len(FEATURED_1M_YOUTUBERS)}] '{yt_name}' 공식 채널 영상·숏츠 AI 분석 중...", "info")
                    try:
                        added_yt, _ = collect_for_query(yt_name, limit=4, only_official=True)
                        total_added.extend(added_yt)
                    except Exception:
                        pass
                render_banner(status_all, f"일괄 수집 완료! 실제 제품 {len(total_added)}개가 새로 추가되었어요.", "success")
                for a in total_added:
                    st.write(f"• **{a['name']}** ({a['youtuber']} · `{a['timestamp']}`)")

    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>🤖 특정 유튜버 최신 영상·숏츠 AI 수집</div>", unsafe_allow_html=True)
        st.markdown("<div class='item-reason' style='margin-bottom:10px;'>공식 채널의 영상과 숏츠 자막을 분석해 실제 브랜드·제품명만 추출합니다.</div>", unsafe_allow_html=True)

        st.markdown("<div class='field-label'>유튜버 이름</div>", unsafe_allow_html=True)
        q_in = st.text_input("키워드", placeholder="예: 지냐, 오늘의 주우재, 잇섭, 이사배", label_visibility="collapsed")

        only_official = st.checkbox("🎯 대표 유튜버 공식 채널만 수집 (타 채널·클립 제외)", value=True)

        st.markdown("<div class='field-label'>분석할 최신 영상·숏츠 수</div>", unsafe_allow_html=True)
        lim = st.slider("영상 수", 1, 10, 6, label_visibility="collapsed")

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 OpenRouter AI 정밀 수집 시작하기", type="primary", use_container_width=True) and q_in:
            status = st.empty()
            if not get_openrouter_key():
                render_banner(status, "⚠️ OpenRouter API 키가 설정되지 않았습니다. [설정] 탭에서 sk-or- 키를 먼저 입력해 주세요.", "error")
            else:
                try:
                    render_banner(status, "1/2 공식 채널의 최신 영상·숏츠 자막을 불러오고 있어요...", "info")
                    added, checked_cnt = collect_for_query(q_in, limit=int(lim), only_official=only_official)
                    if checked_cnt == 0:
                        render_banner(status, "이미 모두 수집한 영상들이거나 일치하는 공식 채널 영상이 없어요.", "info")
                    else:
                        render_banner(status, f"완료! 영상·숏츠 {checked_cnt}개에서 실제 제품 {len(added)}개가 추가되었어요.", "success")
                        for a in added:
                            st.write(f"• **{a['name']}** ({a['youtuber']} · `{a['timestamp']}`)")
                except Exception as e:
                    render_banner(status, f"수집 중 오류가 발생했어요: {e}", "error")

elif st.session_state.nav == "설정":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>⚡ OpenRouter 무료 API 키 설정</div><div class='item-reason' style='margin-bottom:12px;'>openrouter.ai에서 깃허브 로그인 후 발급받은 sk-or- 키를 입력하세요.</div>", unsafe_allow_html=True)
        new_key = st.text_input("OpenRouter API 키", type="password", placeholder="sk-or-v1-...", label_visibility="collapsed")
        if st.button("OpenRouter API 키 저장", type="primary", use_container_width=True) and new_key.strip():
            open(KEY_FILE, "w", encoding="utf-8").write(new_key.strip())
            render_banner(None, "새 OpenRouter API 키가 저장되었어요!", "success")

    with st.container(border=True):
        st.markdown(f"<div class='item-name' style='margin-bottom:6px;'>🗂️ 영구 저장용 DB 백업 및 관리</div><div class='item-reason' style='margin-bottom:12px;'>현재 <b>{len(db)}개</b>가 저장되어 있습니다. 수집 후 다운로드해 깃허브에 올리면 영구 보존됩니다.</div>", unsafe_allow_html=True)

        st.download_button(
            label="📥 수집된 DB(items.json) 다운로드",
            data=json.dumps(db, ensure_ascii=False, indent=2),
            file_name="items.json",
            mime="application/json",
            use_container_width=True,
        )
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("기본 100만+ 유튜버 샘플 DB 복원", use_container_width=True):
            added = add_unique_items(INITIAL_SEED_DB)
            render_banner(None, f"샘플 데이터 {len(added)}개가 복원되었어요!", "success")
            st.rerun()
# === 여기까지 복사되면 끝 ===
