import os
from google.cloud import translate_v2 as translate

API_KEY = os.getenv("GOOGLE_API_KEY")
client = translate.Client()

async def handle_translation(update, context):
    text = update.message.text
    # 언어 감지
    src = client.detect_language(text)["language"]
    # 번역 대상 언어와 이름 매핑
    targets = {
        "ko": "한국어",
        "zh": "中文",
        "km": "ភាសាខ្មែរ",
        "vi": "Tiếng Việt"
    }
    # 입력 언어는 제외하고 번역
    parts = []
    for code, name in targets.items():
        if code == src:
            continue
        tr = client.translate(text, target_language=code)["translatedText"]
        parts.append(f"[{name}] {tr}")
    # 한 번에 묶어서 전송
    reply = "\n".join(parts)
    await update.message.reply_text(reply)
