import os
import re
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SCORE_BATCH_SIZE = int(os.getenv("SCORE_BATCH_SIZE", "300"))
MIN_QUEUE_SCORE = int(os.getenv("MIN_QUEUE_SCORE", "35"))

STRONG_POSITIVE_KEYWORDS = (
    "내돈내산", "추천템", "꿀템", "잘산템", "인생템", "정착템", "최애템", "재구매",
    "리뷰", "후기", "언박싱", "하울", "비교", "가성비", "장바구니", "필수템",
    "왓츠인마이백", "파우치", "데스크셋업", "살림템", "뷰티템", "패션템",
    "올영", "올리브영", "무신사", "쿠팡", "다이소", "이케아", "컬리",
)

PRODUCT_HINT_KEYWORDS = (
    "노트북", "태블릿", "아이패드", "갤럭시", "에어팟", "버즈", "이어폰", "헤드폰",
    "키보드", "마우스", "모니터", "충전기", "보조배터리", "카메라", "스피커", "워치",
    "크림", "세럼", "앰플", "토너", "선크림", "쿠션", "파운데이션", "립", "틴트",
    "섀도우", "마스카라", "클렌징", "샴푸", "향수", "자켓", "패딩", "코트", "니트",
    "가방", "백팩", "신발", "스니커즈", "청소기", "세제", "수납", "프라이팬", "냄비",
    "에어프라이어", "커피머신", "텀블러", "캐리어", "블랙박스", "영양제", "유산균",
)

SHOP_LINK_HINTS = (
    "link.coupang.com", "coupang.com", "smartstore.naver.com", "naver.me",
    "oliveyoung.co.kr", "musinsa.com", "29cm.co.kr", "zigzag.kr", "a-bly.com",
)

NEGATIVE_KEYWORDS = (
    "브이로그", "vlog", "먹방", "레시피", "게임", "롤", "발로란트", "마인크래프트",
    "뉴스", "정치", "주식", "코인", "부동산", "노래", "뮤비", "mv", "커버", "cover",
    "예고편", "하이라이트", "플레이리스트", "playlist", "수면음악", "asmr",
)


def sb_headers(prefer=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    if SUPABASE_KEY.startswith("eyJ"):
        h["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(table, params):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers(),
        params=params,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"{table} 조회 실패: HTTP {resp.status_code} · {resp.text[:250]}")
    return resp.json()


def sb_patch(table, values, params):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers("return=minimal"),
        params=params,
        json=values,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"{table} 수정 실패: HTTP {resp.status_code} · {resp.text[:250]}")


def compute_video_product_score(title, description):
    title_low = str(title or "").lower()
    desc_low = str(description or "").lower()
    merged = f"{title_low} {desc_low[:2000]}"

    score = 10

    for kw in STRONG_POSITIVE_KEYWORDS:
        if kw in title_low:
            score += 25
        elif kw in desc_low[:1500]:
            score += 12

    hint_hits = sum(1 for kw in PRODUCT_HINT_KEYWORDS if kw in merged)
    score += min(30, hint_hits * 8)

    if any(link in desc_low for link in SHOP_LINK_HINTS):
        score += 18

    if re.search(r"(top\s*\d+|\d+가지|\d+개|베스트|모음|총정리)", title_low):
        score += 12

    for neg in NEGATIVE_KEYWORDS:
        if neg in title_low:
            score -= 30

    return max(0, min(100, score))


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY 환경변수가 없습니다.")

    videos = sb_get(
        "videos",
        {
            "select": "video_id,title,description,view_count",
            "analysis_status": "eq.pending",
            "order": "created_at.desc",
            "limit": str(SCORE_BATCH_SIZE),
        },
    )
    print(f"[score_videos] 채점 대상 pending 영상: {len(videos)}개")
    if not videos:
        return

    queued_cnt = 0
    skipped_cnt = 0

    for video in videos:
        vid = str(video.get("video_id") or "").strip()
        if not vid:
            continue
        score = compute_video_product_score(video.get("title"), video.get("description"))
        next_status = "queued" if score >= MIN_QUEUE_SCORE else "skipped_non_product"

        sb_patch(
            "videos",
            {
                "product_score": score,
                "analysis_status": next_status,
                "analysis_error": None,
            },
            {"video_id": f"eq.{vid}"},
        )
        if next_status == "queued":
            queued_cnt += 1
        else:
            skipped_cnt += 1

    print(f"[score_videos] 완료 -> queued: {queued_cnt}개, skipped_non_product: {skipped_cnt}개")


if __name__ == "__main__":
    main()
