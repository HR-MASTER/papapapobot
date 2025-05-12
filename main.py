# main.py

import os
import time
import logging
import requests
from typing import Tuple
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv
import database

# ───────────────────────────────
# 환경 변수 및 로깅 설정
# ───────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")
OWNER_SECRET     = os.getenv("OWNER_SECRET")

logging.basicConfig(level=logging.INFO)

def init_bot_data(app):
    app.bot_data.setdefault("payment_invoice", {})

def format_multilang(ko, zh, km, vi) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ───────────────────────────────
# TUAPI 연동 함수
# ───────────────────────────────
def generate_address(gid: int) -> Tuple[str, str]:
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(url, json={"orderId": order_id}, headers=headers, timeout=10).json()
    if res.get("code") != 0:
        raise RuntimeError("地址生成失败")
    return res["data"]["address"], res["data"]["orderId"]

def check_deposit(order_id: str) -> float:
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(url, params={"orderId": order_id}, headers=headers, timeout=10).json()
    if resp.get("code") != 0:
        raise RuntimeError("交易查询失败")
    return sum(tx["value"] for tx in resp["data"]) / 1e6

# ───────────────────────────────
# 소유자 인증 & 제어 그룹 설정
# ───────────────────────────────
OWNER_ID        = None
CONTROL_GROUP   = None

def owner_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        gid = update.effective_chat.id
        if OWNER_ID is None or uid != OWNER_ID:
            return await update.message.reply_text("❌ 소유자 전용 명령입니다.")
        if CONTROL_GROUP is None or gid != CONTROL_GROUP:
            return await update.message.reply_text("❌ 이 그룹에서만 사용할 수 있습니다.")
        return await func(update, ctx)
    return wrapper

async def auth_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    args = ctx.args
    if not args or args[0] != OWNER_SECRET:
        return await update.message.reply_text("❌ 인증에 실패했습니다.")
    OWNER_ID = update.effective_user.id
    await update.message.reply_text("✅ 소유자 인증이 완료되었습니다.")

@owner_only
async def setcontrol_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global CONTROL_GROUP
    CONTROL_GROUP = update.effective_chat.id
    await update.message.reply_text("✅ 이 그룹을 제어 그룹으로 지정했습니다.")

# ───────────────────────────────
# /start
# ───────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ 翻译机器人正在运行。请输入 /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot đang hoạt động. Gõ /help"
        )
    )

# ───────────────────────────────
# /help (버튼+4개국어 안내)
# ───────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "[한국어]\n"
        "/createcode   – 코드 생성 (무료3일)\n"
        "/registercode – 그룹에 코드 등록\n"
        "/disconnect   – 연결 해제\n"
        "/extendcode   – 코드 연장 3일 (1회)\n"
        "/remaining    – 남은 기간 확인\n"
        "/paymentcheck – 결제확인/주소발급\n\n"
        "[中文]\n"
        "/createcode   – 创建代码 (免费3天)\n"
        "/registercode – 群组注册代码\n"
        "/disconnect   – 断开连接\n"
        "/extendcode   – 延长代码3天 (1次)\n"
        "/remaining    – 查看剩余时间\n"
        "/paymentcheck – 支付检查/地址生成\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode   – បង្កើតកូដ (ឥតគិតថ្លៃ3ថ្ងៃ)\n"
        "/registercode – ក្រុមចុះបញ្ជីកូដ\n"
        "/disconnect   – ផ្អាកការតភ្ជាប់\n"
        "/extendcode   – ពន្យារកូដ3ថ្ងៃ (1ដង)\n"
        "/remaining    – ពិនិត្យរយៈពេលនៅសល់\n"
        "/paymentcheck – ពិនិត្យទូទាត់/បង្កើតអាសយដ្ឋាន\n\n"
        "[Tiếng Việt]\n"
        "/createcode   – Tạo mã (miễn phí3ngày)\n"
        "/registercode – Nhóm đăng ký mã\n"
        "/disconnect   – Ngắt kết nối\n"
        "/extendcode   – Gia hạn mã3ngày (1 lần)\n"
        "/remaining    – Kiểm tra thời gian còn lại\n"
        "/paymentcheck – Thanh toán/địa chỉ\n"
    )
    kb = [
        [InlineKeyboardButton("CreateCode",   callback_data="btn_create")],
        [InlineKeyboardButton("RegisterCode", callback_data="btn_register")],
        [InlineKeyboardButton("Disconnect",   callback_data="btn_disconnect")],
        [InlineKeyboardButton("ExtendCode",   callback_data="btn_extend")],
        [InlineKeyboardButton("Remaining",    callback_data="btn_remaining")],
        [InlineKeyboardButton("PaymentCheck", callback_data="btn_payment")],
    ]
    await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(kb))

# ───────────────────────────────
# 버튼 콜백 핸들러
# ───────────────────────────────
async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cmd = q.data.split("_")[1]
    fake_update = Update(update.update_id, message=q.message, callback_query=q)
    if cmd == "create":
        return await createcode(fake_update, ctx)
    if cmd == "register":
        return await registercode(fake_update, ctx)
    if cmd == "disconnect":
        return await disconnect(fake_update, ctx)
    if cmd == "extend":
        return await extendcode(fake_update, ctx)
    if cmd == "remaining":
        return await remaining(fake_update, ctx)
    if cmd == "payment":
        return await paymentcheck(fake_update, ctx)

# ───────────────────────────────
# /createcode
# ───────────────────────────────
async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = database.register_code(user_id, duration_days=3)
    if code is None:
        return await update.message.reply_text(
            format_multilang(
                "⚠️ 무료 코드 발급 한도(1회) 초과",
                "⚠️ 免费次数已用尽(1次)",
                "⚠️ លើសកំណត់ឥតគិតថ្លៃ(1ដង)",
                "⚠️ Hết lượt miễn phí (1 lần)"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 코드 생성: {code} (3일간)",
            f"✅ 已创建代码: {code} (3天有效)",
            f"✅ បានបង្កើតកូដ: {code} (3ថ្ងៃ)",
            f"✅ Tạo mã: {code} (3 ngày)"
        )
    )

# ───────────────────────────────
# /registercode
# ───────────────────────────────
async def registercode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    gid = update.effective_chat.id
    if not args:
        return await update.message.reply_text("/registercode [code]")
    code = args[0]
    if not database.register_group_to_code(code, gid, duration_days=3):
        return await update.message.reply_text(
            format_multilang(
                "❌ 코드 유효하지 않거나 그룹 초과",
                "❌ 代码无效或超出群组数",
                "❌ កូដមិនមានសុពលភាព ឬក្រុមពេញ",
                "❌ Mã không hợp lệ hoặc nhóm đầy"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 그룹 등록 완료: {code} (3일간)",
            f"✅ 群组注册完成: {code} (3天有效)",
            f"✅ ក្រុមបានចុះបញ្ជី: {code} (3ថ្ងៃ)",
            f"✅ Nhóm đã đăng ký: {code} (3 ngày)"
        )
    )

# ───────────────────────────────
# /disconnect
# ───────────────────────────────
async def disconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    database.disconnect_user(gid)
    await update.message.reply_text(
        format_multilang(
            "🔌 연결이 해제되었습니다.",
            "🔌 已断开连接。",
            "🔌 ផ្តាច់ការតភ្ជាប់រួចរាល់។",
            "🔌 Ngắt kết nối."
        )
    )

# ───────────────────────────────
# /extendcode
# ───────────────────────────────
async def extendcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.extend_group(gid, duration_days=3, max_extends=1):
        rem = database.group_remaining_seconds(gid) // 86400
        await update.message.reply_text(
            format_multilang(
                f"🔁 코드 연장 완료. 남은: {rem}일",
                f"🔁 已延长. 剩余：{rem}天",
                f"🔁 ពន្យារបាន. នៅសល់: {rem}ថ្ងៃ",
                f"🔁 Đã gia hạn. Còn: {rem} ngày"
            )
        )
    else:
        await update.message.reply_text(
            format_multilang(
                "⚠️ 연장 한도(1회) 초과",
                "⚠️ 超过延长次数(1次)",
                "⚠️ លើសកំណត់ពន្យារ(1ដង)",
                "⚠️ Vượt giới hạn gia hạn (1 lần)"
            )
        )

# ───────────────────────────────
# /remaining
# ───────────────────────────────
async def remaining(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    sec = database.group_remaining_seconds(gid)
    if sec <= 0:
        msg = format_multilang(
            "❗ 등록된 코드가 없습니다.",
            "❗ 未注册代码。",
            "❗ មិនមានកូដ។",
            "❗ Không có mã."
        )
    else:
        d, h, m = sec//86400, (sec%86400)//3600, (sec%3600)//60
        msg = format_multilang(
            f"⏳ 남은 기간: {d}일 {h}시간 {m}분",
            f"⏳ 剩余：{d}天 {h}小时 {m}分钟",
            f"⏳ នៅសល់: {d}ថ្ងៃ {h}ម៉ោង {m}នាទី",
            f"⏳ Còn lại: {d}ngày {h}giờ {m}phút"
        )
    await update.message.reply_text(msg)

# ───────────────────────────────
# /paymentcheck
# ───────────────────────────────
async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id

    # 그룹 등록 여부 체크
    if not database.is_group_active(gid):
        return await update.message.reply_text(
            format_multilang(
                "❗ 등록된 코드가 없습니다.",
                "❗ 未注册代码。",
                "❗ មិនមានកូដ។",
                "❗ Không có mã."
            )
        )

    # 이전에 생성된 주문 ID 가져오기
    inv = ctx.bot_data["payment_invoice"].get(gid)
    paid = check_deposit(inv) if inv else 0.0

    # 일정 금액 이상 결제되었으면 연장
    if paid >= PLAN_USD:
        database.extend_group(gid, duration_days=3, max_extends=1)
        rem = database.group_remaining_seconds(gid)//86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ {paid} USDT 결제 확인. 남은: {rem}일",
                f"✅ 已支付 {paid} USDT。剩余：{rem}天",
                f"✅ បានទទួល {paid} USDT។ នៅសល់: {rem}ថ្ងៃ",
                f"✅ Đã nhận {paid} USDT. Còn: {rem} ngày"
            )
        )

    # 아직 결제 없으면 1회용 주소 발급
    addr, order = generate_address(gid)
    ctx.bot_data["payment_invoice"][gid] = order
    await update.message.reply_text(
        format_multilang(
            f"❗ 송금할 USDT: {PLAN_USD} → {addr}",
            f"❗ 转账 {PLAN_USD} USDT → {addr}",
            f"❗ សូមផ្ញើ {PLAN_USD} USDT → {addr}",
            f"❗ Gửi {PLAN_USD} USDT → {addr}"
        )
    )

# ───────────────────────────────
# 메시지 핸들링 (번역)
# ───────────────────────────────
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        from translator import handle_translation
        await handle_translation(update, ctx)

# ───────────────────────────────
# 봇 실행
# ───────────────────────────────
if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 소유자 인증/제어 명령
    app.add_handler(CommandHandler("auth", auth_cmd))
    app.add_handler(CommandHandler("setcontrolgroup", setcontrol_cmd))

    # 일반 명령
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_cb))
    app.add_handler(CommandHandler("createcode",   createcode))
    app.add_handler(CommandHandler("registercode", registercode))
    app.add_handler(CommandHandler("disconnect",   disconnect))
    app.add_handler(CommandHandler("extendcode",   extendcode))
    app.add_handler(CommandHandler("remaining",    remaining))
    app.add_handler(CommandHandler("paymentcheck", paymentcheck))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)
