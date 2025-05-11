import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import Update
from dotenv import load_dotenv
from translator import handle_translation
from database import (register_code, is_code_valid, register_group, disconnect_user,
                      activate_solo_mode, can_extend_solo_mode, extend_solo_mode)
from auth import handle_owner_auth, handle_set_groups, show_owner_commands
from logger import log_message_to_group
from payment import handle_payment_check

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 그룹 등록 상태를 전역에 저장
group_registry = {}
def mark_group(code, chat_id):
    group_registry.setdefault(chat_id,False)
    group_registry[chat_id] = True

# ========== 명령어 ==========
async def start(u,c):
    await u.message.reply_text("✅ Bot running. /help")

async def help_cmd(u,c):
    await u.message.reply_text("📌 Help:\n[EN] /createcode, /registercode, /disconnect, /solomode, /extendcode, /paymentcheck\n[KO] …\n[ZH] …\n[KM] …\n[VI] …")

async def create_code(u,c):
    user = u.effective_user.id
    code = str(user)[-6:]
    register_code(code, user, 3)
    await u.message.reply_text(f"Your code: {code}")

async def register_code_cmd(u,c):
    code = c.args[0] if c.args else None
    if not code or not is_code_valid(code):
        await u.message.reply_text("❌ Invalid code")
        return
    chat = u.effective_chat.id
    register_group(code, chat)
    mark_group(code, chat)
    await u.message.reply_text("✅ Code registered")

async def solo_mode(u,c):
    user=u.effective_user.id
    if not can_extend_solo_mode(user):
        activate_solo_mode(user)
        await u.message.reply_text("Solo mode on")
    else:
        extend_solo_mode(user)
        await u.message.reply_text("Solo mode extended")

async def disconnect(u,c):
    await disconnect_user(u,c)

async def owner_auth(u,c):
    await handle_owner_auth(u,c)
async def set_groups(u,c):
    await handle_set_groups(u,c)
async def owner_help(u,c):
    await show_owner_commands(u,c)
async def payment_check(u,c):
    await handle_payment_check(u,c)

# ========== 실행 ==========
if __name__=="__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # 기본
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    # 코드
    app.add_handler(CommandHandler("createcode", create_code))
    app.add_handler(CommandHandler("registercode", register_code_cmd))
    app.add_handler(CommandHandler("solomode", solo_mode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    # 소유자
    app.add_handler(CommandHandler("auth", owner_auth))
    app.add_handler(CommandHandler("setloggroup", set_groups))
    app.add_handler(CommandHandler("setcontrolgroup", set_groups))
    app.add_handler(CommandHandler("setuserloggroup", set_groups))
    app.add_handler(CommandHandler("ownerhelp", owner_help))
    # 결제
    app.add_handler(CommandHandler("paymentcheck", payment_check))
    # 메시지 번역
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translation))
    app.run_polling()
