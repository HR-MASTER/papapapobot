# main.py

import os
import time
import logging
import requests
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

from translator import handle_translation
import database

# 환경 변수 로드
load_dotenv()
BOT_TOKEN               = os.getenv("BOT_TOKEN")
TRONGRID_API_KEY        = os.getenv("TRONGRID_API_KEY")
TRC20_CONTRACT_ADDRESS  = os.getenv("TRC20_CONTRACT_ADDRESS")
TRC20_RECEIVER_ADDRESS  = os.getenv("TRC20_RECEIVER_ADDRESS")
TRON_API_BASE           = "https://api.trongrid.io"

logging.basicConfig(level=logging.INFO)

# Polling 충돌 제거
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

def init_bot_data(app):
    if "is_group_registered" not in app.bot_data:
        app.bot_data["is_group_registered"] = {}

def fetch_trc20_events(since_ms: int) -> list[dict]:
    url = f"{TRON_API_BASE}/v1/contracts/{TRC20_CONTRACT_ADDRESS}/events"
    params = {
        "only_confirmed": "true",
        "only_to": "true",
        "limit": 200,
        "min_block_timestamp": since_ms
    }
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY
    res = requests.get(url, params=params, headers=headers, timeout=10)
    if res.status_code != 200:
        logging.warning("TronGrid 이벤트 조회 실패 %s", res.status_code)
        return []
    return res.json().get("data", [])

# ───────────────────────────────
# 커맨드 핸들러
# ───────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✅ 번역봇 작동 중. /help\n"
        "✅ Translation bot is running. Type /help\n"
        "✅ 翻译机器人运行中。请输入 /help\n"
        "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ ក្រាប់ /help\n"
        "✅ Bot dịch đang hoạt động. Gõ /help"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Help – 다국어 안내\n\n"
        "[한국어]\n"
        "/createcode       – 3일 무료 코드 생성 (중복 불가)\n"
        "/registercode [코드] – 그룹에 코드 등록 (3일 타이머)\n"
        "/disconnect       – 연결 해제 (등록 정보 삭제)\n"
        "/solomode         – 솔로 모드 시작 (1:1 채팅, 3일)\n"
        "/extendcode       – 코드 30일 연장 요청 (최대 2회)\n"
        "/remaining        – 남은 기간 조회 (일·시·분)\n"
        "/paymentcheck     – USDT 결제 자동 확인 및 연장\n\n"
        "[English]\n"
        "/createcode       – Create a 3-day free code (no duplicates)\n"
        "/registercode [code] – Register code to this group (3-day timer)\n"
        "/disconnect       – Disconnect and delete registration\n"
        "/solomode         – Start solo mode (1:1 chat, 3 days)\n"
        "/extendcode       – Request 30-day extension (max 2 times)\n"
        "/remaining        – Check remaining time (days/hours/min)\n"
        "/paymentcheck     – Auto-check USDT payment & extend\n\n"
        "[中文]\n"
        "/createcode       – 生成 3 天免费代码（不重复）\n"
        "/registercode [代码] – 在本群注册代码（启动3天计时）\n"
        "/disconnect       – 取消连接并删除注册信息\n"
        "/solomode         – 开始独奏模式（1:1 聊天，3 天）\n"
        "/extendcode       – 请求延长 30 天（最多2次）\n"
        "/remaining        – 查询剩余时间（日/时/分）\n"
        "/paymentcheck     – 自动检查 USDT 支付并延长\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode       – បង្កើតកូដឥតគិតថ្លៃ 3 ថ្ងៃ (មិនម្តងទៀត)\n"
        "/registercode [កូដ] – ចុះបញ្ជីកូដ (3 ថ្ងៃកំណត់)\n"
        "/disconnect       – ដកចេញពីការតភ្ជាប់ និងលុបព័ត៌មាន\n"
        "/solomode         – របៀប Solo (1:1, 3 ថ្ងៃ)\n"
        "/extendcode       – សំណើពន្យារ 30 ថ្ងៃ (2 ដង)\n"
        "/remaining        – ពិនិត្យពេលនៅសល់\n"
        "/paymentcheck     – ពិនិត្យទូទាត់ USDT & ពន្យារ\n\n"
        "[Tiếng Việt]\n"
        "/createcode       – Tạo mã miễn phí 3 ngày (không trùng)\n"
        "/registercode [mã] – Đăng ký mã (bộ đếm 3 ngày)\n"
        "/disconnect       – Ngắt kết nối & xóa đăng ký\n"
        "/solomode         – Chế độ solo (1:1, 3 ngày)\n"
        "/extendcode       – Yêu cầu gia hạn 30 ngày (2 lần)\n"
        "/remaining        – Kiểm tra thời gian còn lại\n"
        "/paymentcheck     – Tự động kiểm tra thanh toán USDT & gia hạn"
    )

async def createcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = database.register_code(uid, duration_days=3)
    await update.message.reply_text(f"✅ Your code: {code} (3일간 유효)")

async def registercode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    gid = update.effective_chat.id
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ Usage: /registercode [6-digit code]")
    code = args[0]
    if not database.is_code_valid(code):
        return await update.message.reply_text("❌ 코드 유효하지 않거나 만료됨")
    if not database.register_group_to_code(code, gid):
        return await update.message.reply_text("⚠️ 이미 등록되었거나 제한초과")
    context.bot_data["is_group_registered"][gid] = True
    await update.message.reply_text("✅ 그룹 등록 완료 (3일 후 만료)")

async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.disconnect_user(update, context)

async def solomode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    database.activate_solo_mode(uid, duration_days=3)
    await update.message.reply_text("✅ 솔로 모드 시작 (3일)")

async def extendcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if not database.is_group_active(gid):
        return await update.message.reply_text("❗ 그룹에 등록된 코드가 없습니다.")
    if database.extend_group(gid, duration_days=30):
        rem = database.group_remaining_seconds(gid)
        days = rem // 86400
        await update.message.reply_text(f"🔁 30일 연장 완료. 남은 기간: {days}일")
    else:
        await update.message.reply_text("⚠️ 연장 한도(2회) 초과. 30 USDT 결제 필요")

async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    sec = database.group_remaining_seconds(gid)
    if sec <= 0:
        return await update.message.reply_text("❗ 코드 등록 없거나 만료됨")
    days = sec // 86400
    hours = (sec % 86400) // 3600
    mins = (sec % 3600) // 60
    await update.message.reply_text(f"⏳ 남은 기간: {days}일 {hours}시간 {mins}분")

async def paymentcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if not database.is_group_active(gid):
        return await update.message.reply_text("❗ 코드가 없습니다.")
    last_ms = database.get_last_payment_check(gid)
    events = fetch_trc20_events(last_ms)
    now_ms = int(time.time() * 1000)
    paid = False
    amount = 0

    for ev in events:
        to_addr = ev.get("result", {}).get("to_address", "").lower()
        if to_addr == TRC20_RECEIVER_ADDRESS.lower():
            amount = int(ev["result"].get("value", "0")) / 1e6
            if amount >= 30:
                paid = True
                break

    database.update_last_payment_check(gid, now_ms)

    if paid:
        if database.extend_group(gid, duration_days=30):
            rem = database.group_remaining_seconds(gid)
            days = rem // 86400
            return await update.message.reply_text(
                f"✅ {amount} USDT 결제 확인. 30일 연장 완료. 남은 기간: {days}일"
            )
        else:
            return await update.message.reply_text("⚠️ 이미 2회 연장되었습니다.")
    else:
        return await update.message.reply_text(
            f"❗ 최근 결제가 없습니다.\n30 USDT를 {TRC20_RECEIVER_ADDRESS}로 보내주세요."
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if context.bot_data.get("is_group_registered", {}).get(gid):
        await handle_translation(update, context)

# ──────── 봇 실행 ────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("createcode", createcode))
    app.add_handler(CommandHandler("registercode", registercode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("solomode", solomode))
    app.add_handler(CommandHandler("extendcode", extendcode))
    app.add_handler(CommandHandler("remaining", remaining))
    app.add_handler(CommandHandler("paymentcheck", paymentcheck))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("✅ 번역봇 실행 중...")
    app.run_polling(drop_pending_updates=True)
