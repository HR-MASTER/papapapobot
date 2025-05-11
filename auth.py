# auth.py
# 소유자 인증, 그룹 등록, 소유자 전용 명령어 목록 제공

import os
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv
from database import (
    set_owner, is_owner,
    set_control_group, set_log_group, set_user_log_group,
    is_control_group, is_log_group, is_user_log_group,
)

load_dotenv()
OWNER_SECRET = os.getenv("OWNER_SECRET")

# 소유자 인증
async def handle_owner_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args or args[0] != OWNER_SECRET:
        await update.message.reply_text("❌ 인증 실패: 잘못된 코드입니다.")
        return
    set_owner(user_id)
    await update.message.reply_text("✅ 소유자 인증이 완료되었습니다.")

# 그룹 설정 명령어 처리
async def handle_set_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    command = update.message.text

    if not is_owner(user_id):
        await update.message.reply_text("❌ 소유자만 이 명령어를 사용할 수 있습니다.")
        return

    if command.startswith("/setcontrolgroup"):
        set_control_group(chat_id)
        await update.message.reply_text(
            "✅ 소유자 제어 그룹이 등록되었습니다.\n\n"
            "Control group registered.\n控制群已设定。\nក្រុមគ្រប់គ្រងត្រូវបានកំណត់។"
        )
    elif command.startswith("/setloggroup"):
        set_log_group(chat_id)
        await update.message.reply_text(
            "✅ 로그 기록 그룹이 등록되었습니다.\n\n"
            "Log group registered.\n日志群已设定。\nក្រុមកំណត់ត្រាត្រូវបានកំណត់។"
        )
    elif command.startswith("/setuserloggroup"):
        set_user_log_group(chat_id)
        await update.message.reply_text(
            "✅ 사용자 메시지 기록 그룹이 등록되었습니다.\n\n"
            "User log group registered.\n用户日志群已设定。\nក្រុមកំណត់ត្រាអ្នកប្រើត្រូវបានកំណត់។"
        )

# 소유자 명령어 안내
async def show_owner_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ 소유자만 사용 가능합니다.")
        return

    await update.message.reply_text(
        "📋 소유자 명령어 목록 (/소유자명령어)\n\n"
        "- /인증 [코드] (소유자 등록)\n"
        "- /setcontrolgroup (제어 명령 수신 그룹 지정)\n"
        "- /setloggroup (번역 로그 그룹 지정)\n"
        "- /setuserloggroup (사용자 메시지 기록 그룹 지정)\n"
        "- /한정 [코드] [30days] (기간 제한 코드 발급)\n"
        "- /영구코드 [코드명] (무기한 코드 발급)\n"
        "- /setprice [30d/1y] [금액] (요금 설정)\n"
        "- /listmaster, /listmaster chat [코드] 등 (로그 확인)"
    )
