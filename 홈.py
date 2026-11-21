import streamlit as st
import json, os, re, urllib.request
from urllib.parse import urlparse, parse_qs, quote
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

DEFAULT_API_KEY = ""
DB_FILE = "items.json"
KEY_FILE = "api_key.txt"

FEATURED_YOUTUBERS = [
    "ITSub잇섭",
    "테크몽 Techmong",
    "가전주부",
    "오늘의 주우재",
    "디에디트 THE EDIT",
    "주연 ZUYONI",
    "뻘짓연구소",
]

# === 대표 유튜버 7인 실제 추천템 통합 DB (자동 탑재 및 1클릭 동기화용) ===
CURATED_YOUTUBER_DB = [
    # 1. ITSub잇섭
    {"name": "앤커 맥고 Qi2 3in1 맥세이프 충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "책상 위 아이폰·애플워치·에어팟을 15W 고속으로 한 번에 정리하는 충전 스테이션", "timestamp": "03:15", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+앤커+맥고+충전기"},
    {"name": "유그린 넥소드 100W GaN 멀티 고속충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "노트북과 스마트폰을 동시에 고속 충전할 수 있는 작고 발열 적은 GaN 충전기", "timestamp": "05:10", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+유그린+100W+충전기"},
    {"name": "삼성전자 포터블 SSD T7 Shield 2TB", "keyword": "외장SSD", "youtuber": "ITSub잇섭", "reason": "고화질 영상 편집 데이터도 빠르게 전송하고 충격과 방수에 강한 외장 SSD", "timestamp": "07:42", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+삼성+T7+Shield"},
    {"name": "벨킨 부스트차지 프로 2in1 맥세이프 거치대", "keyword": "거치대", "youtuber": "ITSub잇섭", "reason": "묵직한 하단 무게중심으로 한 손으로 아이폰을 떼어내도 흔들리지 않는 거치대", "timestamp": "04:08", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+벨킨+맥세이프+거치대"},
    {"name": "키크론 Q1 Pro 커스텀 무선 기계식 키보드", "keyword": "키보드", "youtuber": "ITSub잇섭", "reason": "풀 알루미늄 바디와 가스켓 마운트로 도각거리는 타건감을 제공하는 무선 키보드", "timestamp": "09:20", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+키크론+Q1+Pro"},

    # 2. 테크몽 Techmong
    {"name": "로지텍 MX Master 3S 무선 마우스", "keyword": "마우스", "youtuber": "테크몽 Techmong", "reason": "저소음 클릭과 초고속 무한 휠로 장시간 작업 피로도를 줄여주는 데스크 마우스", "timestamp": "05:40", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+MX+Master+3S"},
    {"name": "베이스어스 블레이드 100W 슬림 보조배터리", "keyword": "보조배터리", "youtuber": "테크몽 Techmong", "reason": "노트북 파우치에 쏙 들어가는 얇은 두께에 100W 고출력을 지원하는 보조배터리", "timestamp": "02:50", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+베이스어스+블레이드+100W"},
    {"name": "샤오미 미지아 무선 핸디 청소기 미니", "keyword": "청소기", "youtuber": "테크몽 Techmong", "reason": "책상 위 먼지와 키보드 틈새, 차량 내부를 간편하게 흡입하는 초경량 청소기", "timestamp": "06:15", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+샤오미+미니+청소기"},
    {"name": "신지모루 맥세이프 자석 태블릿 거치대", "keyword": "거치대", "youtuber": "테크몽 Techmong", "reason": "강력한 자력과 견고한 힌지로 아이패드 드로잉·영상 시청 시 흔들림 없는 거치대", "timestamp": "08:17", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+태블릿+거치대"},
    {"name": "앤커 사운드코어 리버티 4 NC 무선 이어폰", "keyword": "이어폰", "youtuber": "테크몽 Techmong", "reason": "10만 원 이하 가격대에서 압도적인 노이즈캔슬링 성능을 보여주는 가성비 이어폰", "timestamp": "04:33", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+리버티+4+NC"},

    # 3. 가전주부
    {"name": "샤오미 미지아 스마트 제습기 22L", "keyword": "제습기", "youtuber": "가전주부", "reason": "대용량 제습과 앱 원격 제어, 조용한 수면 모드를 모두 갖춘 가성비 제습기", "timestamp": "02:10", "youtube_url": "https://www.youtube.com/results?search_query=가전주부+샤오미+제습기"},
    {"name": "다이슨 에어랩 멀티 스타일러 컴플리트 롱", "keyword": "헤어드라이기", "youtuber": "가전주부", "reason": "과도한 열 손상 없이 바람만으로 볼륨과 컬을 빠르게 완성하는 헤어 스타일러", "timestamp": "03:45", "youtube_url": "https://www.youtube.com/results?search_query=가전주부+다이슨+에어랩"},
    {"name": "로보락 S8 MaxV Ultra 로봇청소기", "keyword": "로봇청소기", "youtuber": "가전주부", "reason": "모서리 확장 브러시와 온수 물걸레 세척·건조까지 자동으로 처리하는 로봇청소기", "timestamp": "06:50", "youtube_url": "https://www.youtube.com/results?search_query=가전주부+로보락+S8"},
    {"name": "발뮤다 더 토스터 프로 스팀 토스터기", "keyword": "토스터기", "youtuber": "가전주부", "reason": "스팀 제어 기술로 겉은 바삭하고 속은 촉촉하게 구워주는 주방 인기 토스터기", "timestamp": "01:55", "youtube_url": "https://www.youtube.com/results?search_query=가전주부+발뮤다+토스터"},
    {"name": "에어메이드 스마트 타워형 가열식 가습기", "keyword": "가습기", "youtuber": "가전주부", "reason": "100도 끓인 수증기로 세균 걱정 없이 따뜻하고 쾌적한 습도를 유지하는 가습기", "timestamp": "08:12", "youtube_url": "https://www.youtube.com/results?search_query=가전주부+가열식+가습기"},

    # 4. 오늘의 주우재
    {"name": "무인양품 발이 편한 발수 스니커즈", "keyword": "스니커즈", "youtuber": "오늘의 주우재", "reason": "어떤 바지에도 무난하게 어울리고 인솔 쿠션감이 좋아 매일 손이 가는 기본 운동화", "timestamp": "04:22", "youtube_url": "https://www.youtube.com/results?search_query=주우재+무인양품+스니커즈"},
    {"name": "유니클로 에어리즘 코튼 오버사이즈 티셔츠", "keyword": "티셔츠", "youtuber": "오늘의 주우재", "reason": "탄탄한 겉면과 쾌적한 안감으로 여름부터 간절기 이너까지 활용도 높은 기본 반팔", "timestamp": "02:30", "youtube_url": "https://www.youtube.com/results?search_query=주우재+유니클로+에어리즘+티셔츠"},
    {"name": "아식스 젤 카야노 14 운동화", "keyword": "운동화", "youtuber": "오늘의 주우재", "reason": "메탈릭 실버 포인트와 푹신한 젤 쿠셔닝으로 코디 포인트와 착화감을 동시에 잡은 슈즈", "timestamp": "06:05", "youtube_url": "https://www.youtube.com/results?search_query=주우재+젤+카야노+14"},
    {"name": "포터 탱커 숄더백 블랙", "keyword": "가방", "youtuber": "오늘의 주우재", "reason": "가벼운 나일론 소재와 넉넉한 수납 포켓으로 데일리 캐주얼 룩에 잘 어울리는 가방", "timestamp": "05:18", "youtube_url": "https://www.youtube.com/results?search_query=주우재+포터+탱커+가방"},
    {"name": "젠틀몬스터 릭 01 선글라스", "keyword": "선글라스", "youtuber": "오늘의 주우재", "reason": "유행을 타지 않는 깔끔한 스퀘어 아세테이트 프레임으로 얼굴형을 보완하는 선글라스", "timestamp": "07:40", "youtube_url": "https://www.youtube.com/results?search_query=주우재+젠틀몬스터+선글라스"},

    # 5. 디에디트 THE EDIT
    {"name": "소니 WH-1000XM5 노이즈캔슬링 헤드폰", "keyword": "헤드폰", "youtuber": "디에디트 THE EDIT", "reason": "가벼운 착용감과 업계 최고 수준의 소음 차단 성능을 보여주는 출퇴근·작업용 헤드폰", "timestamp": "06:18", "youtube_url": "https://www.youtube.com/results?search_query=디에디트+WH-1000XM5"},
    {"name": "이솝 레저렉션 아로마틱 핸드 밤", "keyword": "핸드크림", "youtuber": "디에디트 THE EDIT", "reason": "상큼한 시트러스 우디 향과 끈적임 없이 스며드는 보습력을 갖춘 데스크 필수 핸드밤", "timestamp": "03:12", "youtube_url": "https://www.youtube.com/results?search_query=디에디트+이솝+핸드크림"},
    {"name": "모슈 라떼 텀블러 450ml", "keyword": "텀블러", "youtuber": "디에디트 THE EDIT", "reason": "우유병을 닮은 감성적인 디자인과 뛰어난 보온·보냉력을 갖춘 사무실용 텀블러", "timestamp": "04:50", "youtube_url": "https://www.youtube.com/results?search_query=디에디트+모슈+텀블러"},
    {"name": "보스 사운드링크 플렉스 블루투스 스피커", "keyword": "스피커", "youtuber": "디에디트 THE EDIT", "reason": "방수·방진 설계와 눕히거나 세워도 균형 잡힌 사운드를 들려주는 휴대용 스피커", "timestamp": "08:05", "youtube_url": "https://www.youtube.com/results?search_query=디에디트+보스+사운드링크+플렉스"},
    {"name": "킨토 트래블 텀블러 350ml", "keyword": "텀블러", "youtuber": "디에디트 THE EDIT", "reason": "360도 어느 방향에서나 편하게 마실 수 있고 미니멀한 색감이 매력적인 텀블러", "timestamp": "02:44", "youtube_url": "https://www.youtube.com/results?search_query=디에디트+킨토+텀블러"},

    # 6. 주연 ZUYONI
    {"name": "애플 에어팟 프로 2세대 USB-C", "keyword": "이어폰", "youtuber": "주연 ZUYONI", "reason": "아이폰·맥북 간 매끄러운 기기 전환과 강력한 적응형 노이즈캔슬링을 지원하는 이어폰", "timestamp": "03:20", "youtube_url": "https://www.youtube.com/results?search_query=주연+에어팟+프로+2"},
    {"name": "오즈모 포켓 3 크리에이터 콤보", "keyword": "카메라", "youtuber": "주연 ZUYONI", "reason": "1인치 센서와 3축 짐벌이 결합되어 브이로그와 여행 촬영에 최적화된 초소형 카메라", "timestamp": "05:12", "youtube_url": "https://www.youtube.com/results?search_query=주연+오즈모+포켓+3"},
    {"name": "모프트 스냅온 맥세이프 카드지갑 스탠드", "keyword": "카드지갑", "youtuber": "주연 ZUYONI", "reason": "카드 수납과 가로·세로 스마트폰 거치를 초슬림 두께로 해결하는 맥세이프 액세서리", "timestamp": "02:05", "youtube_url": "https://www.youtube.com/results?search_query=주연+모프트+맥세이프+카드지갑"},
    {"name": "로지텍 MX Keys Mini 무선 키보드", "keyword": "키보드", "youtuber": "주연 ZUYONI", "reason": "텐키리스 미니 배열과 손끝에 감기는 펜타그래프 키감으로 휴대성과 타건감을 잡은 키보드", "timestamp": "06:40", "youtube_url": "https://www.youtube.com/results?search_query=주연+MX+Keys+Mini"},
    {"name": "소니 ZV-E10 II 미러리스 카메라", "keyword": "카메라", "youtuber": "주연 ZUYONI", "reason": "가벼운 무게와 빠른 인물 AF, 시네마틱 브이로그 모드를 탑재한 입문용 영상 카메라", "timestamp": "09:15", "youtube_url": "https://www.youtube.com/results?search_query=주연+ZV-E10"},

    # 7. 뻘짓연구소
    {"name": "AMD 라이젠 7 7800X3D 프로세서", "keyword": "CPU", "youtuber": "뻘짓연구소", "reason": "압도적인 3D V-Cache 성능으로 게이밍 PC 견적에서 최고 효율을 보여주는 CPU", "timestamp": "04:10", "youtube_url": "https://www.youtube.com/results?search_query=뻘짓연구소+7800X3D"},
    {"name": "녹투아 NF-A12x25 PWM 쿨링팬", "keyword": "쿨링팬", "youtuber": "뻘짓연구소", "reason": "정숙한 소음 대비 뛰어난 풍압으로 PC 케이스와 라디에이터 소음을 잡아주는 명품 쿨러", "timestamp": "07:25", "youtube_url": "https://www.youtube.com/results?search_query=뻘짓연구소+녹투아+A12x25"},
    {"name": "LG 울트라기어 27GR93U 4K 게이밍 모니터", "keyword": "모니터", "youtuber": "뻘짓연구소", "reason": "4K 고해상도와 144Hz 고주사율 IPS 패널을 균형 있게 갖춘 작업·게임 겸용 모니터", "timestamp": "05:50", "youtube_url": "https://www.youtube.com/results?search_query=뻘짓연구소+27GR93U"},
    {"name": "슈퍼플라워 SF-850F14XG LEADEX VII 파워", "keyword": "파워서플라이", "youtuber": "뻘짓연구소", "reason": "ATX 3.0 규격 지원과 칼전압 출력, 낮은 리플 노이즈로 안정성이 검증된 파워서플라이", "timestamp": "08:30", "youtube_url": "https://www.youtube.com/results?search_query=뻘짓연구소+슈퍼플라워+850W"},
    {"name": "앱코 무접점 키보드 KN10", "keyword": "키보드", "youtuber": "뻘짓연구소", "reason": "보글거리는 특유의 정전용량 무접점 키감을 합리적인 가격에 경험할 수 있는 키보드", "timestamp": "03:48", "youtube_url": "https://www.youtube.com/results?search_query=뻘짓연구소+무접점+키보드"},
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

/* Streamlit 기본 알림창까지 강제 라이트 처리 */
div[data-testid="stAlertContainer"],
div[data-testid="stAlert"],
div[role="alert"] {
    background-color: #E8F3FF !important;
    border: 1px solid #C9E0FF !important;
    border-radius: 14px !important;
    color: #191F28 !important;
}
div[data-testid="stAlertContainer"] *,
div[data-testid="stAlert"] *,
div[role="alert"] * {
    color: #191F28 !important;
    -webkit-text-fill-color: #191F28 !important;
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
    color: #4E5968 !important;
    min-height: 36px !important;
    padding: 4px 10px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"] p {
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

# === 절대 깨지지 않는 밝은 HTML 상태 배너 (글씨 씹힘 원천 차단) ===
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

# === 비상품(챌린지/이벤트/프로모션/문장) 차단 ===
NON_PRODUCT_KEYWORDS = (
    "인트로", "오프닝", "마무리", "아웃트로", "총평", "결론", "구독", "이벤트",
    "당첨", "발표", "공지", "커뮤니티", "종료", "마감", "쿠키", "예고", "목차",
    "근황", "소감", "질문", "후기", "원칙", "고능", "PD", "피디", "출연",
    "브이로그", "일상", "추천", "꿀템", "필수템", "가성비템", "모아옴", "모음",
    "총정리", "하이라이트", "문의", "비즈니스", "협찬", "광고", "인스타", "유튜브",
    "채널", "타임라인", "챕터", "링크", "바로가기", "프로필", "멤버십",
    "할인코드", "쿠폰", "최종가", "할인가", "혜택가", "정상가", "체감가",
    "해외직구", "직구", "로컬", "카테고리", "적용", "카드", "결제", "무료배송",
    "진행기간", "한국시간", "항공권", "숙박", "예약", "고르는", "방법", "비교",
    "배송", "소요", "선택해서", "구매하세요", "포함되어", "미포함", "옵션",
    "챌린지", "장바구니", "신규회원", "전용", "원딜", "광군제", "블프", "세일",
    "free download", "watch more", "ncs", "stream", "download"
)

def is_non_product(text, youtuber=""):
    t = (text or "").strip()
    t_low = t.lower()
    if not t or len(t) < 2 or len(t) > 45:
        return True
    if t[0] in ("=", "👉", "※", "→", "▶", "|", "-", "•", "🎉", "🔥", "✈️", "⚠️") or "?" in t or "!" in t:
        return True
    if re.search(r"(?:합니다|입니다|됩니다|있습니다|없습니다|않습니다|하세요|주세요|구매하세요|바랍니다|해요|예요|이에요|에요|가요|네요|같아요|되네|안해|소요|가능|불가|제외|ㄷㄷ|ㅋㅋ|ㅎㅎ|ㅠㅠ)$", t):
        return True
    if re.search(r"(?:같은|하는|되는|있는|없는|빠지는|넘어질|살펴볼|알아볼|고르는|포함되어)\s", t):
        return True
    if t.endswith((" 제품", " 상품", " 아이템", " 추천", " 후기", " 리뷰", " 소개", " 챌린지", " 원딜", " 딜")):
        return True
    if re.match(r"^(?:그래서|왜|어떻게|가장|제일|진짜|정말|드디어|이제|오늘|이번|옵션을|신규회원)\s", t):
        return True
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*일\s*\([월화수목금토일]\)|\d{1,2}\s*시\s*\d{0,2}|\d+\s*[-~]\s*\d+\s*일", t):
        return True
    if re.fullmatch(r"(?:약\s*)?(?:USD|KRW|US\$|\$|₩)?\s*[\d,\.]+\s*(?:원|달러|불|USD|KRW|%)?", t, re.IGNORECASE):
        return True
    if re.match(r"^(?:약\s*)?[\$\₩]\s*\d", t):
        return True
    if re.fullmatch(r"[\(\[\{〈《「『].*[\)\]\}\〉》」』]", t):
        return True
    if t.count("(") != t.count(")") or t.count("[") != t.count("]"):
        return True
    if len(re.findall(r"[가-힣A-Za-z0-9]", t)) < 2:
        return True
    if any(w in t_low for w in NON_PRODUCT_KEYWORDS):
        return True
    return False

def pick_icon_style(name, keyword):
    text = f"{name} {keyword}".lower()
    if any(k in text for k in ("헤드폰", "이어폰", "airpods", "스피커", "오디오", "마이크")):
        return "🎧", "#EEF4FF"
    if any(k in text for k in ("배터리", "충전", "케이블", "어댑터", "멀티탭", "파워")):
        return "🔋", "#E8F8F0"
    if any(k in text for k in ("키보드", "마우스", "노트북", "모니터", "태블릿", "맥북", "거치대", "책상", "데스크", "ssd", "라이젠", "쿨링팬")):
        return "💻", "#F3EEFF"
    if any(k in text for k in ("카메라", "액션캠", "고프로", "삼각대", "조명", "오즈모", "미러리스")):
        return "📷", "#FFF4E5"
    if any(k in text for k in ("크림", "선크림", "클렌징", "멀티밤", "가습", "청소기", "매트", "담요", "난로", "양말", "히터", "제습", "토스터", "에어랩", "핸드")):
        return "🏠", "#FFEFF4"
    if any(k in text for k in ("지갑", "케이스", "백팩", "가방", "트렁크", "여행", "스니커즈", "신발", "운동화", "티셔츠", "선글라스", "텀블러")):
        return "🎒", "#EBF8FF"
    return "🛍️", "#F2F4F6"

def save_items(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def load_items():
    existing = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # 1) 기존 DB에서 챌린지·할인문구 등 오류 데이터 자동 숙청
    cleaned = [x for x in existing if not is_non_product(x.get("name", ""), x.get("youtuber", ""))]

    # 2) 대표 유튜버 전체 큐레이션 DB가 빠져있으면 자동으로 한 번에 병합
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in cleaned}
    changed = (len(cleaned) != len(existing))
    for seed in CURATED_YOUTUBER_DB:
        key = (seed["name"].strip().lower(), seed["youtuber"].strip().lower())
        if key not in seen:
            cleaned.append(dict(seed))
            seen.add(key)
            changed = True

    if changed or not os.path.exists(DB_FILE):
        save_items(cleaned)
    return cleaned

def add_unique_items(new_items):
    db = load_items()
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in db}
    added = []
    for item in new_items:
        key = (item.get("name", "").strip().lower(), item.get("youtuber", "").strip().lower())
        if key[0] and key not in seen and not is_non_product(item.get("name", ""), item.get("youtuber", "")):
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
                    cid = ""
                    if o_runs:
                        cid = o_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                    nav_url = vr.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
                    is_short = force_shorts or ("/shorts/" in nav_url)
                    items.append({
                        "video_id": vid,
                        "title": t_runs[0].get("text", "제목 없음") if t_runs else "제목 없음",
                        "youtuber": o_runs[0].get("text", default_youtuber) if o_runs else default_youtuber,
                        "channel_id": cid or default_channel_id,
                        "is_shorts": is_short,
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
        "transcript": transcript[:4500],
        "is_shorts": is_shorts,
    }

# === Gemini AI 전용 정밀 추출 (엉터리 정규식 스크래퍼 폐기) ===
def analyze_batch_with_gemini(bundles):
    api_key = get_api_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("Gemini API 키가 필요합니다. [설정] 탭에서 키를 저장해 주세요.")

    shorts_map = {b["video_id"]: b.get("is_shorts", False) for b in bundles}
    blocks = []
    for b in bundles:
        kind = "유튜브 숏츠(Shorts)" if b.get("is_shorts") else "일반 영상"
        blocks.append(
            f"=== VIDEO_ID: {b['video_id']} | TYPE: {kind} | YOUTUBER: {b['youtuber']} ===\n"
            f"[영상 제목] {b['title']}\n"
            f"[설명란]\n{b['desc'][:2000]}\n"
            f"[영상 자막(대본)]\n{b['transcript']}"
        )

    prompt = f"""너는 유튜브 쇼핑 큐레이터야. 아래 영상(일반 영상 및 Shorts 포함)의 [설명란]과 [영상 자막]을 모두 읽고, 실제로 네이버 쇼핑이나 쿠팡에서 검색해 구매할 수 있는 **'진짜 제품명(브랜드명 + 정확한 상품명)'**만 골라서 JSON 배열로 답해줘.

절대 규칙:
1. 이벤트·챌린지·프로모션 문구("11초 장바구니 챌린지", "신규회원 전용 1000원딜", "그래서 얼마에요", "배송 10-14일 소요", "Free Download/Stream")는 절대 넣지 마.
2. 자막과 설명란을 대조해 실제 소개된 **브랜드와 정확한 제품명**만 적어줘. 브랜드·모델명이 불분명하면 과감히 버려.
3. 키 이름: "video_id", "youtuber", "name"(쇼핑몰 검색용 정확한 브랜드+제품명), "keyword"(품목명), "reason"(추천 이유 한 줄 요약), "start_sec"(등장 시작 초 정수, 모르면 0)

{chr(10).join(blocks)}"""

    client = genai.Client(api_key=api_key, http_options={"timeout": 25000})
    last_err = None
    res = None
    for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            break
        except Exception as e:
            last_err = e

    if res is None:
        raise RuntimeError(f"Gemini API 호출 실패: {last_err}")

    cleaned = re.sub(r"^```json|```$", "", res.text.strip()).strip()
    out = []
    for item in json.loads(cleaned):
        vid = item.get("video_id") or bundles[0]["video_id"]
        is_shorts = shorts_map.get(vid, False)
        sec = int(item.get("start_sec", 0))
        mm, ss = divmod(sec, 60)
        name = item.get("name", "").strip()
        yt = item.get("youtuber", bundles[0]["youtuber"]).strip()
        if name and not is_non_product(name, yt):
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

    items = analyze_batch_with_gemini(bundles)
    added = add_unique_items(items)
    return added, len(bundles)

def render_toss_card(item, idx):
    icon, bg_color = pick_icon_style(item.get("name", ""), item.get("keyword", ""))
    is_shorts = item.get("is_shorts") or item.get("timestamp") == "Shorts" or "/shorts/" in item.get("youtube_url", "")
    badge_html = "<span class='shorts-badge'>Shorts</span>" if is_shorts else ""
    meta_text = f"{item['youtuber']} · {'쇼츠 추천' if is_shorts else item['timestamp'] + ' 등장'}"

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
    <div style="font-size:13px; font-weight:600; color:#8B95A1;">유튜버 추천템</div>
</div>
""", unsafe_allow_html=True)

# === 상단 요약 대시보드 카드 ===
fill_pct = min(100, int((len(db) / 100) * 100)) if db else 0
st.markdown(f"""
<div class="hero-card">
    <div class="hero-label">모아둔 유튜버 추천 꿀템</div>
    <div class="hero-big">{len(db):,}개</div>
    <div class="hero-dots">
        <div><span class="dot-blue">●</span>유튜버 <b>{yt_count}명</b></div>
        <div><span class="dot-green">●</span>최저가 비교 <b style="color:#3182F6;">실시간 연동</b></div>
    </div>
    <div class="hero-bar-box">
        <div class="hero-bar-top">
            <span>목표 DB 100개</span>
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
    c_search, c_filter = st.columns([1.65, 1])
    kw = c_search.text_input("검색", placeholder="🔍 찾는 물건 입력 (예: 보조배터리)", label_visibility="collapsed")
    sel_yt = c_filter.selectbox("유튜버", yts, label_visibility="collapsed")

    filtered = [i for i in db if sel_yt == "전체 유튜버" or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "")).lower()]

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
            st.markdown("<div class='item-name'>표시할 추천템이 없어요</div><div class='item-reason'>필터를 '전체 유튜버'로 변경해 보세요.</div>", unsafe_allow_html=True)

elif st.session_state.nav == "자동 수집":
    # 1) 대표 유튜버 전체 DB 일괄 받기 / AI 최신화 카드
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:4px;'>🌐 대표 유튜버 전체 추천템 한 번에 받기</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='item-reason' style='margin-bottom:12px;'>{', '.join(FEATURED_YOUTUBERS)}의 검증된 추천템 전체 데이터를 한 번에 저장해요.</div>", unsafe_allow_html=True)
        if st.button("✨ 전체 유튜버 데이터 한 번에 저장하기", type="primary", use_container_width=True):
            status_all = st.empty()
            added_seed = add_unique_items(CURATED_YOUTUBER_DB)
            if get_api_key():
                total_ai = []
                for idx_yt, yt_name in enumerate(FEATURED_YOUTUBERS, start=1):
                    render_banner(status_all, f"[{idx_yt}/{len(FEATURED_YOUTUBERS)}] '{yt_name}' 공식 채널 최신 영상·숏츠 AI 분석 중...", "info")
                    try:
                        added_yt, _ = collect_for_query(yt_name, limit=3, only_official=True)
                        total_ai.extend(added_yt)
                    except Exception:
                        pass
                render_banner(status_all, f"완료! 대표 유튜버 추천템이 DB에 모두 저장되었어요. (신규 추가 {len(added_seed) + len(total_ai)}건)", "success")
            else:
                render_banner(status_all, f"완료! 대표 유튜버 7인의 검증된 추천템 전체({len(load_items())}건)가 저장되었어요.", "success")

    # 2) 개별 유튜버 추가 AI 정밀 수집 카드
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>🤖 특정 유튜버 최신 영상·숏츠 AI 추가 수집</div>", unsafe_allow_html=True)
        st.markdown("<div class='item-reason' style='margin-bottom:10px;'>AI가 자막과 설명란을 대조해 실제 브랜드·제품명만 정확히 뽑아냅니다.</div>", unsafe_allow_html=True)

        if not get_api_key():
            render_banner(None, "💡 신규 영상·숏츠를 AI로 분석하려면 [설정] 탭에서 Gemini API 키를 저장해 주세요.", "warning")

        st.markdown("<div class='field-label'>유튜버 이름</div>", unsafe_allow_html=True)
        q_in = st.text_input("키워드", placeholder="예: 오늘의 주우재, 잇섭, 테크몽, 가전주부", label_visibility="collapsed")

        only_official = st.checkbox("🎯 대표 유튜버 공식 채널만 수집 (타 채널·클립 제외)", value=True)

        st.markdown("<div class='field-label'>분석할 최신 영상·숏츠 수</div>", unsafe_allow_html=True)
        lim = st.slider("영상 수", 1, 10, 5, label_visibility="collapsed")

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 AI 정밀 수집 시작하기", type="primary", use_container_width=True) and q_in:
            status = st.empty()
            if not get_api_key():
                render_banner(status, "⚠️ Gemini API 키가 설정되지 않았습니다. [설정] 탭에서 API 키를 먼저 입력해 주세요.", "error")
            else:
                try:
                    render_banner(status, "1/2 대표 유튜버 공식 채널의 영상·숏츠를 불러오고 있어요...", "info")
                    videos = search_youtube_videos(q_in, limit=int(lim), only_official=only_official)
                    analyzed = {extract_video_id(i.get("youtube_url", "")) for i in load_items()}
                    targets = [v for v in videos if v["video_id"] not in analyzed]
                    if not targets:
                        render_banner(status, "이미 모두 수집한 영상들이거나 일치하는 공식 채널 영상이 없어요.", "info")
                    else:
                        bundles = []
                        for v in targets:
                            b = fetch_video_bundle(v["video_id"], v["youtuber"], v["title"], is_shorts=v.get("is_shorts", False))
                            if only_official and not _is_channel_match(q_in, b["youtuber"]):
                                continue
                            bundles.append(b)
                        render_banner(status, f"2/2 AI가 영상·숏츠 {len(bundles)}개의 자막을 분석해 진짜 제품명만 추출하고 있어요...", "info")
                        items = analyze_batch_with_gemini(bundles)
                        added = add_unique_items(items)
                        render_banner(status, f"완료! 실제 제품 {len(added)}개가 새로 추가되었어요.", "success")
                        for a in added:
                            st.write(f"• **{a['name']}** ({a['youtuber']} · `{a['timestamp']}`)")
                except Exception as e:
                    render_banner(status, f"수집 중 오류가 발생했어요: {e}", "error")

elif st.session_state.nav == "설정":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>🔑 Gemini API 키 설정</div><div class='item-reason' style='margin-bottom:12px;'>신규 유튜브 영상·숏츠의 자막을 AI로 분석할 때 사용해요.</div>", unsafe_allow_html=True)
        new_key = st.text_input("API 키", type="password", placeholder="AIzaSy...", label_visibility="collapsed")
        if st.button("API 키 저장", type="primary", use_container_width=True) and new_key.strip():
            open(KEY_FILE, "w", encoding="utf-8").write(new_key.strip())
            render_banner(None, "새 Gemini API 키가 저장되었어요!", "success")

    with st.container(border=True):
        st.markdown(f"<div class='item-name' style='margin-bottom:6px;'>🗂️ 데이터 관리</div><div class='item-reason' style='margin-bottom:12px;'>현재 저장된 추천템은 총 <b>{len(db)}개</b>입니다.</div>", unsafe_allow_html=True)
        if st.button("🔄 대표 유튜버 7인 추천템 DB 다시 채우기", type="primary", use_container_width=True):
            save_items(list(CURATED_YOUTUBER_DB))
            st.rerun()
# === 여기까지 복사되면 끝 ===
