# main.py
import os
import time
import logging
import secrets
import requests
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from translator import handle_translation
import database

# ─────────────────────────────
# 환경 변수 및 로깅 설정
# ─────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")           # Telegram Bot Token
GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY")      # Google Translate API Key
OWNER_SECRET     = os.getenv("OWNER_SECRET")        # 소유자 인증 비밀번호
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")      # e.g. https://api.tusdtapi.com
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")
TUAPI_API_SECRET = os.getenv("TUAPI_API_SECRET")

logging.basicConfig(level=logging.INFO)

# 봇 객체 생성 (Webhook 충돌 방지)
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

def init_bot_data(app):
    # 결제 인보이스 저장용
    app.bot_data.setdefault("payment_invoice", {})

# 4개국어 포맷 헬퍼
def format_multilang(ko: str, zh: str, km: str, vi: str) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# TuAPI 주소 생성
def generate_one_time_address_tuapi(gid: int) -> Tuple[str,str]:
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(url, json={"orderId": order_id}, headers=headers, timeout=10).json()
    if res.get("code") != 0:
        raise RuntimeError("TuAPI address generation failed")
    return res["data"]["address"], res["data"]["orderId"]

# TuAPI 입금 확인
def check_tuapi_deposit(order_id: str) -> float:
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(url, params={"orderId": order_id}, headers=headers, timeout=10).json()
    if resp.get("code") != 0:
        raise RuntimeError("TuAPI transaction check failed")
    return sum(tx["value"] for tx in resp["data"]) / 1e6

# ─────────────────────────────
# 커맨드 핸들러
# ─────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """봇 시작 안내문 (4개국어)"""
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ Translation bot is running. Type /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot dịch đang hoạt động. Gõ /help"
        )
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """명령어 안내 (/help)"""
    await update.message.reply_text(
        format_multilang(
            "/createcode – 3일 무료 코드 생성\n/registercode [코드]\n/disconnect\n/solomode\n/extendcode\n/remaining\n/paymentcheck",
            "/createcode – Create 3-day code\n/registercode [code]\n/disconnect\n/solomode\n/extendcode\n/remaining\n/paymentcheck",
            "/createcode – បង្កើតកូដ3ថ្ងៃ\n/registercode [កូដ]\n/disconnect\n/solomode\n/extendcode\n/remaining\n/paymentcheck",
            "/createcode – Tạo mã3ngày\n/registercode [mã]\n/disconnect\n/solomode\n/extendcode\n/remaining\n/paymentcheck"
        )
    )

async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/createcode: 새로운 6자리 코드 생성 (3일)"""
    uid = update.effective_user.id
    code = secrets.token_hex(3)  # 간단히 6자리 hex
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
    """/registercode [코드]: 그룹에 코드 연결 시작"""
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
    """/disconnect: 그룹 연결 해제"""
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
    """/solomode: 솔로 모드(1:1) 3일간 활성화"""
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
    """/extendcode: 그룹 코드 3일 연장 (최대2회)"""
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
    """/remaining: 남은 그룹 코드 유효기간 표시"""
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
    """/paymentcheck: TusdtAPI로 입금 확인 후 연장 또는 새 주소 발급"""
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

    # 이전 invoice 조회
    invoice = ctx.bot_data.setdefault("payment_invoice", {}).get(gid)
    paid = check_tuapi_deposit(invoice) if invoice else 0.0
    required = PLAN_USD
    # 결제 확인 시 연장
    if paid >= required and database.extend_group(gid, duration_days=3, max_extends=2):
        rem = database.group_remaining_seconds(gid)//86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ {paid} USDT 결제 확인. 연장됨: {rem}일",
                f"✅ {paid} USDT paid. Extended: {rem} days",
                f"✅ បានទទួល {paid} USDT។ ពន្យារពេល: {rem} ថ្ងៃ",
                f"✅ Đã nhận {paid} USDT. Gia hạn: {rem} ngày"
            )
        )

    # 새 1회용 주소 발급
    addr, new_invoice = generate_one_time_address_tuapi(gid)
    ctx.bot_data["payment_invoice"][gid] = new_invoice
    await update.message.reply_text(
        format_multilang(
            f"❗ 결제 내역 없음\n송금할 USDT: {required}\n주소: {addr}",
            f"❗ No payment found\nSend USDT: {required}\nAddress: {addr}",
            f"❗ មិនមានការទូទាត់\nផ្ញេ USDT: {required}\nអាសយដ្ឋាន: {addr}",
            f"❗ Không tìm thấy thanh toán\nGửi USDT: {required}\nĐịa chỉ: {addr}"
        )
    )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """일반 메시지: 그룹이 활성 상태면 번역 처리"""
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        await handle_translation(update, ctx)

if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 핸들러 등록
    cmds = [
        ("start", start), ("help", help_cmd),
        ("createcode", createcode), ("registercode", registercode),
        ("disconnect", disconnect), ("solomode", solomode),
        ("extendcode", extendcode), ("remaining", remaining),
        ("paymentcheck", paymentcheck)
    ]
    for cmd, fn in cmds:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)
