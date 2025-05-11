import os, requests
from langdetect import detect
from telegram import Update

API_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
HEADERS = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_TOKEN')}"}

LANG_MAP = {"ko":"kor_Kore","zh":"cmn_Hans","vi":"vie_Latn","km":"khm_Khmr"}

# ① 언어 감지
def detect_language(text):
    try: return detect(text)
    except: return None

# ② 번역 (단일 대상)
def translate(text, src, tgt):
    payload = {"inputs": text, "parameters": {"src_lang":LANG_MAP[src],"tgt_lang":LANG_MAP[tgt]}}
    r = requests.post(API_URL, headers=HEADERS, json=payload)
    if r.status_code!=200: return f"[{src}→{tgt}] 번역 실패 ({r.status_code})"
    return r.json()[0]["translation_text"]

# ③ 메시지 처리 진입
async def handle_translation(update: Update, context):
    chat_id = update.effective_chat.id
    # 그룹 등록 여부 체크 (database.is_group_registered)
    if not context.bot_data.get("is_group_registered", {}).get(chat_id, False):
        return
    text = update.message.text
    src = detect_language(text)
    if src not in LANG_MAP:
        await update.message.reply_text("⚠️ 지원 언어 아님")
        return
    # fallback 대상: ko→zh, zh→vi, vi→km, km→ko
    fallback = {"ko":"zh","zh":"vi","vi":"km","km":"ko"}
    tgt = fallback[src]
    result = translate(text, src, tgt)
    await update.message.reply_text(f"[{src}→{tgt}]\n{result}")
