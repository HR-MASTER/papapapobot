# logger.py
# 유저 간 메시지를 실시간으로 소유자 로그 그룹에 전송

from telegram import Update
from telegram.ext import ContextTypes
from database import is_log_group

# 메시지 전송 로그를 로그 그룹에 전달
async def log_message_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message = update.message
    if not message:
        return

    # 소유자 로그 그룹이 아닐 경우 무시
    if not is_log_group(chat_id):
        return

    user = update.effective_user
    user_name = user.full_name or f"User {user.id}"
    msg = message.text or "[미지원 메시지 유형]"

    log_text = f"[{user_name} | {user.id}]\n{msg}"
    await context.bot.send_message(chat_id=chat_id, text=log_text)
