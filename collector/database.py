import json
import requests

from collector.config import SUPABASE_URL, SUPABASE_KEY


def build_headers(prefer=None):
    """
    최신 Supabase sb_secret_ 키와
    기존 service_role JWT 키를 모두 지원한다.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 기존 service_role 키는 eyJ... 형태의 JWT이므로 Bearer 헤더 사용
    # 최신 sb_secret_ 키는 apikey 헤더만 사용
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"

    if prefer:
        headers["Prefer"] = prefer

    return headers


def table_url(table):
    """
    config.py의 SUPABASE_URL에는
    https://프로젝트ID.supabase.co 까지만 저장한다.
    """
    base_url = SUPABASE_URL.rstrip("/")
    return f"{base_url}/rest/v1/{table}"


def raise_detailed_error(response):
    """
    GitHub Actions 로그에서 Supabase의 실제 오류 내용을 확인할 수 있게 한다.
    API 키 전체 값은 출력하지 않는다.
    """
    if response.ok:
        return

    try:
        error_body = response.json()
    except Exception:
        error_body = response.text[:1000]

    raise RuntimeError(
        f"Supabase 요청 실패: "
        f"HTTP {response.status_code} | "
        f"URL={response.url} | "
        f"응답={error_body}"
    )


def upsert(table, rows, on_conflict):
    if not rows:
        return []

    response = requests.post(
        table_url(table),
        params={
            "on_conflict": on_conflict,
        },
        headers=build_headers(
            "resolution=merge-duplicates,return=representation"
        ),
        data=json.dumps(rows, ensure_ascii=False),
        timeout=45,
    )

    raise_detailed_error(response)

    if not response.text:
        return []

    return response.json()


def select(
    table,
    columns="*",
    filters=None,
    limit=1000,
    order=None,
):
    params = {
        "select": columns,
        "limit": limit,
    }

    if filters:
        params.update(filters)

    if order:
        params["order"] = order

    response = requests.get(
        table_url(table),
        params=params,
        headers=build_headers(),
        timeout=45,
    )

    raise_detailed_error(response)

    if not response.text:
        return []

    return response.json()


def update(table, values, filters):
    response = requests.patch(
        table_url(table),
        params=filters,
        headers=build_headers("return=representation"),
        data=json.dumps(values, ensure_ascii=False),
        timeout=45,
    )

    raise_detailed_error(response)

    if not response.text:
        return []

    return response.json()
