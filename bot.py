import os
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

# Simple in-memory user database
users_db = {}
pending_payments = {}  # Store pending payments with screenshots
pending_game_targets = {}  # Map admin_id -> customer_id for manual game sending
PAYMENT_METHOD = "TELECEL CASH/VODAFONE CASH"
PAYMENT_NUMBER = "0503013078"
PAYMENT_NAME = "Emmanuel Kwaku Kyere"
BOT_OWNER = "PRO AI TIPSTER"
ADMIN_ID = os.getenv('ADMIN_ID')  # Set this in .env file with your Telegram user ID

# Subscription tiers (only one available)
SUBSCRIPTION_TIERS = {
    'tier3': {'price': 100, 'odds': 10, 'name': '10 Odds'}
}


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    if user_id not in users_db:
        users_db[user_id] = {
            'username': user.username or user.first_name,
            'is_premium': False,
            'tips_received': 0,
            'joined_date': datetime.now().isoformat(),
            'pending_payment': None
        }
        
        # If this is the admin, send them a welcome message
        if str(user_id) == str(ADMIN_ID):
            await update.message.reply_html(
                f"<b>👋 Welcome Admin!</b>\n\n"
                f"You are now set up to receive payment screenshots and notifications.\n\n"
                f"Commands:\n"
                f"/pending - View pending payments\n"
                f"/approve [user_id] - Approve a payment\n"
                f"/test - Test if notifications work"
            )
    # Build the main menu inline keyboard
    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"<b>Welcome to PRO AI TIPSTER! 🎲</b>\n\n"
        f"Hi {user.mention_html()}!\n\n"
        f"Get expert betting predictions and tips from our AI-powered analysis.\n\n"
        f"<b>Available Plan:</b>\n"
        f"💰 100 GHS - 10 Odds\n\n"
        f"<b>Features:</b>\n"
        f"✅ Daily betting odds\n"
        f"✅ Expert analysis\n"
        f"✅ Multiple sports covered\n"
        f"✅ High accuracy predictions\n\n"
        f"Subscribe now to unlock premium tips!",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        f"<b>{BOT_OWNER} - Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - This help message\n"
        "/status - Check your subscription status\n"
        "/tips - Get today's betting tips\n\n"
        "<b>Available Plan:</b>\n"
        "💰 100 GHS - 10 Odds\n\n"
        "<b>How to subscribe:</b>\n"
        "1. Open /start\n"
        "2. Tap 'Pay with Paystack' or pay via MTN MOMO\n"
        f"3. MOMO Number: {PAYMENT_NUMBER}\n"
        "4. Send screenshot if you didn't use Paystack\n"
        "5. Wait for approval and receive your odds\n\n"
        "<b>Contact Support:</b>\n"
        f"Message {BOT_OWNER} or reply with 'support'"
    )
    await update.message.reply_html(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check user subscription status."""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Please use /start first to initialize your account.")
        return
    
    # If a customer sends a document (PDF/image as file), also treat as payment screenshot
    if update.message.document and (not ADMIN_ID or str(user_id) != str(ADMIN_ID)):
        pending_tier = context.user_data.get('pending_tier')
        if user_id in users_db and not pending_tier:
            pending_tier = users_db[user_id].get('pending_payment')
        tier_info = SUBSCRIPTION_TIERS.get(pending_tier, {}) if pending_tier else {}

        if user_id not in users_db:
            users_db[user_id] = {
                'username': update.effective_user.username or update.effective_user.first_name,
                'is_premium': False,
                'tips_received': 0,
                'joined_date': datetime.now().isoformat(),
                'pending_payment': pending_tier or None
            }

        pending_payments[user_id] = {
            'username': update.effective_user.username or update.effective_user.first_name,
            'tier': pending_tier or 'unknown',
            'document_id': update.message.document.file_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending'
        }

        await update.message.reply_html(
            "<b>✅ Screenshot Received!</b>\n\n"
            "Thank you for sending your payment proof.\n\n"
            + (f"Plan: {tier_info.get('name', 'Unknown')}\n" if tier_info else "")
            + (f"Amount: {tier_info.get('price', 0)} GHS\n" if tier_info else "")
            + (f"Odds: {tier_info.get('odds', 0)}\n\n" if tier_info else "\n")
            + f"Your screenshot has been sent to {BOT_OWNER} for verification.\n"
              "You'll receive your odds once approved."
        )

        if ADMIN_ID:
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.copy_message(
                    chat_id=int(ADMIN_ID),
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{user_id}')]]
                await bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        "<b>📸 New Payment Screenshot</b>\n\n"
                        f"User: {update.effective_user.username or update.effective_user.first_name}\n"
                        f"User ID: {user_id}\n"
                        + (f"Plan: {tier_info.get('name', 'Unknown')}\n" if tier_info else "")
                        + (f"Amount: {tier_info.get('price', 0)} GHS\n" if tier_info else "")
                        + (f"Odds: {tier_info.get('odds', 0)}\n\n" if tier_info else "\n")
                        + "Tap below to send the game now."
                    ),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Could not copy document to admin: {e}")
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
            [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
            [InlineKeyboardButton("🔔 Subscribe Now", callback_data='subscribe_tier3')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(message, reply_markup=reply_markup)
    else:
        await update.message.reply_html(message)


async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send betting tips to user."""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Please use /start first to initialize your account.")
        return
    
    user = users_db[user_id]
    
    if not user['is_premium']:
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
            [InlineKeyboardButton("🔔 Subscribe", callback_data='subscribe_tier3')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            "<b>Premium Content</b>\n\n"
            "Subscribe to get access to today's betting tips!\n\n"
            "Our premium members receive:\n"
            "🎯 Daily expert predictions\n"
            "📊 Detailed analysis\n"
            "💰 High-value betting opportunities",
            reply_markup=reply_markup
        )
        return
    
    # Premium users receive odds as an image from the admin
    await update.message.reply_html(
        "<b>🎯 Premium Tips Delivery</b>\n\n"
        "Your odds will be sent to you as an image by the admin shortly.\n\n"
        f"If you haven't received it, reply with 'support' to contact {BOT_OWNER}."
    )


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Paystack payment link and quick actions."""
    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        "<b>Secure Payment</b>\n\n"
        "Tap the button below to pay with Paystack.\n\n"
        "If you pay via mobile money directly, please send a screenshot for verification.",
        reply_markup=reply_markup
    )


async def _set_bot_commands(app: Application) -> None:
    """Register bot commands so they appear in the side menu."""
    commands = [
        BotCommand("start", "Open main menu"),
        BotCommand("pay", "Pay with Paystack"),
        BotCommand("status", "View your status"),
        BotCommand("tips", "Get today's tips"),
        BotCommand("help", "Help and info"),
    ]
    await app.bot.set_my_commands(commands)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu inline keyboard explicitly."""
    keyboard = [
        [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
        [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"<b>Welcome to PRO AI TIPSTER! 🎲</b>\n\n"
        f"<b>Available Plan:</b>\n"
        f"💰 100 GHS - 10 Odds\n\n",
        reply_markup=reply_markup
    )


async def refreshcommands_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force refresh side menu commands for this bot."""
    app = context.application
    try:
        await _set_bot_commands(app)
        await update.message.reply_text("✅ Commands refreshed. Open the side menu to see them.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to refresh commands: {e}")


async def clear_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: Clear pending payment records."""
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("This command is for admin only.")
        return
    pending_payments.clear()
    await update.message.reply_text("✅ Cleared all pending payments.")


async def reset_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: Reset all in-memory data structures."""
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("This command is for admin only.")
        return
    users_db.clear()
    pending_payments.clear()
    pending_game_targets.clear()
    await update.message.reply_text("✅ Reset in-memory data: users, pending payments, and compose targets.")


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pending payments (admin only)."""
    user_id = update.effective_user.id
    
    # Check if user is admin (for now, anyone can use this - you can restrict it)
    if not pending_payments:
        await update.message.reply_html(
            "<b>✅ No Pending Payments</b>\n\n"
            "All payments have been processed!"
        )
        return
    
    message = "<b>📋 Pending Payments</b>\n\n"
    
    for idx, (user_id_pending, payment_info) in enumerate(pending_payments.items(), 1):
        tier_info = SUBSCRIPTION_TIERS.get(payment_info['tier'], {})
        message += (
            f"<b>Payment #{idx}</b>\n"
            f"User: {payment_info['username']}\n"
            f"User ID: {user_id_pending}\n"
            f"Plan: {tier_info.get('name', 'Unknown')}\n"
            f"Amount: {tier_info.get('price', 0)} GHS\n"
            f"Odds: {tier_info.get('odds', 0)}\n"
            f"Status: ⏳ Awaiting Approval\n"
            f"Screenshot: Received ✅\n"
            f"Time: {payment_info['timestamp']}\n\n"
        )
    
    message += (
        f"<b>How to proceed:</b>\n"
        f"Use the 'Send Game' button in the screenshot summary to deliver predictions.\n"
        f"Or run: /send [user_id] (e.g. /send {list(pending_payments.keys())[0] if pending_payments else '123456789'})\n\n"
        f"<i>Screenshots are stored in the bot. Check Telegram directly for payment proof.</i>"
    )
    
    await update.message.reply_html(message)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show your Telegram user ID."""
    user_id = update.effective_user.id
    await update.message.reply_html(
        f"<b>Your Telegram User ID:</b>\n\n"
        f"<code>{user_id}</code>\n\n"
        f"Add this to your .env file:\n"
        f"<code>ADMIN_ID={user_id}</code>\n\n"
        f"Then restart the bot to receive payment screenshots."
    )
    
    # Log for debugging
    logger.info(f"ADMIN_ID from env: {ADMIN_ID}")


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command to verify bot is working."""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if str(user_id) == str(ADMIN_ID):
        await update.message.reply_html(
            f"<b>✅ Admin Mode Active!</b>\n\n"
            f"Your ID is correctly configured: {ADMIN_ID}\n\n"
            f"You will now receive:\n"
            f"📸 Payment screenshots\n"
            f"📋 Pending payment notifications\n"
            f"✅ Approval confirmations\n\n"
            f"Ready to receive payments!"
        )
    else:
        await update.message.reply_text(
            f"✅ Bot is working!\n\n"
            f"Your ID: {user_id}\n\n"
            f"This is a customer account. Admin features not available."
        )


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a pending payment."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /approve [user_id]\n"
            "Example: /approve 123456789"
        )
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
    tier_key = payment_info['tier']
    tier_info = SUBSCRIPTION_TIERS.get(tier_key, {})
    
    # Approve the payment
    if user_id_to_approve in users_db:
        users_db[user_id_to_approve]['is_premium'] = True
        users_db[user_id_to_approve]['subscription_tier'] = tier_key
    
    # Remove from pending
    del pending_payments[user_id_to_approve]
    
    # Notify admin of approval with Send Game button (manual send)
    keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{user_id_to_approve}')]]
    await update.message.reply_html(
        f"<b>✅ Payment Approved!</b>\n\n"
        f"User: {payment_info['username']}\n"
        f"Plan: {tier_info.get('name', 'Unknown')}\n"
        f"Amount: {tier_info.get('price', 0)} GHS\n\n"
        f"Tap 'Send Game' to deliver the predictions now.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Notify the customer about delivery timeline
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=user_id_to_approve,
            text=(
                "<b>✅ Payment Approved!</b>\n\n"
                "Thank you. Your predictions will be sent to you by our team within <b>5 minutes</b>.\n\n"
                f"If you don't receive them, reply with 'support' to contact {BOT_OWNER}."
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Could not notify customer {user_id_to_approve} after approval: {e}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in users_db:
        users_db[user_id] = {
            'username': query.from_user.username or query.from_user.first_name,
            'is_premium': False,
            'tips_received': 0,
            'joined_date': datetime.now().isoformat(),
            'pending_payment': None
        }
    
    # Handle admin approve
    if query.data.startswith('admin_approve_'):
        customer_id = int(query.data.replace('admin_approve_', ''))
        
        if customer_id in pending_payments:
            payment_info = pending_payments[customer_id]
            tier_key = payment_info['tier']
            tier_info = SUBSCRIPTION_TIERS.get(tier_key, {})
        
            # Approve the payment
            if customer_id in users_db:
                users_db[customer_id]['is_premium'] = True
                users_db[customer_id]['subscription_tier'] = tier_key
        
            # Remove from pending
            del pending_payments[customer_id]
        
            # Update admin message with Send Game button (manual send)
            keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{customer_id}')]]
            await query.edit_message_text(
                text=(
                    f"<b>✅ Payment Approved!</b>\n\n"
                    f"User: {payment_info['username']}\n"
                    f"Plan: {tier_info.get('name', 'Unknown')}\n"
                    f"Amount: {tier_info.get('price', 0)} GHS\n\n"
                    f"Tap 'Send Game' to deliver the predictions now."
                ),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # Notify customer about delivery timeline
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    chat_id=customer_id,
                    text=(
                        "<b>✅ Payment Approved!</b>\n\n"
                        "Thank you. Your predictions will be sent to you by our team within <b>5 minutes</b>.\n\n"
                        f"If you don't receive them, reply with 'support' to contact {BOT_OWNER}."
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify customer {customer_id}: {e}")
    
    # Handle admin reject
    elif query.data.startswith('admin_reject_'):
        customer_id = int(query.data.replace('admin_reject_', ''))
        
        if customer_id in pending_payments:
            payment_info = pending_payments[customer_id]
            
            # Remove from pending
            del pending_payments[customer_id]
            
            # Update admin message
            await query.edit_message_text(
                text=f"<b>❌ Payment Rejected</b>\n\n"
                     f"User: {payment_info['username']}\n"
                     f"Customer has been notified.",
                parse_mode='HTML'
            )
            
            # Notify customer
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    chat_id=customer_id,
                    text=f"<b>❌ Payment Rejected</b>\n\n"
                         f"Your payment could not be verified.\n\n"
                         f"Please contact {BOT_OWNER} for assistance.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify customer {customer_id}: {e}")
    
    # Admin chooses to send the game manually (enter compose mode)
    elif query.data.startswith('admin_send_'):
        customer_id = int(query.data.replace('admin_send_', ''))
        # Scope compose target to the current admin user
        pending_game_targets[str(user_id)] = customer_id
        # Immediate toast confirmation to stop spinner
        try:
            await query.answer("Compose mode started. Send the game now.", show_alert=False)
        except Exception as e:
            logger.error(f"Failed to answer callback for admin_send: {e}")
        # Confirm compose mode in the edited message
        await query.edit_message_text(
            text=(
                f"<b>✉️ Compose Game</b>\n\n"
                f"Now send the game as a message.\n"
                f"- Text, photo, or document are supported.\n"
                f"- It will be delivered to the customer immediately.\n\n"
                f"Target user ID: {customer_id}\n"
                f"To cancel: /cancel_send"
            ),
            parse_mode='HTML'
        )
        # Also send a separate confirmation message for visibility
        try:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=(
                    f"Compose mode started. Target user ID: {customer_id}.\n"
                    f"Send the odds now (text/photo/document). Use /cancel_send to cancel."
                )
            )
        except Exception as e:
            logger.error(f"Failed to send compose confirmation: {e}")
    
    elif query.data == 'get_tips':
        if not users_db[user_id]['is_premium']:
            keyboard = [
                [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
                [InlineKeyboardButton("💳 100 GHS - 10 Odds", callback_data='subscribe_tier3')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text="<b>Premium Content</b>\n\nSubscribe to get access to today's betting tips!",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                text=(
                    "<b>🎯 Premium Tips Delivery</b>\n\n"
                    "Your odds will be sent to you as an image by the admin shortly.\n\n"
                    f"If you haven't received it, reply with 'support' to contact {BOT_OWNER}."
                ),
                parse_mode='HTML'
            )
    
    elif query.data.startswith('subscribe_tier'):
        tier = query.data.replace('subscribe_tier', '')
        tier_key = f'tier{tier}'
        
        if tier_key not in SUBSCRIPTION_TIERS:
            return
        
        tier_info = SUBSCRIPTION_TIERS[tier_key]
        users_db[user_id]['pending_payment'] = tier_key
        
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
            [InlineKeyboardButton("📸 Send Payment Screenshot", callback_data=f'upload_screenshot_{tier_key}')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"<b>Subscribe to {tier_info['name']}</b>\n\n"
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
                 f"<i>Your odds will be sent after approval</i>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith('upload_screenshot_'):
        tier_key = query.data.replace('upload_screenshot_', '')
        context.user_data['waiting_for_screenshot'] = True
        context.user_data['pending_tier'] = tier_key
        
        await query.edit_message_text(
            text="<b>📸 Send Payment Screenshot</b>\n\n"
                 "Please send a screenshot of your payment confirmation.\n"
                 "Make sure it clearly shows:\n"
                 "✅ Payment amount\n"
                 "✅ Recipient number (0503013078)\n"
                 "✅ Transaction reference\n"
                 "✅ Your name",
            parse_mode='HTML'
        )
    
    elif query.data == 'how_it_works':
        await query.edit_message_text(
            text=(
                f"<b>How {BOT_OWNER} Works</b>\n\n"
                f"1️⃣ <b>Choose Plan</b> - 100 GHS for 10 Odds\n"
                f"2️⃣ <b>Pay</b> - Use the Paystack button or pay via {PAYMENT_METHOD} to {PAYMENT_NUMBER}\n"
                f"3️⃣ <b>Send Screenshot</b> - Upload payment proof if you didn't use Paystack\n"
                f"4️⃣ <b>Get Approved</b> - Wait for {BOT_OWNER} to verify\n"
                f"5️⃣ <b>Receive Tips</b> - Get your daily betting odds\n\n"
                f"<b>Available Plan:</b>\n"
                f"💰 100 GHS - 10 Odds\n\n"
                f"<b>Payment To:</b> {PAYMENT_NAME}\n"
                f"<b>{PAYMENT_METHOD}:</b> {PAYMENT_NUMBER}\n\n"
                f"<b>Our Accuracy:</b> 78% average prediction accuracy\n"
                f"<b>Sports Covered:</b> Football, Basketball, Tennis, Cricket, and more"
            ),
            parse_mode='HTML'
        )
    
    elif query.data == 'cancel':
        users_db[user_id]['pending_payment'] = None
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Paystack", url='https://paystack.shop/pay/gar9gazycx')],
            [InlineKeyboardButton("💳 100 GHS - 15 Odds", callback_data='subscribe_tier3')],
            [InlineKeyboardButton("ℹ️ How It Works", callback_data='how_it_works')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"<b>Welcome to PRO AI TIPSTER! 🎲</b>\n\n"
                 "Get expert betting predictions and tips from our AI-powered analysis.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular messages and screenshots."""
    user_id = update.effective_user.id
    # If an admin is composing a game to send (scoped to this user)
    if pending_game_targets.get(str(user_id)):
        target_id = pending_game_targets.get(str(user_id))
        try:
            from telegram import Bot
            bot = Bot(token=BOT_TOKEN)
            if update.message.text and not update.message.photo and not update.message.document:
                await bot.send_message(chat_id=target_id, text=update.message.text)
            elif update.message.photo:
                # Send highest resolution photo
                await bot.send_photo(chat_id=target_id, photo=update.message.photo[-1].file_id, caption=update.message.caption)
            elif update.message.document:
                await bot.send_document(chat_id=target_id, document=update.message.document.file_id, caption=update.message.caption)
            else:
                await update.message.reply_text("Unsupported message type. Send text, photo, or document.")
                return
            await update.message.reply_text("✅ Game delivered to customer.")
            # Clear compose mode
            pending_game_targets.pop(str(user_id), None)
        except Exception as e:
            logger.error(f"Failed to deliver game to {target_id}: {e}")
            await update.message.reply_text("❌ Failed to deliver. Please try again.")
        return
    
    # If a customer sends a photo at any time, treat it as a payment screenshot
    if update.message.photo and (not ADMIN_ID or str(user_id) != str(ADMIN_ID)):
        # Determine tier context if available
        pending_tier = context.user_data.get('pending_tier')
        if user_id in users_db and not pending_tier:
            pending_tier = users_db[user_id].get('pending_payment')
        tier_info = SUBSCRIPTION_TIERS.get(pending_tier, {}) if pending_tier else {}

        # Ensure user record exists
        if user_id not in users_db:
            users_db[user_id] = {
                'username': update.effective_user.username or update.effective_user.first_name,
                'is_premium': False,
                'tips_received': 0,
                'joined_date': datetime.now().isoformat(),
                'pending_payment': pending_tier or None
            }

        # Store in pending payments
        pending_payments[user_id] = {
            'username': update.effective_user.username or update.effective_user.first_name,
            'tier': pending_tier or 'unknown',
            'photo_id': update.message.photo[-1].file_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending'
        }

        # Acknowledge to user
        await update.message.reply_html(
            "<b>✅ Screenshot Received!</b>\n\n"
            "Thank you for sending your payment proof.\n\n"
            + (f"Plan: {tier_info.get('name', 'Unknown')}\n" if tier_info else "")
            + (f"Amount: {tier_info.get('price', 0)} GHS\n" if tier_info else "")
            + (f"Odds: {tier_info.get('odds', 0)}\n\n" if tier_info else "\n")
            + f"Your screenshot has been sent to {BOT_OWNER} for verification.\n"
              "You'll receive your odds once approved."
        )

        # Forward/copy to admin
        if ADMIN_ID:
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.copy_message(
                    chat_id=int(ADMIN_ID),
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{user_id}')]]
                await bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        "<b>📸 New Payment Screenshot</b>\n\n"
                        f"User: {update.effective_user.username or update.effective_user.first_name}\n"
                        f"User ID: {user_id}\n"
                        + (f"Plan: {tier_info.get('name', 'Unknown')}\n" if tier_info else "")
                        + (f"Amount: {tier_info.get('price', 0)} GHS\n" if tier_info else "")
                        + (f"Odds: {tier_info.get('odds', 0)}\n\n" if tier_info else "\n")
                        + "Tap below to send the game now."
                    ),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Could not copy screenshot to admin: {e}")
        return
    
    # Check if user is waiting for screenshot
    if context.user_data.get('waiting_for_screenshot'):
        if update.message.photo or update.message.document:
            # User sent a photo
            pending_tier = context.user_data.get('pending_tier')
            tier_info = SUBSCRIPTION_TIERS.get(pending_tier, {})
            
            # Store screenshot info
            if user_id not in users_db:
                users_db[user_id] = {
                    'username': update.effective_user.username or update.effective_user.first_name,
                    'is_premium': False,
                    'tips_received': 0,
                    'joined_date': datetime.now().isoformat(),
                    'pending_payment': None
                }
            
            # Store in pending payments
            if update.message.photo:
                media_id = update.message.photo[-1].file_id
                pending_payments[user_id] = {
                    'username': update.effective_user.username or update.effective_user.first_name,
                    'tier': pending_tier,
                    'photo_id': media_id,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'pending'
                }
            else:
                media_id = update.message.document.file_id
                pending_payments[user_id] = {
                    'username': update.effective_user.username or update.effective_user.first_name,
                    'tier': pending_tier,
                    'document_id': media_id,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'pending'
                }
            
            users_db[user_id]['pending_payment'] = pending_tier
            users_db[user_id]['screenshot_received'] = True
            
            # Notify user
            await update.message.reply_html(
                f"<b>✅ Screenshot Received!</b>\n\n"
                f"Thank you for sending your payment proof.\n\n"
                f"<b>Details:</b>\n"
                f"Plan: {tier_info.get('name', 'Unknown')}\n"
                f"Amount: {tier_info.get('price', 0)} GHS\n"
                f"Odds: {tier_info.get('odds', 0)}\n\n"
                f"Your screenshot has been sent to {BOT_OWNER} for verification.\n"
                f"You'll receive your odds once approved.\n\n"
                f"<i>Please wait for approval...</i>"
            )
            
            # Forward screenshot to admin
            if ADMIN_ID:
                try:
                    from telegram import Bot
                    bot = Bot(token=BOT_TOKEN)
                    # Use copy_message to reliably copy media/captions without download
                    await bot.copy_message(
                        chat_id=int(ADMIN_ID),
                        from_chat_id=update.effective_chat.id,
                        message_id=update.message.message_id
                    )
                    # Send summary message with 'Send Game' button
                    keyboard = [[InlineKeyboardButton("✉️ Send Game", callback_data=f'admin_send_{user_id}')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text=f"<b>📸 New Payment Screenshot</b>\n\n"
                             f"User: {update.effective_user.username or update.effective_user.first_name}\n"
                             f"User ID: {user_id}\n"
                             f"Plan: {tier_info.get('name', 'Unknown')}\n"
                             f"Amount: {tier_info.get('price', 0)} GHS\n"
                             f"Odds: {tier_info.get('odds', 0)}\n\n"
                             f"Click below to approve or reject:",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Could not forward screenshot to admin: {e}")
            
            # Clear the waiting state
            context.user_data['waiting_for_screenshot'] = False
            
        else:
            await update.message.reply_text(
                "❌ Please send a screenshot image.\n\n"
                "Make sure it clearly shows:\n"
                "✅ Payment amount\n"
                "✅ Recipient number (0503013078)\n"
                "✅ Transaction reference\n"
                "✅ Your name"
            )
    else:
        # Regular message handling
        user_message = update.message.text.lower() if update.message.text else ""
        
        if 'support' in user_message:
            await update.message.reply_html(
                f"📧 <b>Support Request Received</b>\n\n"
                f"Thank you for contacting us.\n\n"
                f"<b>Contact {BOT_OWNER} directly for support</b>\n\n"
                f"In the meantime, use /help for common questions."
            )
        else:
            await update.message.reply_html(
                f"<b>Welcome to PRO AI TIPSTER! 🎲</b>\n\n"
                f"Use /start to get started or /help for more information."
            )

async def cancel_send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin cancels compose mode."""
    user_id = update.effective_user.id
    if pending_game_targets.get(str(user_id)):
        pending_game_targets.pop(str(user_id), None)
        await update.message.reply_text("✅ Cancelled. Compose mode ended.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin chooses a target user_id to send odds to (enter compose mode)."""
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
    # Optional: warn if user is unknown
    if target_id not in users_db:
        await update.message.reply_text("Warning: user not found in database. You can still send.")
    pending_game_targets[str(user_id)] = target_id
    await update.message.reply_text(
        "✉️ Compose mode: send the odds now (text/photo/document).\nUse /cancel_send to cancel."
    )


def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
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

    # Register callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Register message handler for photos
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    
    # Register message handler for documents (PDF/images as files)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))

    # Register message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    logger.info("BetTips Pro Bot started. Press Ctrl+C to stop.")
    # Ensure commands are registered in side menu
    application.post_init = _set_bot_commands
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
