# translator.py
# 번역 1회만 수행, gTTS 제거, 403 방지용 응답 처리 포함

import requests
import os
from langdetect import detect
from telegram import Update

API_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_TOKEN')}"
}

LANG_MAP = {
    "ko": "kor_Kore",
    "zh-cn": "cmn_Hans",
    "zh": "cmn_Hans",
    "vi": "vie_Latn",
    "km": "khm_Khmr"
}

# 언어 자동 감지
def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

# 번역 수행 (단일 대상 언어로)
def translate(text, source_lang, target_lang):
    payload = {
        "inputs": text,
        "parameters": {
            "src_lang": LANG_MAP.get(source_lang),
            "tgt_lang": LANG_MAP.get(target_lang)
        }
    }
    response = requests.post(API_URL, headers=HEADERS, json=payload)
    if response.status_code != 200:
        return f"[{source_lang} → {target_lang}] 번역 실패 ({response.status_code})"
    try:
        return response.json()[0]['translation_text']
    except:
        return "[번역 실패: 응답 파싱 오류]"

# 메시지 처리 진입점
async def handle_translation(update: Update, context):
    text = update.message.text
    src_lang = detect_language(text)

    if src_lang not in LANG_MAP:
        await update.message.reply_text("⚠️ 지원되지 않는 언어입니다.")
        return

    # 자동 대상 언어 결정 (한국어 입력이면 중국어로 번역 등)
    fallback_targets = {
        "ko": "zh",
        "zh": "vi",
        "vi": "km",
        "km": "ko"
    }
    target_lang = fallback_targets.get(src_lang, "zh")

    translated = translate(text, src_lang, target_lang)
    await update.message.reply_text(f"[{src_lang} → {target_lang}]\n{translated}")
