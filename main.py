# main.py
# 텔레그램 번역봇 실행 진입점 (영문 명령어 + 5개국어 안내 포함)

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
        "✅ Translation bot is active.\n"
        "Use /help to learn how to use it.\n\n"
        "✅ 번역봇이 작동 중입니다.\n사용법은 /help 입력.\n\n"
        "✅ 翻译机器人运行中。\n请输入 /help 查看使用方式。\n\n"
        "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។\nសូមប្រើ /help ដើម្បីមើលការណែនាំ។\n\n"
        "✅ Bot dịch đang hoạt động.\nGõ /help để xem hướng dẫn sử dụng."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Help – Multi-language Guide (5개국어 안내)\n\n"
        "[한국어]\n"
        "/createcode - 3일 무료 코드 생성\n"
        "/registercode [코드] - 그룹에 코드 등록\n"
        "/disconnect - 연결 해제\n"
        "/solomode - 혼자 번역모드 3일 시작\n"
        "/extendcode - 코드 연장 요청\n"
        "/paymentcheck [해시] [코드] - 결제 확인\n\n"
        "[English]\n"
        "/createcode - Create free 3-day code\n"
        "/registercode [code] - Register code to group\n"
        "/disconnect - Disconnect\n"
        "/solomode - Solo translation mode (3 days)\n"
        "/extendcode - Request extension\n"
        "/paymentcheck [txhash] [code] - Check payment\n\n"
        "[中文]\n"
        "/createcode - 生成3天免费代码\n"
        "/registercode [代码] - 向群注册代码\n"
        "/disconnect - 断开连接\n"
        "/solomode - 单人翻译模式 (3天)\n"
        "/extendcode - 请求延长\n"
        "/paymentcheck [哈希] [代码] - 验证付款\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode - បង្កើតកូដ 3 ថ្ងៃ\n"
        "/registercode [code] - ចុះបញ្ជីកូដក្នុងក្រុម\n"
        "/disconnect - ផ្ដាច់ការភ្ជាប់\n"
        "/solomode - បើកមូដបកប្រែផ្ទាល់ខ្លួន (3 ថ្ងៃ)\n"
        "/extendcode - ស្នើបន្ត\n"
        "/paymentcheck [hash] [code] - ផ្ទៀងផ្ទាត់ការទូទាត់\n\n"
        "[Tiếng Việt]\n"
        "/createcode - Tạo mã miễn phí 3 ngày\n"
        "/registercode [mã] - Đăng ký mã vào nhóm\n"
        "/disconnect - Ngắt kết nối\n"
        "/solomode - Chế độ dịch cá nhân (3 ngày)\n"
        "/extendcode - Yêu cầu gia hạn\n"
        "/paymentcheck [mã giao dịch] [mã] - Kiểm tra thanh toán"
    )

async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_create_code(user_id):
        await update.message.reply_text("❌ You have exceeded the monthly free code limit.")
        return
    code = str(user_id)[-6:]
    register_code(code, user_id, duration_days=3)
    register_code_creation(user_id)
    await update.message.reply_text(f"✅ Your code: {code}\nUse /registercode {code} in your group.")

async def register_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args[0]) != 6:
        await update.message.reply_text("❗ Usage: /registercode [6-digit-code]")
        return
    code = args[0]
    if not is_code_valid(code):
        await update.message.reply_text("❌ Code not found or expired.")
        return
    chat_id = update.effective_chat.id
    if not register_group_to_code(code, chat_id):
        await update.message.reply_text("⚠️ This code is already used in 2 groups.")
        return
    await update.message.reply_text("✅ Code registered to this group. Translation is now active.")

async def solo_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_solo_mode_active(user_id):
        activate_solo_mode(user_id)
        await update.message.reply_text("✅ Solo translation mode activated for 3 days.")
    elif can_extend_solo_mode(user_id):
        extend_solo_mode(user_id)
        await update.message.reply_text("🔁 Solo mode extended by 3 more days.")
    else:
        await update.message.reply_text("⚠️ You cannot extend solo mode more than twice.")

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
