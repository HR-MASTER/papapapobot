f"⏳ Còn lại: {d}ngày {h}giờ {m}phút"
        )
    await update.message.reply_text(text)

async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if not database.is_group_active(gid):
        return await update.message.reply_text(
            format_multilang(
                "❗ 등록된 코드가 없습니다.",
                "❗ 未注册代码。",
                "❗ មិនមានកូដចុះបញ្ជី។",
                "❗ Không có mã đăng ký."
            )
        )

    invoice = ctx.bot_data.setdefault("payment_invoice", {}).get(gid)
    paid = check_tuapi_deposit(invoice) if invoice else 0.0
    if paid >= PLAN_USD and database.extend_group(gid, duration_days=3, max_extends=2):
        rem = database.group_remaining_seconds(gid) // 86400
        return await update.message.reply_text(
            format_multilang(
                f"✅ {paid} USDT 결제 확인. 연장됨: {rem}일",
                f"✅ 已支付 {paid} USDT。已延长：{rem}天",
                f"✅ បានទទួល {paid} USDT។ ពន្យារជា: {rem}ថ្ងៃ",
                f"✅ Đã nhận {paid} USDT. Gia hạn: {rem} ngày"
            )
        )

    addr, inv = generate_one_time_address_tuapi(gid)
    ctx.bot_data["payment_invoice"][gid] = inv
    await update.message.reply_text(
        format_multilang(
            f"❗ 결제 내역 없음\n송금할 USDT: {PLAN_USD}\n주소: {addr}",
            f"❗ 未检测到支付\n请汇款：{PLAN_USD} USDT\n地址：{addr}",
            f"❗ មិនមានការទូទាត់\nផ្ញើ USDT: {PLAN_USD}\nអាសយដ្ឋាន: {addr}",
            f"❗ Không tìm thấy thanh toán\nGửi USDT: {PLAN_USD}\nĐịa chỉ: {addr}"
        )
    )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        await handle_translation(update, ctx)

if name == "__main__":
    logging.info("✅ 번역봇 시작")

    # ───────────────────────────────
    # webhook 제거를 위한 post_init 콜백
    # ───────────────────────────────
    async def drop_pending(app):
        await app.bot.delete_webhook(drop_pending_updates=True)

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(drop_pending)        # ← 여기서 webhook 삭제
        .build()
    )
    init_bot_data(app)

    handlers = [
        ("start",       start),
        ("help",        help_cmd),
        ("createcode",  createcode),
        ("registercode",registercode),
        ("disconnect",  disconnect),
        ("solomode",    solomode),
        ("extendcode",  extendcode),
        ("remaining",   remaining),
        ("paymentcheck",paymentcheck),
    ]
    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)
