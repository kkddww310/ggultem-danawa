# 1축: Google Gemini 무료 티어 (할당량이 넉넉한 flash-lite 우선 호출)
    if GEMINI_API_KEY:
        gemini_models = ["gemini-3.1-flash-lite", "gemini-2.5-flash"]
        for model_name in gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                },
            }
            try:
                resp = requests.post(url, json=body, timeout=35)
                if resp.status_code == 429:
                    errors.append(f"{model_name} HTTP 429")
                    continue
                if not resp.ok:
                    errors.append(f"{model_name} HTTP {resp.status_code}: {resp.text[:120]}")
                    continue
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return parse_json_response(text)
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")

    # 2축: OpenRouter 무료 모델 순차 호출 (Gemini 한도 소진 시 자동 폴백)
    if OPENROUTER_API_KEY:
        or_models = []
        if OPENROUTER_MODEL:
            or_models.append(OPENROUTER_MODEL)
        for fallback_or in ("openrouter/free", "google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"):
            if fallback_or not in or_models:
                or_models.append(fallback_or)
