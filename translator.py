# translator.py
import os
import requests
from langdetect import detect
from telegram import Update

# Google Cloud Translation API 설정
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

# 내부에서 사용할 단일 키 언어코드
LANG_MAP = {
    "ko": "ko",
    "zh": "zh-CN",
    "vi": "vi",
    "km": "km"
}

SUPPORTED = set(LANG_MAP.keys())

def normalize_lang(lang: str) -> str | None:
    """
    langdetect 가 'zh-cn', 'zh-tw' 등을 반환할 수 있으니
    '-' 이전 부분만 취해서 'zh' 로 매핑합니다.
    """
    if not lang:
        return None
    code = lang.split("-")[0].lower()
    return code if code in SUPPORTED else None

def detect_language(text: str) -> str | None:
    try:
        raw = detect(text)
        return normalize_lang(raw)
    except:
        return None

def translate(text: str, src: str, tgt: str) -> str:
    """
    Google Cloud Translate v2 호출
    """
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
    try:
        return r.json()["data"]["translations"][0]["translatedText"]
    except:
        return f"[{src}→{tgt}] 번역 실패 (응답 파싱 오류)"

async def handle_translation(update: Update, context):
    chat_id = update.effective_chat.id
    # 그룹 등록 여부 체크
    if not context.bot_data.get("is_group_registered", {}).get(chat_id, False):
        return

    text = update.message.text
    src = detect_language(text)
    if not src:
        await update.message.reply_text("⚠️ 지원되지 않는 언어입니다.")
        return

    # 나머지 3개국어 모두 번역
    targets = SUPPORTED - {src}
    lines = []
    for tgt in targets:
        tr = translate(text, src, tgt)
        lines.append(f"[{src}→{tgt}] {tr}")

    # 한 번에 3줄 출력
    await update.message.reply_text("\n".join(lines))
