# translator.py

import os
import requests

API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = "https://translation.googleapis.com/language/translate/v2"

async def handle_translation(update, context):
    text = update.message.text

    # 언어 감지
    detect_res = requests.post(
        f"{BASE_URL}/detect",
        params={"key": API_KEY, "q": text}
    ).json()
    src = detect_res["data"]["detections"][0][0]["language"]

    targets = {
        "ko": "한국어",
        "zh": "中文",
        "km": "ភាសាខ្មែរ",
        "vi": "Tiếng Việt"
    }

    parts = []
    for lang, name in targets.items():
        if lang == src:
            continue
        resp = requests.post(
            BASE_URL,
            params={
                "key": API_KEY,
                "q": text,
                "target": lang,
                "format": "text"
            }
        ).json()
        translated = resp["data"]["translations"][0]["translatedText"]
        parts.append(f"[{name}] {translated}")

    await update.message.reply_text("\n".join(parts))
