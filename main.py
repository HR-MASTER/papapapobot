# main.py
import os
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from telegram import Update
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

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 그룹 등록 상태
def init_bot_data(app):
    if "is_group_registered" not in app.bot_data:
        app.bot_data["is_group_registered"] = {}

# ========== 명령어 핸들러 ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ 번역봇이 작동 중입니다. /help\n"
        "✅ Bot running. /help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Help – 다국어 안내\n\n"
        "[한국어]\n"
        "/createcode\n/registercode [코드]\n/disconnect\n/solomode\n/extendcode\n/paymentcheck [해시] [코드]\n\n"
        "[English]\n"
        "/createcode\n/registercode [code]\n/disconnect\n/solomode\n/extendcode\n/paymentcheck [txhash] [code]\n\n"
        "[中文]\n"
        "/createcode\n/registercode [代码]\n/disconnect\n/solomode\n/extendcode\n/paymentcheck [哈希] [代码]\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode\n/registercode [code]\n/disconnect\n/solomode\n/extendcode\n/paymentcheck [hash] [code]\n\n"
        "[Tiếng Việt]\n"
        "/createcode\n/registercode [mã]\n/disconnect\n/solomode\n/extendcode\n/paymentcheck [hash] [mã]"
    )

async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = str(user_id)[-6:]
    register_code(code, user_id, duration_days=3)
    await update.message.reply_text(f"✅ Your code: {code}")

async def register_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args[0]) != 6:
        await update.message.reply_text("❗ Usage: /registercode [6-digit-code]")
        return
    code = args[0]
    if not is_code_valid(code):
        await update.message.reply_text("❌ Code invalid or expired.")
        return
    chat_id = update.effective_chat.id
    if not register_group_to_code(code, chat_id):
        await update.message.reply_text("⚠️ Code already used in 2 groups.")
        return
    # 그룹 등록 표시
    context.bot_data["is_group_registered"][chat_id] = True
    await update.message.reply_text("✅ Code registered to this group.")

async def solo_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    if not is_solo_mode_active(user):
        activate_solo_mode(user)
        await update.message.reply_text("✅ Solo mode started (3 days).")
    elif can_extend_solo_mode(user):
        extend_solo_mode(user)
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
    await handle_translation(update, context)
    await log_message_to_group(update, context)

# ========== 봇 실행 ==========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 커맨드
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

    # 메시지 번역
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("✅ 번역봇 실행 중...")
    app.run_polling()
