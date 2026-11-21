import streamlit as st
import json, os, re, urllib.request
from urllib.parse import urlparse, parse_qs, quote
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

DEFAULT_API_KEY = ""
DB_FILE = "items.json"
KEY_FILE = "api_key.txt"

st.set_page_config(page_title="꿀템 다나와", layout="wide")
st.title("🔍 유튜버 꿀템 & 최저가 한눈에 비교")
st.caption("유튜버가 추천한 진짜 꿀템과 실시간 최저가 비교 페이지로 바로 연결해 줍니다.")

NOISE_WORDS = (
    "인트로", "오프닝", "시작", "마무리", "아웃트로", "총평", "결론",
    "구독", "이벤트", "쿠키", "예고", "목차", "근황", "달라졌어요",
    "소감", "질문", "후기", "원칙", "고능", "PD", "피디", "출연",
    "등장", "브이로그", "일상", "주부", "추천", "꿀템", "문의", "비즈니스",
    "협찬", "광고", "인스타", "유튜브", "채널", "타임라인", "챕터"
)

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

def load_items():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_items(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def add_unique_items(new_items):
    db = load_items()
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in db}
    added = []
    for item in new_items:
        key = (item.get("name", "").strip().lower(), item.get("youtuber", "").strip().lower())
        if key[0] and key not in seen:
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

def search_youtube_videos(query, limit=5):
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html) or re.search(r"ytInitialData\s*=\s*(\{.*?\});", html)
    if not m:
        return []
    data = json.loads(m.group(1))
    results, seen = [], set()

    def walk(node):
        if len(results) >= limit:
            return
        if isinstance(node, dict):
            if "videoRenderer" in node:
                vr = node["videoRenderer"]
                vid = vr.get("videoId", "")
                if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    t_runs = vr.get("title", {}).get("runs", [])
                    o_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                    results.append({
                        "video_id": vid,
                        "title": t_runs[0].get("text", "제목 없음") if t_runs else "제목 없음",
                        "youtuber": o_runs[0].get("text", "유튜버") if o_runs else "유튜버",
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return results

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

def fetch_video_bundle(video_id, youtuber_hint="유튜버", title_hint=""):
    title, desc, youtuber = title_hint, "", youtuber_hint

    # 1순위: YouTube 웹 설명란 전용 API (youtubei/v1/next - 해외 서버 차단 우회)
    try:
        payload = json.dumps({
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20261101.00.00",
                    "hl": "ko",
                    "gl": "KR"
                }
            },
            "videoId": video_id
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/next",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-YouTube-Client-Name": "1",
                "X-YouTube-Client-Version": "2.20261101.00.00",
            }
        )
        next_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
        desc = _find_desc_in_json(next_data)
    except Exception:
        pass

    # 2순위: YouTube iOS 클라이언트 player API
    if not desc:
        try:
            payload = json.dumps({
                "context": {
                    "client": {
                        "clientName": "IOS",
                        "clientVersion": "19.45.4",
                        "deviceMake": "Apple",
                        "deviceModel": "iPhone16,2",
                        "hl": "ko",
                        "gl": "KR"
                    }
                },
                "videoId": video_id
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://www.youtube.com/youtubei/v1/player",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)",
                    "X-YouTube-Client-Name": "5",
                    "X-YouTube-Client-Version": "19.45.4",
                }
            )
            res_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
            details = res_data.get("videoDetails", {})
            if details:
                title = details.get("title", title)
                desc = details.get("shortDescription", "")
                youtuber = details.get("author", youtuber)
        except Exception:
            pass

    # 3순위: 일반 웹 HTML 파싱 보조
    if not desc:
        try:
            req = urllib.request.Request(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}
            )
            html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
            m = re.search(r"var ytInitialPlayerResponse = (\{.*?\});</script>", html)
            if m:
                details = json.loads(m.group(1)).get("videoDetails", {})
                title = details.get("title", title)
                desc = details.get("shortDescription", "")
                youtuber = details.get("author", youtuber)
        except Exception:
            pass

    transcript = ""
    if len(desc) < 150:
        try:
            ytt = YouTubeTranscriptApi()
            if hasattr(ytt, "fetch"):
                fetched = ytt.fetch(video_id, languages=["ko", "en"])
                transcript = "\n".join([f"[{int(s.start)}초] {s.text}" for s in fetched])
        except Exception:
            pass

    return {"video_id": video_id, "youtuber": youtuber, "title": title, "desc": desc, "transcript": transcript[:1200]}

def extract_products_locally(bundles):
    extracted = []
    for b in bundles:
        vid = b["video_id"]
        yt = b["youtuber"]
        title = b["title"]
        raw_lines = [ln.strip() for ln in b["desc"].splitlines() if ln.strip()]

        ts_list = []
        for ln in raw_lines:
            m_ts = re.match(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", ln)
            if m_ts:
                hh = int(m_ts.group(1) or 0)
                mm, ss = int(m_ts.group(2)), int(m_ts.group(3))
                label = re.sub(r"^[\-\•\*\d\.\)\]]+\s*", "", m_ts.group(4)).strip()
                ts_list.append((hh * 3600 + mm * 60 + ss, label))

        for raw_ln in raw_lines:
            if "@" in raw_ln or raw_ln.startswith("#"):
                continue

            has_url = "http" in raw_ln
            ln = re.sub(r"https?://\S+", "", raw_ln).strip()
            ln = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", ln).strip()
            if not ln or len(ln) < 2:
                continue

            candidate = None
            category = ""
            sec = 0

            m_colon = re.match(r"^([^:：]{1,35})\s*[:：]\s*(.*)$", ln)
            if m_colon:
                left = m_colon.group(1).strip()
                right = m_colon.group(2).strip()
                if has_url and not right:
                    candidate = left
                elif right:
                    category = left
                    candidate = right
            else:
                m_line_ts = re.match(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", ln)
                if m_line_ts:
                    hh = int(m_line_ts.group(1) or 0)
                    mm, ss = int(m_line_ts.group(2)), int(m_line_ts.group(3))
                    sec = hh * 3600 + mm * 60 + ss
                    body = m_line_ts.group(4).strip()
                    if " - " in body:
                        parts = body.split(" - ", 1)
                        category = parts[0].strip()
                        candidate = parts[1].strip()
                    else:
                        candidate = body
                else:
                    m_list = re.match(r"^(?:[\-\•\*\▶\▸\✔\✓]|\d{1,2}[\.\)\]])\s*(.+)$", ln)
                    if m_list:
                        candidate = m_list.group(1).strip()

            if not candidate:
                continue

            candidate = re.sub(r"^[\-\•\*\▶\▸\d\.\)\]]+\s*", "", candidate).strip()
            candidate = re.split(r"\s*(?:👉|▶|→|\|)\s*", candidate)[0].strip()
            if len(candidate) < 2 or len(candidate) > 70:
                continue
            if any(w in candidate for w in NOISE_WORDS) and not re.search(r"[A-Za-z0-9]{2,}", candidate):
                continue

            if sec == 0 and ts_list:
                for t_sec, t_label in ts_list:
                    if any(tok and tok in t_label for tok in candidate.split()[:2]):
                        sec = t_sec
                        break

            split_names = [s.strip() for s in re.split(r"\s*(?:&|/)\s*", candidate) if len(s.strip()) >= 2]
            for pname in split_names:
                mm, ss = divmod(sec, 60)
                reason = f"'{title}'에서 {yt}가 소개한 {category or '추천'} 제품"
                extracted.append({
                    "name": pname,
                    "keyword": category or pname.split()[0],
                    "youtuber": yt,
                    "reason": reason,
                    "timestamp": f"{mm:02d}:{ss:02d}",
                    "youtube_url": f"https://youtu.be/{vid}?t={sec}",
                })

    return extracted

def analyze_batch_with_gemini(bundles):
    api_key = get_api_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("API 키가 설정되지 않았습니다.")

    blocks = []
    for b in bundles:
        blocks.append(f"=== VIDEO_ID: {b['video_id']} | YOUTUBER: {b['youtuber']} ===\n[제목] {b['title']}\n[설명란]\n{b['desc'][:1500]}\n[자막]\n{b['transcript']}")

    prompt = f"""아래 유튜브 영상들에서 실제로 쇼핑몰에서 구매할 수 있는 '구체적인 제품(브랜드+제품명)'만 골라 JSON 배열로만 답해줘.
규칙:
1. PD/출연진 이름, 코너명, 인트로/아웃트로, 추상적 주제는 절대 넣지 마.
2. 실제 구매 가능한 상품이 없으면 [] 만 반환해.
3. 키 이름: "video_id", "youtuber", "name"(쇼핑몰 검색용 정확한 제품명), "keyword"(핵심 품목명), "reason"(추천 이유 한 줄), "start_sec"(등장 시작 초 정수, 모르면 0)

{chr(10).join(blocks)}"""

    client = genai.Client(api_key=api_key, http_options={"timeout": 20000})
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    cleaned = re.sub(r"^```json|```$", "", res.text.strip()).strip()
    out = []
    for item in json.loads(cleaned):
        vid = item.get("video_id") or bundles[0]["video_id"]
        sec = int(item.get("start_sec", 0))
        mm, ss = divmod(sec, 60)
        name = item.get("name", "").strip()
        if name:
            out.append({
                "name": name,
                "keyword": item.get("keyword", "").strip(),
                "youtuber": item.get("youtuber", bundles[0]["youtuber"]).strip(),
                "reason": item.get("reason", "").strip(),
                "timestamp": f"{mm:02d}:{ss:02d}",
                "youtube_url": f"https://youtu.be/{vid}?t={sec}",
            })
    return out

def render_card(item, idx):
    with st.container(border=True):
        c1, c2 = st.columns([1.6, 1])
        with c1:
            st.markdown(f"### 🏆 {item['name']}")
            st.write(f"**추천 유튜버:** {item['youtuber']} · `{item['timestamp']}` 등장")
            st.info(f"💡 **추천 이유:** {item['reason']}")
            b_yt, b_del = st.columns([3, 1])
            b_yt.link_button("▶️ 유튜버 영상 해당 구간 바로보기", item["youtube_url"])
            if b_del.button("🗑️ 삭제", key=f"del_{idx}_{item['name']}"):
                db = [x for x in load_items() if not (x.get("name") == item.get("name") and x.get("youtuber") == item.get("youtuber"))]
                save_items(db)
                st.rerun()
        with c2:
            st.markdown("### 💰 실시간 최저가 비교")
            q = quote(item["name"])
            st.link_button("🟢 네이버 쇼핑 낮은가격순 보기", f"https://search.shopping.naver.com/search/all?query={q}&sort=price_asc", type="primary")
            st.link_button("🚀 쿠팡 낮은가격순 보기", f"https://www.coupang.com/np/search?q={q}&sorter=salePriceAsc")

tab1, tab2 = st.tabs(["🔎 꿀템 검색하기", "🤖 유튜브 자동 수집기 (DB 채우기)"])

with tab1:
    db = load_items()
    yts = ["전체 유튜버"] + sorted(list({i.get("youtuber", "") for i in db if i.get("youtuber")}))
    c1, c2 = st.columns([3, 1])
    kw = c1.text_input(f"찾으시는 물건을 입력하세요 (저장된 추천템: {len(db)}개)", placeholder="예: 헤드폰, 마우스, 보조배터리, 충전기")
    sel_yt = c2.selectbox("유튜버 필터", yts)

    filtered = [i for i in db if sel_yt == "전체 유튜버" or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "")).lower()]

    if filtered:
        st.subheader(f"'{kw}' 검색 결과 ({len(filtered)}건)" if kw else f"🔥 최신 등록된 유튜버 추천 꿀템 ({len(filtered)}건)")
        for idx, item in enumerate(reversed(filtered)):
            render_card(item, idx)
    elif kw:
        st.warning(f"아직 DB에 '{kw}' 관련 추천템이 없습니다.")
        st.link_button(f"🟢 네이버 쇼핑에서 '{kw}' 최저가 바로 보기", f"https://search.shopping.naver.com/search/all?query={quote(kw)}&sort=price_asc")
    else:
        st.info("아직 저장된 추천템이 없습니다. 위쪽 **'🤖 유튜브 자동 수집기'** 탭에서 키워드를 입력해 꿀템을 모아보세요!")

with tab2:
    mode = st.radio(
        "수집 방식",
        ["⚡ 무제한 로컬 추출 (AI 한도 소모 0회)", "🤖 Gemini AI 정밀 분석 (API 키 사용)"],
        horizontal=True
    )
    c1, c2 = st.columns([3, 1])
    q_in = c1.text_input("유튜브 검색 키워드", placeholder="예: 잇섭 추천템, 가전주부 추천템, 내돈내산")
    lim = c2.number_input("분석할 영상 수", 1, 8, 5)

    if st.button("🚀 자동 수집 시작하기", type="primary") and q_in:
        status = st.empty()
        try:
            status.info("1/2 유튜브 영상 목록과 설명란 수집 중...")
            videos = search_youtube_videos(q_in, limit=int(lim))
            analyzed = {extract_video_id(i.get("youtube_url", "")) for i in load_items()}
            targets = [v for v in videos if v["video_id"] not in analyzed]
            if not targets:
                status.empty()
                st.info("이미 모두 수집한 영상들입니다.")
            else:
                bundles = [fetch_video_bundle(v["video_id"], v["youtuber"], v["title"]) for v in targets]
                if "무제한 로컬 추출" in mode:
                    status.info("2/2 설명란에서 실제 구매 제품만 무제한 추출 중...")
                    items = extract_products_locally(bundles)
                else:
                    status.info("2/2 Gemini AI 정밀 분석 중...")
                    try:
                        items = analyze_batch_with_gemini(bundles)
                    except Exception:
                        status.info("2/2 AI 한도 초과 -> 무제한 로컬 추출로 자동 전환 중...")
                        items = extract_products_locally(bundles)

                added = add_unique_items(items)
                status.empty()
                st.success(f"🎉 완료! 총 {len(added)}개의 제품이 저장되었습니다.")
                if not added:
                    st.caption(f"확인한 영상 {len(bundles)}개 중 설명란이 수집된 영상: {sum(1 for b in bundles if b['desc'])}개 (설명란에 제품 목록이 없는 영상일 수 있습니다.)")
                for a in added:
                    st.write(f"- **{a['name']}** ({a['youtuber']} · `{a['timestamp']}`): {a['reason']}")
        except Exception as e:
            status.empty()
            st.error(f"수집 중 오류: {e}")

    with st.expander("⚙️ API 키 변경 / 저장된 DB 관리"):
        new_key = st.text_input("새 Gemini API 키 입력", type="password")
        if st.button("API 키 저장") and new_key.strip():
            open(KEY_FILE, "w", encoding="utf-8").write(new_key.strip())
            st.success("새 API 키가 저장되었습니다!")
        st.divider()
        db_now = load_items()
        st.write(f"현재 저장된 추천템: **{len(db_now)}개**")
        if db_now and st.button("모든 데이터 초기화"):
            save_items([])
            st.rerun()
# === 여기까지 복사되면 끝 ===
