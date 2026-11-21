import os

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MIN_SUBSCRIBERS = int(os.getenv("MIN_SUBSCRIBERS", "1000000"))
DISCOVERY_QUERY_LIMIT = int(os.getenv("DISCOVERY_QUERY_LIMIT", "12"))
VIDEOS_PER_CHANNEL = int(os.getenv("VIDEOS_PER_CHANNEL", "20"))

DISCOVERY_QUERIES = [
    "올리브영 추천템", "화장품 내돈내산", "메이크업 제품 추천", "스킨케어 추천",
    "IT 제품 리뷰", "스마트폰 사용기", "노트북 추천", "데스크테리어 추천템",
    "패션 하울", "신발 추천", "가방 추천", "남자 패션 추천",
    "살림 추천템", "자취 필수템", "주방용품 추천", "삶의 질 아이템",
    "여행 필수템", "캐리어 추천", "차량용품 추천", "자동차 용품 리뷰",
    "육아템 추천", "아기용품 리뷰", "강아지 용품 추천", "고양이 용품 추천",
    "운동 장비 추천", "홈트 기구 리뷰",
]
