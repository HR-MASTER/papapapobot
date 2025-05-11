 async def crea:contentReference[oaicite:2]{index=2}DEFAULT_TYPE):
  :contentReference[oaicite:3]{index=3}ve_user.id
     :contentReference[oaicite:4]{index=4}     database.register_code(uid, code, duration_days=3)
-    await update.message.reply_text(
-        format_multilang(
-            f"✅ 코드 생성: {code} (3일간 유효)",
-            f"✅ Code created: {code} (valid:contentReference[oaicite:5]{index=5}       :contentReference[oaicite:6]{index=6}ងៃ)",
-          :contentReference[oaicite:7]{index=7}ã: {cod:contentReference[oaicite:8]{index=8}   )
-    )
+    await update.message.reply_text:contentReference[oaicite:9]{index=9}t_multi:contentReference[oaicite:10]{index=10}+            f"✅ :contentReference[oaicite:11]{index=11} 유효)",
:contentReference[oaicite:12]{index=12} {code} (3天有效)",               # ← zh slot
+         :contentReference[oaicite:13]{index=13}{code} :contentReference[oaicite:14]{index=14} # ← km slot
+   :contentReference[oaicite:15]{index=15})"                   #:contentReference[oaicite:16]{index=16}anslator.p:contentReference[oaicite:17]{index=17}ranslator.py

from google.cloud import translate_v2 as translate

translate_client = translate.Client()

async def handle_translation(update, context):
    src_text = update.message.text
    # 감지된 소스 언어 코드 예: 'ko', 'zh-CN', 'km', 'vi'
    src_lang = translate_client.detect_language(src_text)["language"]

    # 4개국어 목표 언어 순서: 한국어, 중국어(zh), 크메르어(km), 베트남어(vi)
    targets = ["ko", "zh-CN", "km", "vi"]
    # 입력과 같은 언어는 제외
    targets = [t for t in targets if not t.startswith(src_lang)]

    segments = []
    for tgt in targets:
        res = translate_client.translate(
            src_text,
            source_language=src_lang,
            target_language=tgt
        )
        # 언어 코드별 친절한 이름 맵핑
        name = {
            "ko": "한국어",
            "zh-CN": "中文",
            "km": "ភាសាខ្មែរ",
            "vi": "Tiếng Việt"
        }[tgt]
        segments.append(f"[{name}] {res['translatedText']}")

    # 한 번에 모두 묶어서 보내기
    reply = "\n".join(segments)
    await update.message.reply_text(reply)
