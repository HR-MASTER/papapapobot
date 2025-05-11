import os
from google.cloud import translate_v2 as translate

API_KEY = os.getenv("GOOGLE_API_KEY")
client = translate.Client()

async def handle_translation(update, context):
    text = update.message.text
    result = client.detect_language(text)
    lang = result["language"]
    targets = {"ko":"한국어","zh":"中文","km":"ភាសាខ្មែរ","vi":"Tiếng Việt"}
    for code, name in targets.items():
        if code == lang:
            continue
        tr = client.translate(text, target_language=code)["translatedText"]
        await update.message.reply_text(f"[{name}]\n{tr}")
