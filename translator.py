# translator.py
import os
import requests

API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = "https://translation.googleapis.com/language/translate/v2"

async def handle_translation(update, context):
    text = update.message.text

    # 1) 언어 감지
    detect_res = requests.post(
        f"{BASE_URL}/detect",
        params={"key": API_KEY, "q": text}
    ).json()
    src = detect_res["data"]["detections"][0][0]["language"]

    # 2) 번역 대상 언어 목록
    targets = {
        "ko": "한국어",
        "zh": "中文",
        "km": "ភាសាខ្មែរ",
        "vi": "Tiếng Việt",
    }

    # 3) 각 언어로 번역
    for code, name in targets.items():
        if code == src:
            continue
        resp = requests.post(
            BASE_URL,
            params={
                "key": API_KEY,
                "q": text,
                "target": code,
                "format": "text"
            }
        ).json()
        translated = resp["data"]["translations"][0]["translatedText"]
        await update.message.reply_text(f"[{name}]\n{translated}")
