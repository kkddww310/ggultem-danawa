from collector.database import select, update

POSITIVE = {
    "내돈내산": 4, "추천템": 3, "필수템": 3, "하울": 3,
    "리뷰": 2, "사용기": 2, "비교": 2, "언박싱": 2,
    "구매": 2, "신제품": 2, "가성비": 2, "베스트": 1, "top": 1,
}
NEGATIVE = {
    "뮤직비디오": -8, "티저": -6, "예고": -5, "다시보기": -5,
    "라이브": -4, "먹방": -4, "브이로그": -3, "챌린지": -3,
}


def score(text):
    value = 0
    lowered = (text or "").lower()
    for keyword, points in POSITIVE.items():
        if keyword in lowered:
            value += points
    for keyword, points in NEGATIVE.items():
        if keyword in lowered:
            value += points
    return value


def main():
    videos = select(
        "videos", "video_id,title,description",
        {"analysis_status": "eq.pending"}, limit=5000,
    )
    queued = 0
    for video in videos:
        product_score = score(f"{video['title']} {video.get('description', '')[:1500]}")
        status = "queued" if product_score >= 3 else "skipped_non_product"
        update("videos", {"product_score": product_score, "analysis_status": status}, {"video_id": f"eq.{video['video_id']}"})
        queued += status == "queued"
    print(f"Scored {len(videos)} videos; queued for AI: {queued}")


if __name__ == "__main__":
    main()
