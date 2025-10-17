import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Env
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # e.g. https://mybot-1-vovk.onrender.com
PORT = int(os.getenv('PORT', '10000'))
ADMIN_ID = os.getenv('ADMIN_ID')

if not BOT_TOKEN:
    raise ValueError('TELEGRAM_BOT_TOKEN not found in environment variables')

# In-memory storage
users_db = {}
pending_payments = {}
pending_game_targets = {}

# Config
PAYMENT_METHOD = os.getenv('PAYMENT_METHOD', 'TELECEL CASH/VODAFONE CASH')
PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER', '0503013078')
PAYMENT_NAME = os.getenv('PAYMENT_NAME', 'Emmanuel Kwaku Kyere')
BOT_OWNER = os.getenv('BOT_OWNER', 'PRO AI TIPSTER')
PAYSTACK_LINK = os.getenv('PAYSTACK_LINK', 'https://paystack.shop/pay/gar9gazycx')

# Only one plan
SUBSCRIPTION_TIERS = {
    'tier3': {'price': 100, 'odds': 10, 'name': '10 Odds'}
}


async def _set_bot_commands(app: Application) -> None:
    commands = [
        BotCommand("start", "Open main menu"),
        BotCommand("pay", "Pay with Paystack"),
        BotCommand("status", "View your status"),
        BotCommand("tips", "Get today's tips"),
        BotCommand("help", "Help and info"),
    ]
    await app.bot.set_my_commands(commands)


# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    if user_id not in users_db:
        users_db[user_id] = {
            'username': user.username or user.first_name,
            'is_premium': False,
            'tips_received': 0,
            'joined_date': datetime.now().isoformat(),
            'pending_payment': None,
        }
        if str(user_id) == str(ADMIN_ID):
            await update.message.reply_html(
                "<b>👋 Welcome Admin!</b>\n\n"
                "You are now set up to receive payment screenshots and notifications.\n\n"
                "Commands:\n/pending, /approve [user_id], /test"
            )

    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"<b>Welcome to {BOT_OWNER}! 🎲</b>\n\n"
        f"Hi {user.mention_html()}!\n\n"
        f"<b>Available Plan:</b>\n💰 100 GHS - 10 Odds\n\n"
        f"<b>Features:</b>\n"
        f"✅ Daily betting odds\n✅ Expert analysis\n✅ Multiple sports covered\n✅ High accuracy predictions\n\n"
        f"Subscribe now to unlock premium tips!",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        f"<b>{BOT_OWNER} - Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start, /pay, /status, /tips, /help\n\n"
        "<b>Available Plan:</b>\n💰 100 GHS - 10 Odds\n\n"
        "<b>How to subscribe:</b>\n"
        "1. Open /start\n"
        "2. Tap 'Pay with Paystack' or pay via MoMo\n"
        f"3. MOMO Number: {PAYMENT_NUMBER}\n"
        "4. Send screenshot if you didn't use Paystack\n"
        "5. Wait for approval and receive your odds\n\n"
        "<b>Contact Support:</b> Reply with 'support'"
    )
    await update.message.reply_html(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users_db:
        await update.message.reply_text("Please use /start first to initialize your account.")
        return

    user = users_db[user_id]
    status = "✅ Premium" if user['is_premium'] else "❌ Free"
    message = (
        f"<b>Your Account Status</b>\n\n"
        f"Status: {status}\n"
        f"Tips Received: {user['tips_received']}\n"
        f"Joined: {user['joined_date'][:10]}\n"
    )

    if not user['is_premium']:
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
            [InlineKeyboardButton("🔔 Subscribe Now", callback_data='subscribe_tier3')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(message, reply_markup=reply_markup)
    else:
        await update.message.reply_html(message)


async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users_db:
        await update.message.reply_text("Please use /start first to initialize your account.")
        return

    user = users_db[user_id]
    if not user['is_premium']:
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
            [InlineKeyboardButton("🔔 Subscribe", callback_data='subscribe_tier3')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            "<b>Premium Content</b>\n\n"
            "Subscribe to get access to today's betting tips!\n\n"
            "Our premium members receive:\n"
            "🎯 Daily expert predictions\n"
            "📊 Detailed analysis\n"
            "💰 High-value betting opportunities",
            reply_markup=reply_markup,
        )
        return

    await update.message.reply_html(
        "<b>🎯 Premium Tips Delivery</b>\n\n"
        "Your odds will be sent to you as an image by the admin shortly.\n\n"
        f"If you haven't received it, reply with 'support' to contact {BOT_OWNER}."
    )


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        "<b>Secure Payment</b>\n\n"
        "Tap the button below to pay with Paystack.\n\n"
        "If you pay via mobile money directly, please send a screenshot for verification.",
        reply_markup=reply_markup,
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"<b>Welcome to {BOT_OWNER}! 🎲</b>\n\n"
        f"<b>Available Plan:</b>\n"
        f"💰 100 GHS - 10 Odds\n\n",
        reply_markup=reply_markup,
    )


async def refreshcommands_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    try:
        await _set_bot_commands(app)
        await update.message.reply_text("✅ Commands refreshed. Open the side menu to see them.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to refresh commands: {e}")


# Admin utilities
async def clear_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("This command is for admin only.")
        return
    pending_payments.clear()
    await update.message.reply_text("✅ Cleared all pending payments.")


async def reset_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("This command is for admin only.")
        return
    users_db.clear()
    pending_payments.clear()
    pending_game_targets.clear()
    await update.message.reply_text("✅ Reset in-memory data: users, pending payments, and compose targets.")


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not pending_payments:
        await update.message.reply_html(
            "<b>✅ No Pending Payments</b>\n\nAll payments have been processed!"
        )
        return
    message = "<b>📋 Pending Payments</b>\n\n"
    for idx, (uid, info) in enumerate(pending_payments.items(), 1):
        tier_info = SUBSCRIPTION_TIERS.get(info.get('tier', 'tier3'), SUBSCRIPTION_TIERS['tier3'])
        message += (
            f"<b>Payment #{idx}</b>\n"
            f"User: {info.get('username','')}\n"
            f"User ID: {uid}\n"
            f"Plan: {tier_info.get('name','10 Odds')}\n"
            f"Amount: {tier_info.get('price',100)} GHS\n"
            f"Odds: {tier_info.get('odds',10)}\n"
            f"Status: ⏳ Awaiting Approval\n"
            f"Screenshot: Received ✅\n"
            f"Time: {info.get('timestamp','')}\n\n"
        )
    await update.message.reply_html(message)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_html(
        f"<b>Your Telegram User ID:</b>\n\n<code>{user_id}</code>\n\n"
        f"Add to .env as ADMIN_ID and restart bot."
    )


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) == str(ADMIN_ID):
        await update.message.reply_html(
            f"<b>✅ Admin Mode Active!</b>\n\nYour ID: {ADMIN_ID}\nReady to receive payments!"
        )
    else:
        await update.message.reply_text(
            f"✅ Bot is working!\n\nYour ID: {user_id}"
        )


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /approve [user_id]")
        return
    try:
        user_id_to_approve = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID")
        return
    if user_id_to_approve not in pending_payments:
        await update.message.reply_text(f"No pending payment found for user {user_id_to_approve}")
        return

    payment_info = pending_payments[user_id_to_approve]
    tier_key = payment_info.get('tier', 'tier3')
    if user_id_to_approve in users_db:
        users_db[user_id_to_approve]['is_premium'] = True
        users_db[user_id_to_approve]['subscription_tier'] = tier_key
    del pending_payments[user_id_to_approve]

    await update.message.reply_html(
        f"<b>✅ Payment Approved!</b>\n\nUser: {payment_info['username']}\n"
        f"Plan: {SUBSCRIPTION_TIERS[tier_key]['name']}\nAmount: {SUBSCRIPTION_TIERS[tier_key]['price']} GHS\n\n"
        f"Use /send {user_id_to_approve} to deliver the predictions now."
    )


# Buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {
            'username': query.from_user.username or query.from_user.first_name,
            'is_premium': False,
            'tips_received': 0,
            'joined_date': datetime.now().isoformat(),
            'pending_payment': None,
        }

    if query.data.startswith('subscribe_tier'):
        tier = query.data.replace('subscribe_tier', '')
        tier_key = f'tier{tier}'
        if tier_key not in SUBSCRIPTION_TIERS:
            tier_key = 'tier3'
        tier_info = SUBSCRIPTION_TIERS[tier_key]
        users_db[user_id]['pending_payment'] = tier_key

        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
            [InlineKeyboardButton("📸 Send Payment Screenshot", callback_data=f'upload_screenshot_{tier_key}')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=(
                f"<b>Subscribe to {tier_info['name']}</b>\n\n"
                f"<b>Price: {tier_info['price']} GHS</b>\n"
                f"<b>You'll get: {tier_info['odds']} Odds</b>\n\n"
                f"<b>📱 Payment Details:</b>\n"
                f"Method: {PAYMENT_METHOD}\n"
                f"Number: {PAYMENT_NUMBER}\n"
                f"Name: {PAYMENT_NAME}\n\n"
                f"<b>Send {tier_info['price']} GHS to the above number</b>\n\n"
                f"After payment:\n"
                f"1️⃣ Take a screenshot of the payment\n"
                f"2️⃣ Click 'Send Payment Screenshot'\n"
                f"3️⃣ Upload the screenshot\n"
                f"4️⃣ Wait for approval from {BOT_OWNER}\n\n"
                f"<i>Your odds will be sent after approval</i>"
            ),
            reply_markup=reply_markup,
            parse_mode='HTML',
        )
        return

    if query.data.startswith('upload_screenshot_'):
        tier_key = query.data.replace('upload_screenshot_', '')
        context.user_data['waiting_for_screenshot'] = True
        context.user_data['pending_tier'] = tier_key
        await query.edit_message_text(
            text=(
                "<b>📸 Send Payment Screenshot</b>\n\n"
                "Please send a screenshot of your payment confirmation.\n"
                "Make sure it clearly shows your amount, recipient number, reference, and name."
            ),
            parse_mode='HTML',
        )
        return

    if query.data == 'get_tips':
        if not users_db[user_id]['is_premium']:
            keyboard = [
                [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
                [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text="<b>Premium Content</b>\n\nSubscribe to get access to today's betting tips!",
                reply_markup=reply_markup,
                parse_mode='HTML',
            )
        else:
            await query.edit_message_text(
                text=(
                    "<b>🎯 Premium Tips Delivery</b>\n\nYour odds will be sent to you as an image by the admin shortly."
                ),
                parse_mode='HTML',
            )
        return

    if query.data == 'how_it_works':
        await query.edit_message_text(
            text=(
                f"<b>How {BOT_OWNER} Works</b>\n\n"
                f"1️⃣ <b>Choose Plan</b> - 100 GHS for 10 Odds\n"
                f"2️⃣ <b>Pay</b> - Use the Paystack button or pay via {PAYMENT_METHOD} to {PAYMENT_NUMBER}\n"
                f"3️⃣ <b>Send Screenshot</b> - If you didn't use Paystack\n"
                f"4️⃣ <b>Get Approved</b> - Wait for {BOT_OWNER} to verify\n"
                f"5️⃣ <b>Receive Tips</b> - Get your daily betting odds\n\n"
                f"<b>Available Plan:</b>\n💰 100 GHS - 10 Odds\n\n"
                f"<b>Payment To:</b> {PAYMENT_NAME}\n<b>{PAYMENT_METHOD}:</b> {PAYMENT_NUMBER}"
            ),
            parse_mode='HTML',
        )
        return

    if query.data == 'cancel':
        users_db[user_id]['pending_payment'] = None
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url=PAYSTACK_LINK)],
            [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
            [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=(
                f"<b>Welcome to {BOT_OWNER}! 🎲</b>\n\nGet expert betting predictions and tips from our AI-powered analysis."
            ),
            reply_markup=reply_markup,
            parse_mode='HTML',
        )
        return


# Messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # Admin compose delivery
    if pending_game_targets.get(str(user_id)):
        target_id = pending_game_targets.get(str(user_id))
        try:
            if update.message.text and not update.message.photo and not update.message.document:
                await context.bot.send_message(chat_id=target_id, text=update.message.text)
            elif update.message.photo:
                await context.bot.send_photo(chat_id=target_id, photo=update.message.photo[-1].file_id, caption=update.message.caption)
            elif update.message.document:
                await context.bot.send_document(chat_id=target_id, document=update.message.document.file_id, caption=update.message.caption)
            else:
                await update.message.reply_text("Unsupported message type. Send text, photo, or document.")
                return
            await update.message.reply_text("✅ Game delivered to customer.")
            pending_game_targets.pop(str(user_id), None)
        except Exception as e:
            logger.error(f"Failed to deliver game to {target_id}: {e}")
            await update.message.reply_text("❌ Failed to deliver. Please try again.")
        return

    # Treat photos/documents as payment screenshots (non-admin)
    if (update.message.photo or update.message.document) and (not ADMIN_ID or str(user_id) != str(ADMIN_ID)):
        pending_tier = context.user_data.get('pending_tier') or users_db.get(user_id, {}).get('pending_payment') or 'tier3'
        tier_info = SUBSCRIPTION_TIERS.get(pending_tier, SUBSCRIPTION_TIERS['tier3'])

        if user_id not in users_db:
            users_db[user_id] = {
                'username': update.effective_user.username or update.effective_user.first_name,
                'is_premium': False,
                'tips_received': 0,
                'joined_date': datetime.now().isoformat(),
                'pending_payment': pending_tier,
            }

        entry = {
            'username': update.effective_user.username or update.effective_user.first_name,
            'tier': pending_tier,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending',
        }
        if update.message.photo:
            entry['photo_id'] = update.message.photo[-1].file_id
        else:
            entry['document_id'] = update.message.document.file_id
        pending_payments[user_id] = entry

        await update.message.reply_html(
            "<b>✅ Screenshot Received!</b>\n\n"
            f"Thank you for sending your payment proof.\n\n"
            f"Plan: {tier_info.get('name')}\n"
            f"Amount: {tier_info.get('price')} GHS\n"
            f"Odds: {tier_info.get('odds')}\n\n"
            f"Your screenshot has been sent to {BOT_OWNER} for verification.\nYou'll receive your odds once approved."
        )

        if ADMIN_ID:
            try:
                await context.bot.copy_message(
                    chat_id=int(ADMIN_ID),
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                )
                keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{user_id}')]]
                await context.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        "<b>📸 New Payment Screenshot</b>\n\n"
                        f"User: {update.effective_user.username or update.effective_user.first_name}\n"
                        f"User ID: {user_id}\n"
                        f"Plan: {tier_info.get('name')}\n"
                        f"Amount: {tier_info.get('price')} GHS\n"
                        f"Odds: {tier_info.get('odds')}\n\n"
                        "Tap below to send the game now."
                    ),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            except Exception as e:
                logger.error(f"Could not copy screenshot to admin: {e}")
        return

    # Regular help/support
    user_message = update.message.text.lower() if update.message.text else ""
    if 'support' in user_message:
        await update.message.reply_html(
            "📧 <b>Support Request Received</b>\n\n"
            f"Contact {BOT_OWNER} directly for support. Use /help for common questions."
        )
    else:
        await update.message.reply_html(
            f"<b>Welcome to {BOT_OWNER}! 🎲</b>\n\nUse /start to get started or /help for more information."
        )


async def cancel_send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if pending_game_targets.get(str(user_id)):
        pending_game_targets.pop(str(user_id), None)
        await update.message.reply_text("✅ Cancelled. Compose mode ended.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("This command is for admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /send <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user_id. Usage: /send <user_id>")
        return
    if target_id not in users_db:
        await update.message.reply_text("Warning: user not found in database. You can still send.")
    pending_game_targets[str(user_id)] = target_id
    await update.message.reply_text(
        "✉️ Compose mode: send the odds now (text/photo/document).\nUse /cancel_send to cancel."
    )


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("tips", tips_command))
    application.add_handler(CommandHandler("pay", pay_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("refreshcommands", refreshcommands_command))
    application.add_handler(CommandHandler("clear_pending", clear_pending_command))
    application.add_handler(CommandHandler("reset_data", reset_data_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("cancel_send", cancel_send_command))
    application.add_handler(CommandHandler("send", send_command))

    # Callback and message handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start
    logger.info("BetTips Pro Bot starting...")
    application.post_init = _set_bot_commands

    if WEBHOOK_URL:
        logger.info(f"Starting in WEBHOOK mode at {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("Starting in POLLING mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
