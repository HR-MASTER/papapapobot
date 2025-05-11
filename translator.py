# translator.py
# 번역 1회만 수행, gTTS 제거, 그룹 등록 체크 포함

import os
import requests
from langdetect import detect
from telegram import Update

API_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
HEADERS = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_TOKEN')}"}

LANG_MAP = {
    "ko": "kor_Kore",
    "zh": "cmn_Hans",
    "vi": "vie_Latn",
    "km": "khm_Khmr"
}

# 언어 감지
def detect_language(text):
    try:
        return detect(text)
    except:
        return None

# 단일 번역 수행
def translate(text, src, tgt):
    payload = {
        "inputs": text,
        "parameters": {"src_lang": LANG_MAP[src], "tgt_lang": LANG_MAP[tgt]}
    }
    r = requests.post(API_URL, headers=HEADERS, json=payload)
    if r.status_code != 200:
        return f"[{src}→{tgt}] 번역 실패 ({r.status_code})"
    try:
        return r.json()[0]["translation_text"]
    except:
        return "[번역 실패: 응답 파싱 오류]"

# 메시지 번역 진입
async def handle_translation(update: Update, context):
    chat_id = update.effective_chat.id
    # 그룹 등록 여부 체크
    if not context.bot_data.get("is_group_registered", {}).get(chat_id, False):
        return

    text = update.message.text
    src = detect_language(text)
    if src not in LANG_MAP:
        await update.message.reply_text("⚠️ 지원되지 않는 언어입니다.")
        return

    # fallback 대상 언어
    fallback = {"ko": "zh", "zh": "vi", "vi": "km", "km": "ko"}
    tgt = fallback.get(src, "zh")

    result = translate(text, src, tgt)
    await update.message.reply_text(f"[{src}→{tgt}]\n{result}")
