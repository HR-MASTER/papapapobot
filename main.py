# main.py
import os
import time
import logging
import secrets
import requests
from typing import Tuple                # ← Tuple을 여기서 import
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from translator import handle_translation
import database

# ─────────────────────────────
# 환경 변수 및 로깅 설정
# ─────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY")
OWNER_SECRET     = os.getenv("OWNER_SECRET")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")
TUAPI_API_SECRET = os.getenv("TUAPI_API_SECRET")

logging.basicConfig(level=logging.INFO)

# 봇 객체 생성 (Webhook 충돌 방지는 run_polling의 drop_pending_updates=True로 처리)
bot = Bot(BOT_TOKEN)
# ← 아래 줄을 제거했습니다. delete_webhook은 async이므로 module 레벨에서 await할 수 없어 경고가 발생합니다.
# bot.delete_webhook(drop_pending_updates=True)

def init_bot_data(app):
    app.bot_data.setdefault("payment_invoice", {})

def format_multilang(ko: str, zh: str, km: str, vi: str) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ─────────────────────────────
# Tuapi 연동 함수
# ─────────────────────────────
def generate_one_time_address_tuapi(gid: int) -> Tuple[str, str]:
    """Tuapi로 1회용 입금 주소+주문ID 생성"""
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(
        url, json={"orderId": order_id}, headers=headers, timeout=10
    ).json()
    if res.get("code") != 0:
        raise RuntimeError("TuAPI 주소 생성 실패")
    return res["data"]["address"], res["data"]["orderId"]

def check_tuapi_deposit(order_id: str) -> float:
    """Tuapi로 해당 주문의 입금 합계 조회 (USDT 단위)"""
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(
        url, params={"orderId": order_id}, headers=headers, timeout=10
    ).json()
    if resp.get("code") != 0:
        raise RuntimeError("TuAPI 거래 조회 실패")
    # value는 트론 단위(sun), 1e6 나눠서 USDT
    return sum(tx["value"] for tx in resp["data"]) / 1e6

# ─────────────────────────────
# Command Handlers
# ─────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ Translation bot is running. Type /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot dịch đang hoạt động. Gõ /help"
        )
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
        "[한국어]\n"
        "/createcode – 3일 무료 코드 생성\n"
        "/registercode [코드] – 그룹에 코드 등록\n"
        "/disconnect – 연결 해제\n"
        "/solomode – 솔로 모드 (3일)\n"
        "/extendcode – 코드 3일 연장 (최대 2회)\n"
        "/remaining – 남은 기간 확인\n"
        "/paymentcheck – 결제 확인 및 연장/주소 발급\n\n"
        "[English]\n"
        "/createcode – Create 3-day free code\n"
        "/registercode [code] – Register code in group\n"
        "/disconnect – Disconnect\n"
        "/solomode – Solo mode (3 days)\n"
        "/extendcode – Extend code by 3 days (max 2)\n"
        "/remaining – Check remaining time\n"
        "/paymentcheck – Check payment / Extend or get address\n\n"
        "[中文]\n"
        "/createcode – 生成 3 天免费代码\n"
        "/registercode [代码] – 在群组注册代码\n"
        "/disconnect – 断开连接\n"
        "/solomode – 独享模式（3 天）\n"
        "/extendcode – 延长代码 3 天（最多 2 次）\n"
        "/remaining – 查询剩余时间\n"
        "/paymentcheck – 检查支付 / 延长或获取地址\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode – បង្កើតកូដ 3 ថ្ងៃឥតគិតថ្លៃ\n"
        "/registercode [កូដ] – ចុះបញ្ជីកូដក្នុងក្រុម\n"
        "/disconnect – ផ្អាកការតភ្ជាប់\n"
        "/solomode – ម៉ូដផ្ទាល់ខ្លួន (3 ថ្ងៃ)\n"
        "/extendcode – ពន្យារកូដ 3 ថ្ងៃ (2 ដងអតិបរមា)\n"
        "/remaining – ពិនិត្យមើលពេលនៅសល់\n"
        "/paymentcheck – ពិនិត្យការទូទាត់ / ពន្យារឬទទួលអាសយដ្ឋាន\n\n"
        "[Tiếng Việt]\n"
        "/createcode – Tạo mã miễn phí 3 ngày\n"
        "/registercode [mã] – Đăng ký mã trong nhóm\n"
        "/disconnect – Ngắt kết nối\n"
        "/solomode – Chế độ solo (3 ngày)\n"
        "/extendcode – Gia hạn mã 3 ngày (tối đa 2 lần)\n"
        "/remaining – Kiểm tra thời gian còn lại\n"
        "/paymentcheck – Kiểm tra thanh toán / Gia hạn hoặc nhận địa chỉ"
        )
    )

async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = secrets.token_hex(3)
    database.register_code(uid, code, duration_days=3)
    await update.message.reply_text(
        format_multilang(
            f"✅ 코드 생성: {code} (3일간 유효)",
            f"✅ Code created: {code} (valid 3 days)",
            f"✅ បានបង្កើតកូដ: {code} (3ថ្ងៃ)",
            f"✅ Tạo mã: {code} (3ngày)"
        )
    )

async def registercode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args; gid = update.effective_chat.id
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ /registercode [6자리 코드]")
    code = args[0]
    if not database.register_group_to_code(code, gid, duration_days=3):
        return await update.message.reply_text(
            format_multilang(
                "❌ 코드 유효하지 않거나 이미 등록됨",
                "❌ Code invalid or already registered",
                "❌ កូដមិនមានសុពលភាព ឬបានចុះបញ្ជីរួច",
                "❌ Mã không hợp lệ hoặc đã đăng ký"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 그룹 등록 완료: {code} (3일간)",
            f"✅ Group registered: {code} (3 days)",
            f"✅ ក្រុមបានចុះបញ្ជី: {code} (3ថ្ងៃ)",
            f"✅ Nhóm đã đăng ký: {code} (3 ngày)"
        )
    )

async def disconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    database.disconnect_user(gid)
    await update.message.reply_text(
        format_multilang(
            "🔌 연결이 해제되었습니다.",
            "🔌 Disconnected.",
            "🔌 ផ្តាច់ការតភ្ជាប់រួចរាល់។",
            "🔌 Ngắt kết nối."
        )
    )

async def solomode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    database.activate_solo_mode(uid, duration_days=3)
    await update.message.reply_text(
        format_multilang(
            "✅ 솔로 모드 시작 (3일간)",
            "✅ Solo mode started (3 days)",
            "✅ Solo Mode ចាប់ផ្តើម (3ថ្ងៃ)",
            "✅ Bắt đầu solo mode (3 ngày)"
        )
    )

async def extendcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.extend_group(gid, duration_days=3, max_extends=2):
        rem = database.group_remaining_seconds(gid)//86400
        await update.message.reply_text(
            format_multilang(
                f"🔁 코드 3일 연장 완료. 남은 기간: {rem}일",
                f"🔁 Code extended 3 days. Remaining: {rem} days",
                f"🔁 ពន្យារពេល 3 ថ្ងៃ. នៅសល់: {rem} ថ្ងៃ",
                f"🔁 Gia hạn 3 ngày. Còn lại: {rem} ngày"
            )
        )
    else:
        await update.message.reply_text(
            format_multilang(
                "⚠️ 연장 한도(2회) 초과",
                "⚠️ Extension limit (2) reached",
                "⚠️ លើសកំណត់ពន្យារ(2ដង)",
                "⚠️ Vượt giới hạn gia hạn(2 lần)"
            )
        )

async def remaining(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    sec = database.group_remaining_seconds(gid)
    if sec <= 0:
        text = format_multilang(
            "❗ 등록된 코드가 없습니다.",
            "❗ No code registered.",
            "❗ មិនមានកូដចុះបញ្ជី។",
            "❗ Không có mã đăng ký."
        )
    else:
        d, h, m = sec//86400, (sec%86400)//3600, (sec%3600)//60
        text = format_multilang(
            f"⏳ 남은 기간: {d}일 {h}시간 {m}분",
            f"⏳ Remaining: {d}d {h}h {m}m",
            f"⏳ នៅសល់: {d}ថ្ងៃ {h}ម៉ោង {m}នាទី",
            f"⏳ Còn lại: {d}ngày {h}giờ {m}phút"
        )
    await update.message.reply_text(text)

async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if not database.is_group_active(gid):
        return await update.message.reply_text(
            format_multilang(
                "❗ 등록된 코드가 없습니다.",
                "❗ No code registered.",
                "❗ មិនមានកូដចុះបញ្ជី។",
                "❗ Không có mã đăng ký."
            )
        )

    invoice = ctx.bot_data.setdefault("payment_invoice", {}).get(gid)
    paid = check_tuapi_deposit(invoice) if invoice else 0.0
    if paid >= PLAN_USD and database.extend_group(gid, duration_days=3, max_extends=2):
        rem = database.group_remaining_seconds(gid)//86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ {paid} USDT 결제 확인. 연장됨: {rem}일",
                f"✅ {paid} USDT paid. Extended: {rem} days",
                f"✅ បានទទួល {paid} USDT។ ពន្យារពេល: {rem} ថ្ងៃ",
                f"✅ Đã nhận {paid} USDT. Gia hạn: {rem} ngày"
            )
        )

    addr, inv = generate_one_time_address_tuapi(gid)
    ctx.bot_data["payment_invoice"][gid] = inv
    await update.message.reply_text(
        format_multilang(
            f"❗ 결제 내역 없음\n송금할 USDT: {PLAN_USD}\n주소: {addr}",
            f"❗ No payment found\nSend USDT: {PLAN_USD}\nAddress: {addr}",
            f"❗ មិនមានការទូទាត់\nផ្ញើ USDT: {PLAN_USD}\nអាសយដ្ឋាន: {addr}",
            f"❗ Không tìm thấy thanh toán\nGửi USDT: {PLAN_USD}\nĐịa chỉ: {addr}"
        )
    )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        await handle_translation(update, ctx)

if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    handlers = [
        ("start", start), ("help", help_cmd),
        ("createcode", createcode), ("registercode", registercode),
        ("disconnect", disconnect), ("solomode", solomode),
        ("extendcode", extendcode), ("remaining", remaining),
        ("paymentcheck", paymentcheck),
    ]
    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # drop_pending_updates=True 로 기존 업데이트 무시
    app.run_polling(drop_pending_updates=True)
