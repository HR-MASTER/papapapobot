# main.py
import os
import logging
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv

from translator import handle_translation
from database import (
    register_code, is_code_valid,
    register_group_to_code, disconnect_user,
    activate_solo_mode, can_extend_solo_mode,
    extend_solo_mode, is_solo_mode_active
)
from auth import (
    handle_owner_auth, handle_set_groups,
    show_owner_commands
)
from logger import log_message_to_group
from payment import handle_payment_check

# 로깅 레벨 설정
logging.basicConfig(level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ====== Webhook 강제 삭제 & Pending Updates 드롭 ======
# 이렇게 하면 혹시 남아 있던 Webhook/업데이트가 모두 무시됩니다.
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

# 그룹 등록 상태 저장소
# database.register_group_to_code 호출 시 이 dict도 업데이트 해 주세요.
def init_bot_data(app):
    if "is_group_registered" not in app.bot_data:
        app.bot_data["is_group_registered"] = {}

# ========== 커맨드 핸들러 ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ 번역봇이 작동 중입니다. /help\n"
        "✅ Bot running. Type /help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Help – 다국어 안내\n"
        "[한국어]/createcode /registercode /disconnect /solomode /extendcode /paymentcheck\n"
        "[English]/createcode /registercode /disconnect /solomode /extendcode /paymentcheck\n"
        "[中文]/createcode /registercode /disconnect /solomode /extendcode /paymentcheck\n"
        "[ភាសាខ្មែរ]/createcode /registercode /disconnect /solomode /extendcode /paymentcheck\n"
        "[Tiếng Việt]/createcode /registercode /disconnect /solomode /extendcode /paymentcheck"
    )

async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = str(uid)[-6:]
    register_code(code, uid, duration_days=3)
    await update.message.reply_text(f"✅ Your code: {code}")

async def register_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ Usage: /registercode [6-digit-code]")
    code = args[0]
    if not is_code_valid(code):
        return await update.message.reply_text("❌ Code invalid or expired.")
    chat_id = update.effective_chat.id
    if not register_group_to_code(code, chat_id):
        return await update.message.reply_text("⚠️ Code already used in 2 groups.")
    # 그룹 등록 표시
    context.bot_data["is_group_registered"][chat_id] = True
    await update.message.reply_text("✅ Code registered to this group.")

async def solo_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_solo_mode_active(uid):
        activate_solo_mode(uid)
        await update.message.reply_text("✅ Solo mode started (3 days).")
    elif can_extend_solo_mode(uid):
        extend_solo_mode(uid)
        await update.message.reply_text("🔁 Solo mode extended.")
    else:
        await update.message.reply_text("⚠️ Cannot extend solo more than twice.")

async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await disconnect_user(update, context)

async def owner_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_owner_auth(update, context)

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_set_groups(update, context)

async def owner_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_owner_commands(update, context)

async def payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_payment_check(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 등록된 그룹에서만 번역
    await handle_translation(update, context)
    # 로그 전송
    await log_message_to_group(update, context)

# ========== 봇 실행 ==========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # Command
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("createcode", create_code))
    app.add_handler(CommandHandler("registercode", register_code_cmd))
    app.add_handler(CommandHandler("solomode", solo_mode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("auth", owner_auth))
    app.add_handler(CommandHandler("setloggroup", set_group))
    app.add_handler(CommandHandler("setcontrolgroup", set_group))
    app.add_handler(CommandHandler("setuserloggroup", set_group))
    app.add_handler(CommandHandler("ownerhelp", owner_help))
    app.add_handler(CommandHandler("paymentcheck", payment_check))

    # Message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("✅ 번역봇 실행 중...")
    # drop_pending_updates=True 로 이전 getUpdates 무시
    app.run_polling(drop_pending_updates=True)
