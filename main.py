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

logging.basicConfig(level=logging.INFO)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Webhook/polling 충돌 제거 (getUpdates 드롭)
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

def init_bot_data(app):
    if "is_group_registered" not in app.bot_data:
        app.bot_data["is_group_registered"] = {}

# ---- 명령어들 ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 번역봇 작동 중. /help")

async def help_command(update, context):
    await update.message.reply_text(
        "📌 Help:\n"
        "/createcode 3일 코드 생성\n"
        "/registercode [코드] 그룹 등록\n"
        "/disconnect 연결 해제\n"
        "/solomode 솔로 모드(3일)\n"
        "/extendcode 연장 요청\n"
        "/paymentcheck [hash][code] 결제 확인"
    )

async def create_code(update, context):
    uid = update.effective_user.id
    code = str(uid)[-6:]
    register_code(code, uid, duration_days=3)
    await update.message.reply_text(f"✅ Your code: {code}")

async def register_code_cmd(update, context):
    args = context.args
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ Usage: /registercode [6-digit]")
    code = args[0]
    if not is_code_valid(code):
        return await update.message.reply_text("❌ Code invalid/expired")
    chat_id = update.effective_chat.id
    if not register_group_to_code(code, chat_id):
        return await update.message.reply_text("⚠️ Code used in 2 groups")
    context.bot_data["is_group_registered"][chat_id] = True
    await update.message.reply_text("✅ Code registered")

async def solo_mode(update, context):
    uid = update.effective_user.id
    if not is_solo_mode_active(uid):
        activate_solo_mode(uid)
        await update.message.reply_text("✅ Solo mode ON (3일)")
    elif can_extend_solo_mode(uid):
        extend_solo_mode(uid)
        await update.message.reply_text("🔁 Solo mode extended")
    else:
        await update.message.reply_text("⚠️ Solo 연장 한도 초과")

async def disconnect(update, context):
    await disconnect_user(update, context)

async def owner_auth(update, context):
    await handle_owner_auth(update, context)

async def set_group(update, context):
    await handle_set_groups(update, context)

async def owner_help(update, context):
    await show_owner_commands(update, context)

async def payment_check(update, context):
    await handle_payment_check(update, context)

async def message_handler(update, context):
    await handle_translation(update, context)
    await log_message_to_group(update, context)

# ---- 실행 ----
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("✅ 번역봇 실행.")
    app.run_polling(drop_pending_updates=True)
