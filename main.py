# main.py
# 텔레그램 번역봇 실행 진입점 (영문 명령어 + 5개국어 안내 + 단일 번역 출력)

import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram import Update
from dotenv import load_dotenv

from translator import handle_translation
from database import (
    register_code,
    disconnect_user,
    is_code_valid,
    register_group_to_code,
    activate_solo_mode,
    can_extend_solo_mode,
    extend_solo_mode,
    is_solo_mode_active,
    get_owner,
    set_owner,
    is_owner,
    set_control_group,
    set_log_group,
    set_user_log_group,
    is_control_group,
    is_log_group,
    is_user_log_group,
    can_create_code,
    register_code_creation,
)
from auth import (
    handle_owner_auth,
    handle_set_groups,
    show_owner_commands,
)
from logger import log_message_to_group
from payment import handle_payment_check

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ========== 명령어 핸들러 ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ 번역봇이 작동 중입니다. /help 를 입력하세요.\n"
        "✅ Translation bot is running. Type /help\n"
        "✅ 翻译机器人正在运行。请输入 /help\n"
        "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ /help\n"
        "✅ Bot dịch đang hoạt động. Gõ /help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 사용 안내 / Help / 使用指南 / សេចក្តីណែនាំ / Hướng dẫn\n\n"
        "[한국어]\n"
        "/createcode - 3일 무료 코드 생성\n"
        "/registercode [코드] - 그룹에 코드 등록\n"
        "/disconnect - 연결 해제\n"
        "/solomode - 번역모드 (3일)\n"
        "/extendcode - 연장 요청\n"
        "/paymentcheck [해시] [코드] - 결제 확인\n\n"
        "[English]\n"
        "/createcode - Create 3-day code\n"
        "/registercode [code] - Register to group\n"
        "/disconnect - Disconnect\n"
        "/solomode - Solo translation (3 days)\n"
        "/extendcode - Request extension\n"
        "/paymentcheck [txhash] [code] - Check payment\n\n"
        "[中文]\n"
        "/createcode - 创建3天免费代码\n"
        "/registercode [代码] - 注册到群组\n"
        "/disconnect - 断开连接\n"
        "/solomode - 单人翻译模式 (3天)\n"
        "/extendcode - 请求延长\n"
        "/paymentcheck [哈希] [代码] - 确认付款\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode - បង្កើតកូដ 3 ថ្ងៃ\n"
        "/registercode [code] - ចុះបញ្ជីកូដក្នុងក្រុម\n"
        "/disconnect - ផ្ដាច់ការភ្ជាប់\n"
        "/solomode - បើកបកប្រែផ្ទាល់ខ្លួន (3 ថ្ងៃ)\n"
        "/extendcode - ស្នើបន្ត\n"
        "/paymentcheck [hash] [code] - ផ្ទៀងផ្ទាត់ទូទាត់\n\n"
        "[Tiếng Việt]\n"
        "/createcode - Tạo mã miễn phí 3 ngày\n"
        "/registercode [mã] - Đăng ký nhóm\n"
        "/disconnect - Ngắt kết nối\n"
        "/solomode - Dịch cá nhân (3 ngày)\n"
        "/extendcode - Yêu cầu gia hạn\n"
        "/paymentcheck [hash] [mã] - Kiểm tra thanh toán"
    )

async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_create_code(user_id):
        await update.message.reply_text("❌ Free code limit exceeded.")
        return
    code = str(user_id)[-6:]
    register_code(code, user_id, duration_days=3)
    register_code_creation(user_id)
    await update.message.reply_text(f"✅ Your code: {code}\nUse /registercode {code} in group.")

async def register_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text("✅ Code registered to this group.")

async def solo_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_solo_mode_active(user_id):
        activate_solo_mode(user_id)
        await update.message.reply_text("✅ Solo translation mode started (3 days).")
    elif can_extend_solo_mode(user_id):
        extend_solo_mode(user_id)
        await update.message.reply_text("🔁 Solo mode extended.")
    else:
        await update.message.reply_text("⚠️ You can't extend solo mode more than twice.")

async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await disconnect_user(update, context)

async def owner_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_owner_auth(update, context)

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_set_groups(update, context)

async def owner_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_owner_commands(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_translation(update, context)
    await log_message_to_group(update, context)

async def payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_payment_check(update, context)

# ========== 실행 ==========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("createcode", create_code))
    app.add_handler(CommandHandler("registercode", register_code_command))
    app.add_handler(CommandHandler("solomode", solo_mode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("auth", owner_auth))
    app.add_handler(CommandHandler("setloggroup", set_group))
    app.add_handler(CommandHandler("setcontrolgroup", set_group))
    app.add_handler(CommandHandler("setuserloggroup", set_group))
    app.add_handler(CommandHandler("ownerhelp", owner_help))
    app.add_handler(CommandHandler("paymentcheck", payment_check))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("✅ 번역봇 실행 중...")
    app.run_polling()
