import html
import json
import re
from collections import Counter

MAX_CURATED_PRODUCTS = 300
AUTO_APPROVE_MIN_SCORE = 80

CATEGORIES = ["IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행", "자동차", "운동·건강", "육아", "반려동물", "기타"]
IMAGE_SOURCES = ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"]
IMAGE_SOURCE_LABELS = {
    "": "출처 미선택",
    "brand_official": "브랜드 공식",
    "affiliate": "제휴사 제공",
    "manual": "직접 확인",
    "youtube_thumbnail": "유튜브 썸네일",
}
CATEGORY_VISUALS = {
    "IT·전자": ("IT", "#EEF3FA", "#335C99"),
    "뷰티": ("BEAUTY", "#FBF1EC", "#9E532B"),
    "패션": ("FASHION", "#F3EFFB", "#5E439C"),
    "생활·살림": ("LIVING", "#EDF6F1", "#266B4E"),
    "주방": ("KITCHEN", "#FAF4E6", "#8C5B0E"),
    "여행": ("TRAVEL", "#EBF5F7", "#20626E"),
    "자동차": ("AUTO", "#EFF1F4", "#475261"),
    "운동·건강": ("HEALTH", "#FAEEEE", "#963333"),
    "육아": ("KIDS", "#FAF2EA", "#99531D"),
    "반려동물": ("PET", "#F2F5EA", "#566624"),
    "기타": ("PICK", "#F1F3F6", "#525E6C"),
}
INVALID_POINT_PATTERNS = (
    "원문에", "명시됨", "후기는 없음", "후기 없음", "언급 없음",
    "정보가 없음", "확인되지 않", "알 수 없", "단점 없음", "장점 없음",
    "해당 없음", "내용 없음", "특이사항 없음",
)
GENERIC_BRAND_KEYS = {
    "대기업", "중소기업", "가성비", "추천템", "인기템", "꿀템", "필수템",
    "기타", "미상", "알수없음", "무명", "브랜드", "제품", "상품",
}
HOLLOW_COPY_REGEX = re.compile(
    r"(에\s*사용된|에서\s*소개된|에서\s*추천한|에서\s*언급된|에서\s*리뷰한|으로\s*구매한|직접\s*구매\s*제품|추천\s*제품|소개\s*제품|언급\s*제품|리뷰\s*제품|협찬\s*제품|제공\s*제품)$"
)
SEARCH_SYNONYMS = {
    "태블릿": ["pad", "탭", "아이패드", "갤럭시탭", "tablet"],
    "노트북": ["laptop", "맥북", "macbook", "그램", "갤럭시북"],
    "이어폰": ["버즈", "에어팟", "earbuds", "earphone"],
    "헤드폰": ["헤드셋", "headphone", "headset"],
    "청소기": ["다이슨", "dyson", "로봇청소기", "물걸레"],
    "키보드": ["keyboard"],
    "마우스": ["mouse"],
    "보조배터리": ["파워뱅크", "powerbank", "맥세이프"],
    "패딩": ["다운", "푸퍼", "파카", "점퍼", "down", "puffer", "parka"],
    "가방": ["백", "숄더백", "토트백", "크로스백", "핸드백", "에코백", "백팩", "bag"],
    "신발": ["스니커즈", "운동화", "로퍼", "부츠", "구두", "슬리퍼", "샌들", "shoes", "sneakers"],
}

# 전 카테고리 세부 품목군 매칭 테이블 (상세페이지 연관 추천템 정확도 향상용)
ITEM_GROUPS = (
    ("음향기기", ("헤드폰", "헤드셋", "이어폰", "버즈", "에어팟", "스피커", "사운드바", "앰프", "dac", "이어팁", "headphone", "headset", "earbuds", "earphone", "speaker")),
    ("태블릿", ("태블릿", "아이패드", "갤럭시탭", "울트라패드", "미니패드", "패드", "ipad", "tablet", "pad")),
    ("노트북·PC", ("노트북", "맥북", "그램", "갤럭시북", "미니pc", "데스크탑", "laptop", "macbook")),
    ("모니터", ("모니터", "디스플레이", "포터블모니터", "monitor", "display")),
    ("키보드·마우스", ("키보드", "마우스", "트랙패드", "장패드", "keyboard", "mouse")),
    ("충전·배터리", ("보조배터리", "충전기", "멀티탭", "맥세이프", "파워뱅크", "케이블", "어댑터", "charger", "powerbank")),
    ("스마트워치", ("스마트워치", "애플워치", "갤럭시워치", "미밴드", "워치", "watch")),
    ("카메라·촬영장비", ("카메라", "짐벌", "액션캠", "삼각대", "마이크", "조명", "오즈모", "고프로", "웹캠", "camera", "gimbal")),
    ("아이·브로우 메이크업", ("아이라이터", "아이라이너", "아이섀도우", "섀도우", "팔레트", "마스카라", "아이브로우", "브로우", "애교살", "글리터", "속눈썹", "뷰러", "eyeliner", "shadow", "mascara", "brow")),
    ("립·치크 메이크업", ("립", "틴트", "립스틱", "립밤", "립글로스", "립오일", "립펜슬", "푸딩팟", "블러셔", "치크", "하이라이터", "쉐딩", "셰딩", "컨투어", "tint", "lip", "blush", "cheek", "highlighter")),
    ("베이스 메이크업", ("쿠션", "파운데이션", "컨실러", "파우더", "팩트", "프라이머", "비비크림", "톤업크림", "cushion", "foundation", "concealer", "powder")),
    ("스킨·선케어", ("선크림", "선스틱", "썬크림", "선쿠션", "토너", "스킨", "세럼", "앰플", "에센스", "로션", "수분크림", "크림", "클렌징", "폼클렌징", "클렌징오일", "클렌징밤", "마스크팩", "필링", "패드", "sunscreen", "toner", "serum", "cream", "cleansing")),
    ("헤어·바디·향수", ("샴푸", "트리트먼트", "헤어에센스", "헤어오일", "헤어팩", "드라이기", "고데기", "바디워시", "바디로션", "핸드크림", "향수", "퍼퓸", "미스트", "shampoo", "perfume")),
    ("청소·생활가전", ("청소기", "로봇청소기", "공기청정기", "가습기", "제습기", "선풍기", "서큘레이터", "온풍기", "다리미", "스팀다리미", "면도기", "전동칫솔", "다이슨")),
    ("수납·생활용품", ("수납", "정리함", "행거", "바구니", "빨래", "건조대", "세제", "섬유유연제", "탈취제", "디퓨저", "캔들", "베개", "이불", "매트리스", "타월", "수건")),
    ("주방가전·용품", ("커피머신", "에스프레소", "에어프라이어", "블렌더", "믹서기", "전기포트", "토스터", "텀블러", "보온병", "프라이팬", "냄비", "밀폐용기", "식기", "수저", "칼", "도마")),
    ("가방·파우치", ("가방", "백팩", "숄더백", "토트백", "크로스백", "에코백", "핸드백", "파우치", "카드지갑", "지갑", "캐리어", "bag", "backpack", "pouch", "wallet")),
    ("신발", ("신발", "스니커즈", "운동화", "러닝화", "런닝화", "로퍼", "구두", "부츠", "슬리퍼", "샌들", "뮬", "슈즈", "shoes", "sneakers")),
    ("아우터", ("패딩", "다운", "자켓", "재킷", "코트", "점퍼", "바람막이", "가디건", "후리스", "플리스", "베스트", "조끼", "jacket", "coat")),
    ("상의·하의", ("티셔츠", "셔츠", "블라우스", "맨투맨", "후드", "니트", "스웨터", "바지", "팬츠", "데님", "청바지", "슬랙스", "스커트", "원피스")),
    ("패션잡화", ("모자", "볼캡", "비니", "안경", "선글라스", "벨트", "머플러", "스카프", "양말", "시계", "목걸이", "반지", "귀걸이")),
    ("영양제·건강식품", ("유산균", "비타민", "오메가3", "마그네슘", "루테인", "콜라겐", "단백질", "프로틴", "효소", "홍삼", "영양제", "보조제")),
    ("운동·홈트용품", ("덤벨", "아령", "요가매트", "폼롤러", "밴드", "마사지건", "마사지기", "러닝", "등산", "골프", "테니스")),
    ("차량용품", ("블랙박스", "차량용", "세차", "방향제", "거치대", "하이패스", "와이퍼", "코일매트")),
    ("여행·캠핑", ("텐트", "캠핑", "체어", "랜턴", "침낭", "목베개", "압축파우치")),
    ("육아·유아용품", ("기저귀", "물티슈", "젖병", "유모차", "카시트", "아기띠", "분유", "이유식", "장난감", "유아")),
    ("반려동물용품", ("사료", "간식", "배변패드", "모래", "캣타워", "하네스", "리드줄", "강아지", "고양이")),
)

EXTRA_MALLS = ("naver", "oliveyoung", "musinsa", "29cm", "zigzag", "ably")
MALL_META = {
    "naver": {
        "label": "네이버쇼핑",
        "short": "네이버쇼핑",
        "css": "shop-btn-naver",
        "badge_css": "mall-pill-naver",
        "benefit": "네이버페이 포인트 적립 · 스마트스토어/백화점 가격비교",
    },
    "coupang": {
        "label": "쿠팡 검색",
        "short": "쿠팡",
        "css": "shop-btn-coupang",
        "badge_css": "mall-pill-coupang",
        "benefit": "로켓배송 · 와우회원 무료배송 및 빠른 반품",
    },
    "oliveyoung": {
        "label": "올리브영",
        "short": "올리브영",
        "css": "shop-btn-oliveyoung",
        "badge_css": "mall-pill-oliveyoung",
        "benefit": "오늘드림 당일배송 · 올리브영 공식 멤버십 혜택",
    },
    "musinsa": {
        "label": "무신사",
        "short": "무신사",
        "css": "shop-btn-musinsa",
        "badge_css": "mall-pill-musinsa",
        "benefit": "무신사 전 상품 무료배송 · 회원 등급 할인",
    },
    "29cm": {
        "label": "29CM",
        "short": "29CM",
        "css": "shop-btn-29cm",
        "badge_css": "mall-pill-29cm",
        "benefit": "감도 깊은 셀렉트샵 · 쿠폰 및 적립금 혜택",
    },
    "zigzag": {
        "label": "지그재그",
        "short": "지그재그",
        "css": "shop-btn-zigzag",
        "badge_css": "mall-pill-zigzag",
        "benefit": "직진배송 빠른도착 · 스토어 통합 결제",
    },
    "ably": {
        "label": "에이블리",
        "short": "에이블리",
        "css": "shop-btn-ably",
        "badge_css": "mall-pill-ably",
        "benefit": "전 상품 무료배송 · 앱 전용 할인 쿠폰",
    },
}
AFFILIATE_DISCLOSURE = (
    "에디션 픽은 쿠팡 파트너스, 네이버 쇼핑 커넥트, 올리브영 쇼핑 큐레이터 등 "
    "제휴 마케팅 활동의 일환으로, 링크를 통한 구매 시 일정액의 수수료를 제공받을 수 있습니다."
)


def safe(value):
    return html.escape(str(value or ""), quote=True)


def norm_key(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def clean_evidence_text(value):
    text = re.sub(r"https?://\S+", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" ·,-/")
    return text


def format_korean_count(value):
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n >= 10000:
        man = n / 10000
        return f"{man:.1f}만".rstrip("0").rstrip(".")
    if n >= 1000:
        cheon = n / 1000
        return f"{cheon:.1f}천".rstrip("0").rstrip(".")
    return f"{n:,}"


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


def is_meaningful_point(text):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip()).strip(" .·,-")
    if len(cleaned) < 3:
        return False
    if any(pattern in cleaned for pattern in INVALID_POINT_PATTERNS):
        return False
    if HOLLOW_COPY_REGEX.search(cleaned):
        return False
    return True


def has_valid_brand_and_model(product):
    brand = str(product.get("brand") or "").strip()
    model = str(product.get("model") or "").strip()
    b_key = norm_key(brand)
    m_key = norm_key(model)
    if len(b_key) < 1 or len(m_key) < 2:
        return False
    if b_key in GENERIC_BRAND_KEYS or m_key in GENERIC_BRAND_KEYS:
        return False
    if b_key == m_key:
        return False
    return True


def is_auto_approvable_product(product, recommendations=None):
    """식별 점수 80점 이상 + 브랜드/모델명 완비 + 유효 리뷰 근거 보유 여부 판별."""
    try:
        score = float(product.get("identification_score") or 0)
    except (TypeError, ValueError):
        score = 0
    if score < AUTO_APPROVE_MIN_SCORE:
        return False
    if not has_valid_brand_and_model(product):
        return False
    recs = recommendations if recommendations is not None else (product.get("recommendations") or [])
    if recs:
        summary = recommendation_summary(recs)
        if not (summary["pros"] or summary["cons"] or summary["reasons"]):
            return False
    return True


def passes_quality_gate(product):
    """홈 카탈로그 노출을 위한 기본 자격 필터 (과락 기준)."""
    recs = product.get("recommendations") or []
    if not recs:
        return False
    if not product.get("_has_quality_copy"):
        return False
    if not has_valid_brand_and_model(product):
        return False

    channel_count = int(product.get("_channel_count") or 0)
    raw_score = product.get("identification_score")
    if raw_score is not None and str(raw_score).strip() != "":
        try:
            id_score = float(raw_score)
            if id_score < AUTO_APPROVE_MIN_SCORE and channel_count < 2:
                return False
        except (TypeError, ValueError):
            pass
    return True


def compute_curation_score(product):
    """내돈내산 최우선 · 유료광고 캠페인 후순위 · 리뷰 깊이 반영 큐레이션 점수."""
    recs = product.get("recommendations") or []
    channel_count = int(
