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

    # 2) 번역 대상 언어 목록 및 이름 매핑
    targets = {
        "ko": "한국어",
        "zh": "中文",
        "km": "ភាសាខ្មែរ",
        "vi": "Tiếng Việt"
    }

    # 입력 언어는 제외
    to_translate = [lang for lang in targets if lang != src]

    # 3) 번역 후 한 번에 묶어서 전송
    parts = []
    for lang in to_translate:
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
        parts.append(f"[{targets[lang]}] {translated}")

    await update.message.reply_text("\n".join(parts))
