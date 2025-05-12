import os
import time
import logging
import requests
from typing import Tuple

from tronpy import Tron
from tronpy.keys import PrivateKey
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv

import database
from translator import handle_translation

# ───────────────────────────────
# 환경 변수 및 로깅 설정
# ───────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
OWNER_SECRET     = os.getenv("OWNER_SECRET")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))

# TronGrid 설정
TRON_FULL_NODE   = os.getenv("TRON_FULL_NODE", "https://api.trongrid.io")
TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY")
TRON_API_KEY     = os.getenv("TRON_API_KEY")  # 새로 추가된 전용 API 키

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
# Tronpy 클라이언트 초기화
# ───────────────────────────────
tron = Tron(
    full_node=TRON_FULL_NODE,
    solidity_node=TRON_FULL_NODE,
    event_server=TRON_FULL_NODE
)
if TRON_API_KEY:
    # tronpy 내부 HTTP 요청 헤더에 PRO-API-KEY 추가
    tron.default_headers["TRON-PRO-API-KEY"] = TRON_API_KEY

my_priv_key = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY))
MY_ADDRESS   = my_priv_key.public_key.to_base58check_address()

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
        "/paymentcheck – ពន្យារកូដ/បញ្ចេញអាសយដ្ឋានទូទាត់\n\n"
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
# /paymentcheck 수정 부분
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

    order_id = ctx.bot_data["payment_invoice"].get(cid)
    paid = 0.0
    if order_id:
        try:
            # TronGrid 이벤트로 USDT 수신 확인
            events = tron.trx.get_event_result(
                contract_address="TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj",
                event_name="Transfer",
                only_confirmed=True,
                address=MY_ADDRESS
            )
            for ev in events:
                data = ev["result"]
                if data.get("memo") == order_id:
                    paid += int(data["value"]) / 1e6
        except Exception:
            return await update.message.reply_text(
                format_multilang(
                    "⚠️ 결제 확인 중 오류 발생",
                    "⚠️ Error checking payment",
                    "⚠️ មានកំហុសពេលពិនិត្យការទូទាត់",
                    "⚠️ Lỗi khi kiểm tra thanh toán"
                )
            )

    if paid >= PLAN_USD:
        database.extend_group(cid)
        rem = database.group_remaining_seconds(cid) // 86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ {paid} USDT 결제 확인. 남은: {rem}일",
                f"✅ {paid} USDT paid. Remaining: {rem} days",
                f"✅ ទទួលបាន {paid} USDT។ នៅសល់: {rem} ថ្ងៃ",
                f"✅ Đã nhận {paid} USDT. Còn: {rem} ngày"
            )
        )

    if not order_id:
        order_id = f"{cid}-{int(time.time())}"
        ctx.bot_data["payment_invoice"][cid] = order_id

    text = format_multilang(
        f"❗ 송금할 USDT: {PLAN_USD}\n주소: {MY_ADDRESS}\n메모: {order_id}",
        f"❗ Please send {PLAN_USD} USDT\nAddress: {MY_ADDRESS}\nMemo: {order_id}",
        f"❗ សូមផ្ញើ {PLAN_USD} USDT\nអាសយដ្ឋាន: {MY_ADDRESS}\nជំរៅ: {order_id}",
        f"❗ Vui lòng gửi {PLAN_USD} USDT\nĐịa chỉ: {MY_ADDRESS}\nGhi chú: {order_id}"
    )
    kb = [
        [
            InlineKeyboardButton("Extend Code", callback_data="btn_extend"),
            InlineKeyboardButton("New Code",    callback_data="btn_create"),
        ]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ───────────────────────────────
# 나머지 핸들러 및 봇 구동부는 이전과 동일
# ───────────────────────────────
# (start, help_cmd, button_cb, createcode, registercode,
#  disconnect, extendcode, remaining, message_handler 등)

if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 여기에 나머지 CommandHandler, CallbackQueryHandler, MessageHandler 등록

    app.run_polling(drop_pending_updates=True)
