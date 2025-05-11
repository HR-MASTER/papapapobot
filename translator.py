# translator.py
# 네 언어(ko/zh/vi/km) 중 하나 입력 시 나머지 3개 언어로 모두 번역해서 출력

import os
import requests
from langdetect import detect
from telegram import Update

# Google Cloud Translation API 예시 (앞서 안내드린)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

# 지원 언어 매핑
LANG_MAP = {
    "ko": "ko",
    "zh": "zh-CN",
    "vi": "vi",
    "km": "km"
}

# 감지된 언어가 키로 쓰일 코드
SUPPORTED = set(LANG_MAP.keys())

def detect_language(text):
    try:
        return detect(text)
    except:
        return None

def translate(text, src, tgt):
    params = {"key": GOOGLE_API_KEY}
    body = {
        "q": text,
        "source": LANG_MAP[src],
        "target": LANG_MAP[tgt],
        "format": "text"
    }
    r = requests.post(TRANSLATE_URL, params=params, json=body)
    if r.status_code != 200:
        return f"[{src}→{tgt}] 번역 실패 ({r.status_code})"
    data = r.json()
    try:
        return data["data"]["translations"][0]["translatedText"]
    except:
        return f"[{src}→{tgt}] 번역 실패 (응답 파싱 오류)"

async def handle_translation(update: Update, context):
    chat_id = update.effective_chat.id
    # 그룹 등록 여부 체크
    if not context.bot_data.get("is_group_registered", {}).get(chat_id, False):
        return

    text = update.message.text
    src = detect_language(text)
    if src not in SUPPORTED:
        await update.message.reply_text("⚠️ 지원되지 않는 언어입니다.")
        return

    # 나머지 세 언어로 동시 번역
    targets = SUPPORTED - {src}
    lines = []
    for tgt in targets:
        tr = translate(text, src, tgt)
        lines.append(f"[{src}→{tgt}] {tr}")

    # 한 번에 3줄로 출력
    await update.message.reply_text("\n".join(lines))
