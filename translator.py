# translator.py
# NLLB 마이크로 모델 기반 4개국어 번역 모듈 (Hugging Face API 사용)

import requests
import os
from langdetect import detect
from gtts import gTTS
from telegram import Update, InputFile
import uuid

API_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_TOKEN')}"
}

# 언어 코드 매핑: 감지 언어 코드 → NLLB API용
LANG_MAP = {
    "ko": "kor_Kore",     # 한국어
    "zh-cn": "cmn_Hans",  # 중국어
    "zh": "cmn_Hans",     # 중국어
    "vi": "vie_Latn",     # 베트남어
    "km": "khm_Khmr"      # 크메르어
}

# 언어 감지
def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

# 텍스트 → 타겟 언어 번역
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
        return f"[번역 실패] ({response.status_code})"
    try:
        return response.json()[0]['translation_text']
    except:
        return "[번역 오류]"

# 텍스트 → 음성 파일 생성
def generate_tts(text, lang):
    path = f"/tmp/{uuid.uuid4().hex}.mp3"
    tts = gTTS(text=text, lang=lang)
    tts.save(path)
    return path

# 메인 메시지 핸들러 (main.py에서 호출)
async def handle_translation(update: Update, context):
    text = update.message.text
    user_id = update.effective_user.id
    input_lang = detect_language(text)

    if input_lang not in LANG_MAP:
        await update.message.reply_text("⚠️ 이 언어는 지원되지 않습니다.")
        return

    target_langs = [lang for lang in ["ko", "zh", "vi", "km"] if lang != input_lang]

    for tgt in target_langs:
        translated = translate(text, input_lang, tgt)
        await update.message.reply_text(f"[{input_lang} → {tgt}]\n{translated}")
        try:
            audio_path = generate_tts(translated, tgt)
            with open(audio_path, "rb") as f:
                await update.message.reply_voice(voice=InputFile(f))
        except:
            await update.message.reply_text(f"(음성 전송 실패 - {tgt})")
