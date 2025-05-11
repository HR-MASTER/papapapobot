# main.py

import os
import time
import logging
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv

from translator import handle_translation
import database

logging.basicConfig(level=logging.INFO)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─────────────────────────
# 1) Polling 충돌 방지
# ─────────────────────────
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

# ─────────────────────────
# 2) Bot Data 초기화
# ─────────────────────────
def init_bot_data(app):
    if "is_group_registered" not in app.bot_data:
        app.bot_data["is_group_registered"] = {}

# ─────────────────────────
# 3) 커맨드 핸들러들
# ─────────────────────────

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✅ 번역봇이 작동 중입니다. /help 를 입력하세요.\n"
        "✅ Translation bot is running. Type /help\n"
        "✅ 翻译机器人运行中。请输入 /help\n"
        "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ ក្រាប់ /help\n"
        "✅ Bot dịch đang hoạt động. Gõ /help"
    )
    await update.message.reply_text(msg)

# /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📌 Help – 다국어 안내\n"
        "[한국어],[English],[中文],[ភាសាខ្មែរ],[Tiếng Việt]\n\n"
        "/createcode       – 3일 무료 코드 생성\n"
        "/registercode [코드] – 그룹에 코드 등록\n"
        "/disconnect       – 연결 해제\n"
        "/solomode         – 솔로 모드 (3일)\n"
        "/extendcode       – 연장 요청 (30 USDT → 30일)\n"
        "/remaining        – 남은 기간 확인\n"
    )
    await update.message.reply_text(msg)

# /createcode
async def createcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = database.register_code(uid, duration_days=3)
    await update.message.reply_text(f"✅ Your code: {code}\n(3일간 유효)")

# /registercode
async def registercode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ Usage: /registercode [6-digit code]")
    code = args[0]
    gid = update.effective_chat.id
    if not database.is_code_valid(code):
        return await update.message.reply_text("❌ 코드가 유효하지 않거나 만료되었습니다.")
    if not database.register_group_to_code(code, gid, duration_days=3):
        return await update.message.reply_text("⚠️ 이미 연결되어 있거나 2회 초과 등록 불가.")
    context.bot_data["is_group_registered"][gid] = True
    await update.message.reply_text(
        f"✅ 그룹이 코드 {code} 로 등록되었습니다.\n"
        "3일 후 자동 해제됩니다."
    )

# /disconnect
async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.disconnect_user(update, context)

# /solomode
async def solomode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    database.activate_solo_mode(uid, duration_days=3)
    await update.message.reply_text("✅ 솔로 모드가 시작되었습니다. (3일간)")

# /extendcode
async def extendcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if not database.is_group_active(gid):
        return await update.message.reply_text("❗ 등록된 코드가 없습니다.")
    if database.extend_group(gid, duration_days=30):
        rem = database.group_remaining_seconds(gid)
        days = rem // 86400
        await update.message.reply_text(
            f"🔁 코드가 30일 연장되었습니다. 남은 기간: {days}일"
        )
    else:
        await update.message.reply_text(
            "⚠️ 연장 한도(2회)를 초과했습니다.\n"
            "추가 연장은 30 USDT 결제 후 가능합니다."
        )

# /remaining
async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    sec = database.group_remaining_seconds(gid)
    if sec <= 0:
        return await update.message.reply_text("❗ 등록된 코드가 없거나 만료되었습니다.")
    days = sec // 86400
    hrs = (sec % 86400) // 3600
    mins = (sec % 3600) // 60
    await update.message.reply_text(
        f"⏳ 남은 기간: {days}일 {hrs}시간 {mins}분"
    )

# /paymentcheck (생략 가능)
async def paymentcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 트랜스액션 자동 감지 연동 필요 시 여기에 구현
    await update.message.reply_text("💳 결제 확인 기능은 곧 제공됩니다.")

# 관리자/소유자용 (auth, setloggroup 등) 핸들러 생략…

# 메시지 핸들러: 번역 + 로그
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if context.bot_data.get("is_group_registered", {}).get(gid):
        await handle_translation(update, context)
        # logger.log_message_to_group(update, context)

# ─────────────────────────
# 4) Bot 실행
# ─────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # Command 등록
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("createcode", createcode))
    app.add_handler(CommandHandler("registercode", registercode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("solomode", solomode))
    app.add_handler(CommandHandler("extendcode", extendcode))
    app.add_handler(CommandHandler("remaining", remaining))
    app.add_handler(CommandHandler("paymentcheck", paymentcheck))
    # … 소유자용 핸들러도 여기에 추가

    # Message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("✅ 번역봇 실행 중...")
    app.run_polling(drop_pending_updates=True)
