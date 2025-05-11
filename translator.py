# translator.py
import os
import requests
from telegram import Update

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
DETECT_URL    = "https://translation.googleapis.com/language/translate/v2/detect"

# 내부에서 사용할 간단 키
LANG_MAP = {
    "ko": "ko",
    "zh": "zh-CN",
    "vi": "vi",
    "km": "km"
}
SUPPORTED = set(LANG_MAP.keys())

def detect_language(text: str) -> str | None:
    """
    Google Translate detect API 호출로 언어 코드 추출
    기본적으로 raw 코드(rfc5646)에서 앞부분만 취함.
    """
    params = {"key": GOOGLE_API_KEY}
    body = {"q": text}
    resp = requests.post(DETECT_URL, params=params, json=body)
    if resp.status_code != 200:
        return None
    try:
        raw = resp.json()["data"]["detections"][0][0]["language"]
    except:
        return None
    code = raw.split("-")[0].lower()
    return code if code in SUPPORTED else None

def translate(text: str, src: str, tgt: str) -> str:
    """
    Google Translate v2 API 번역 호출
    """
    params = {"key": GOOGLE_API_KEY}
    body = {
        "q": text,
        "source": LANG_MAP[src],
        "target": LANG_MAP[tgt],
        "format": "text"
    }
    resp = requests.post(TRANSLATE_URL, params=params, json=body)
    if resp.status_code != 200:
        return f"[{src}→{tgt}] 번역 실패 ({resp.status_code})"
    try:
        return resp.json()["data"]["translations"][0]["translatedText"]
    except:
        return f"[{src}→{tgt}] 번역 실패(파싱 오류)"

async def handle_translation(update: Update, context):
    chat_id = update.effective_chat.id
    # 1. 등록된 그룹만 번역
    if not context.bot_data.get("is_group_registered", {}).get(chat_id, False):
        return

    text = update.message.text
    src = detect_language(text)
    if not src:
        await update.message.reply_text("⚠️ 지원되지 않는 언어입니다.")
        return

    # 2. 나머지 3개 언어로 모두 번역
    targets = SUPPORTED - {src}
    parts = []
    for tgt in targets:
        tr = translate(text, src, tgt)
        parts.append(f"[{src}→{tgt}] {tr}")

    # 3. 한 번에 출력
    await update.message.reply_text("\n".join(parts))
