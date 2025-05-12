# main.py

import os
import time
import logging
import requests
from typing import Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv
from translator import handle_translation
import database

# ───────────────────────────────
# Tron 설정을 위한 import
# ───────────────────────────────
from tronpy import Tron
from tronpy.providers import HTTPProvider

# ───────────────────────────────
# 환경 변수 및 로깅 설정
# ───────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")
TRON_API_KEY     = os.getenv("TRON_API_KEY")

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
# TUAPI 연동
# ───────────────────────────────
def generate_address(gid: int) -> Tuple[str, str]:
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(url, json={"orderId": order_id}, headers=headers).json()
    if res.get("code") != 0:
        raise RuntimeError("地址生成失败")
    return res["data"]["address"], res["data"]["orderId"]


def check_deposit(order_id: str) -> float:
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(url, params={"orderId": order_id}, headers=headers).json()
    if resp.get("code") != 0:
        raise RuntimeError("交易查询失败")
    return sum(tx["value"] for tx in resp["data"]) / 1e6


# ───────────────────────────────
# /start
# ───────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ 翻译机器人正在运行。请输入 /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot dịch đang hoạt động. Gõ /help"
        )
    )


# ───────────────────────────────
# /help (버튼+4개국어 텍스트)
# ───────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "[한국어]\n"
        "/createcode   – 코드 생성 3일 (무료 1회, 이후 결제 필요)\n"
        "/registercode – 명령어+코드 등록\n"
        "/disconnect   – 등록된 코드 연결 해제\n"
        "/extendcode   – 코드 3일 연장 (최대 1회)\n"
        "/remaining    – 남은 기간 확인\n"
        "/paymentcheck – 코드 연장/결제주소 발급\n\n"
        "[中文]\n"
        "/createcode   – 生成 3 天代码（免费1次，之后需付费）\n"
        "/registercode – 命令+注册代码\n"
        "/disconnect   – 取消已注册代码连接\n"
        "/extendcode   – 延长代码 3 天（最多1次）\n"
        "/remaining    – 查看剩余时间\n"
        "/paymentcheck – 延长代码/支付地址生成\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode   – បង្កើតកូដ 3 ថ្ងៃ (ឥតគិតថ្លៃ1ដង, បន្ទាប់ត្រូវបង់ប្រាក់)\n"
        "/registercode – បញ្ជារមុខងារ+ចុះបញ្ជីកូដ\n"
        "/disconnect   – ផ្អាកការតភ្ជាប់កូដដែលបានចុះបញ្ជី\n"
        "/extendcode   – ពន្យារកូដ 3 ថ្ងៃ (1ដងអតិបរមា)\n"
        "/remaining    – ធ្វើការត្រួតពិនិត្យរយៈពេលនៅសល់\n"
        "/paymentcheck – ពន្យារ/បញ្ចេញអាសយដ្ឋានទូទាត់\n\n"
        "[Tiếng Việt]\n"
        "/createcode   – Tạo mã 3 ngày (miễn phí 1 lần, sau đó cần trả phí)\n"
        "/registercode – Lệnh+Đăng ký mã\n"
        "/disconnect   – Hủy kết nối mã đã đăng ký\n"
        "/extendcode   – Gia hạn mã 3 ngày (tối đa 1 lần)\n"
        "/remaining    – Kiểm tra thời gian còn lại\n"
        "/paymentcheck – Gia hạn mã/Phát địa chỉ thanh toán\n"
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
# 버튼 콜백
# ───────────────────────────────
async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cmd = query.data.split("_")[1]
    if cmd == "create":
        return await createcode(update, ctx)
    if cmd == "register":
        return await registercode(update, ctx)
    if cmd == "disconnect":
        return await disconnect(update, ctx)
    if cmd == "extend":
        return await extendcode(update, ctx)
    if cmd == "remaining":
        return await remaining(update, ctx)
    if cmd == "payment":
        return await paymentcheck(update, ctx)


# ───────────────────────────────
# /createcode
# ───────────────────────────────
async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = database.register_code(user_id)
    if code is None:
        return await update.message.reply_text(
            format_multilang(
                "⚠️ 무료 코드 발급 한도(1회) 초과",
                "⚠️ 超过免费代码次数(1次)",
                "⚠️ លើសកំណត់ឥតគិតថ្លៃ(1ដង)",
                "⚠️ Vượt giới hạn miễn phí (1 lần)"
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
    args    = ctx.args
    chat_id = update.effective_chat.id
    if not args:
        return await update.message.reply_text("/registercode [code]")
    code = args[0]
    if not database.register_group_to_code(code, chat_id):
        return await update.message.reply_text(
            format_multilang(
                "❌ 코드 유효하지 않거나 그룹 초과",
                "❌ 代码无效或组数已达上限",
                "❌ កូដមិនមានសុពលភាព ឬក្រុមពេញ",
                "❌ Mã không hợp lệ hoặc nhóm đầy"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 등록 완료: {code}",
            f"✅ 注册完成: {code}",
            f"✅ ចុះបញ្ជីរ: {code}",
            f"✅ Đã đăng ký: {code}"
        )
    )


# ───────────────────────────────
# /disconnect
# ───────────────────────────────
async def disconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    database.disconnect_user(update.effective_chat.id)
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
    cid = update.effective_chat.id
    if database.extend_group(cid):
        rem = database.group_remaining_seconds(cid) // 86400
        await update.message.reply_text(
            format_multilang(
                f"🔁 코드 연장 완료. 남은: {rem}일",
                f"🔁 已延长. 剩余：{rem}天",
                f"🔁 ពន្យារ. នៅសល់: {rem}ថ្ងៃ",
                f"🔁 Đã gia hạn. Còn: {rem} ngày"
            )
        )
    else:
        await update.message.reply_text(
            format_multilang(
                "⚠️ 연장 실패",
                "⚠️ 延长失败",
                "⚠️ មិនអាចពន្យា",
                "⚠️ Không thể gia hạn"
            )
        )


# ───────────────────────────────
# /remaining
# ───────────────────────────────
async def remaining(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sec = database.group_remaining_seconds(update.effective_chat.id)
    if sec <= 0:
        msg = format_multilang(
            "❗ 등록된 코드가 없습니다.",
            "❗ 未注册代码。",
            "❗ មិនមានកូដ។",
            "❗ Không có mã."
        )
    else:
        d, h, m = sec // 86400, (sec % 86400) // 3600, (sec % 3600) // 60
        msg = format_multilang(
            f"⏳ 남은: {d}일 {h}시간 {m}분",
            f"⏳ 剩余：{d}天 {h}时 {m}分",
            f"⏳ នៅសល់: {d}ថ្ងៃ {h}ម៉ោង {m}នាទី",
            f"⏳ Còn: {d}ngày {h}giờ {m}phút"
        )
    await update.message.reply_text(msg)


# ───────────────────────────────
# /paymentcheck
# ───────────────────────────────
async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not database.is_group_active(cid):
        return await update.message.reply_text(
            format_multilang(
                "❗ 등록된 코드가 없습니다.",
                "❗ 未注册代码。",
                "❗ មិនមានកូដ។",
                "❗ Không có mã."
            )
        )
    inv = ctx.bot_data["payment_invoice"].get(cid)
    paid = check_deposit(inv) if inv else 0.0
    if paid >= PLAN_USD:
        database.extend_group(cid)
        rem = database.group_remaining_seconds(cid) // 86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ 결제 확인. 남은: {rem}일",
                f"✅ 支付成功。剩余：{rem}天",
                f"✅ បានទូទាត់. នៅសល់: {rem}ថ្ងៃ",
                f"✅ Thanh toán OK. Còn: {rem} ngày"
            )
        )
    addr, order = generate_address(cid)
    ctx.bot_data["payment_invoice"][cid] = order
    await update.message.reply_text(
        format_multilang(
            f"❗ 송금할 USDT: {PLAN_USD} → {addr}",
            f"❗ 转账 {PLAN_USD} USDT → {addr}",
            f"❗ សូមផ្ញើ {PLAN_USD} USDT → {addr}",
            f"❗ Gửi USDT: {PLAN_USD} → {addr}"
        )
    )


async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if database.is_group_active(update.effective_chat.id):
        await handle_translation(update, ctx)


# ───────────────────────────────
# 봇 구동
# ───────────────────────────────
if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 핸들러 등록
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       help_cmd))
    app.add_handler(CallbackQueryHandler(button_cb))
    app.add_handler(CommandHandler("createcode", createcode))
    app.add_handler(CommandHandler("registercode", registercode))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("extendcode", extendcode))
    app.add_handler(CommandHandler("remaining",  remaining))
    app.add_handler(CommandHandler("paymentcheck", paymentcheck))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)
