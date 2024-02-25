#!/usr/bin/env python
# pylint: disable=unused-argument
# pylint: disable=logging-fstring-interpolation
"""
Aligner Telegram Bot
"""
import datetime
import logging
import os

import pytz
from pyairtable import Api
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

SAVE_KUDO = 0

TG_BOT_TOK = os.environ["TG_BOT_TOK"]
TG_BOT_UNAME = os.environ["TG_BOT_UNAME"]

AIRTABLE_TOK = os.environ["AIRTABLE_TOK"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_DB_PART_ID = os.environ["AIRTABLE_DB_PART_ID"]
AIRTABLE_DB_VOTE_ID = os.environ["AIRTABLE_DB_VOTE_ID"]

airtable_api = Api(AIRTABLE_TOK)

# Store the time of the last greeting
last_greeting_time = None  # pylint: disable=invalid-name

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


def get_today() -> str:
    mountain_time = pytz.timezone("America/Denver")
    now_in_mountain_time = datetime.datetime.now(mountain_time)
    return now_in_mountain_time.strftime("%Y-%m-%d")


async def greet_new_users(update: Update, context: CallbackContext):
    logger.info("greeting")
    global last_greeting_time  # pylint: disable=global-statement
    now = datetime.datetime.now()
    if last_greeting_time is None or (now - last_greeting_time).total_seconds() > 600:
        bot_username = context.bot.username
        if update.message.new_chat_members:
            message = f"""
🤗 Welcome to our newcomers\\!

To register as an Alignooor and be eligible for rewards, \
[send me a DM](https://t.me/{bot_username}?start)\\.

Please read the pinned message to learn more\\.
            """
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
            last_greeting_time = now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"start {update.effective_user.name}")
    user = update.effective_user
    bot: Bot = context.bot

    if update.effective_chat.type != "private" and update.message:
        await update.message.reply_markdown_v2(
            f"👋 Hi {user.name}\\! "
            f"Let's continue the conversation [in DMs]"
            f"(https://t.me/{context.bot.username})\\."
        )

    await bot.send_message(
        chat_id=user.id,
        text=f"Hi {user.name}, ready to join the game? Just hit Join.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join", callback_data="/join")]]
        ),
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"join {update.effective_user.name}")
    user = update.effective_user
    table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_PART_ID)
    fields = {
        "Telegram ID": user.id,
        "Telegram handle": user.username,
        "Telegram name": user.full_name,
    }

    try:
        existing = table.all(formula=f"{{Telegram ID}}={fields['Telegram ID']}")
        if not existing:
            table.create(fields)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)
        await context.bot.send_message(
            chat_id=user.id, text="🤦1️⃣ An unknown error occurred, we're on it."
        )
    else:
        if existing:
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "✅ You're already in!\n"
                    "Hit /kudo "
                    "when you're ready to start sending Kudos."
                ),
            )
        else:
            await context.bot.send_message(
                chat_id=user.id, text="🎉 You're now registered as an Alignooor!"
            )


async def start_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"kudo {update.effective_user.name}")
    user = update.effective_user
    part_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_PART_ID)
    kudo_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_VOTE_ID)

    try:
        existing_part = part_table.all(formula=f"{{Telegram ID}}={user.id}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)
        await context.bot.send_message(
            chat_id=user.id, text="🤦2️⃣ An unknown error occurred, we're on it."
        )
        return ConversationHandler.END

    if not existing_part:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "🤌 You need to join first. Join first by hitting Join "
                "or sending the /join command."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join", callback_data="/join")]]
            ),
        )
        return ConversationHandler.END

    part_id = existing_part[0]["id"]
    part_ID = existing_part[0]["fields"]["ID"]  # pylint: disable=invalid-name
    today = get_today()

    try:
        existing_kudos = kudo_table.all(formula=f"FIND({part_ID},{{Participant}})")
        existing_kudos_today = [
            k for k in existing_kudos if k["fields"]["Date"] == today
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)
        await context.bot.send_message(
            chat_id=user.id, text="🤦3️⃣ An unknown error occurred, we're on it."
        )
        return ConversationHandler.END

    if len(existing_kudos_today) >= 3:
        names = [k["fields"]["Kudoee Telegram handle"] for k in existing_kudos_today]
        # [TODO] Add a reset procedure but this needs to be tied to a date.
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"💗 You already gave your 3 kudos today, to {', '.join(names)}.\n"
                "🙏 Please get in touch with the team to reset your Kudos for today."
            ),
        )
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=user.id,
        text=(
            "Please write the Telegram handle of the person you'd like to send kudos to."
            "\nIf you don't want to send kudos anymore, just send /cancel."
        ),
    )
    context.user_data["part_id"] = part_id
    context.user_data["day"] = today
    return SAVE_KUDO


async def unsafe_save_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    user = update.effective_user
    kudo_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_VOTE_ID)

    part_id = context.user_data["part_id"]
    del context.user_data["part_id"]
    day = context.user_data["day"]
    del context.user_data["day"]

    fields = {
        "Participant": [part_id],
        "Kudoee Telegram handle": name,
        "Date": day,
    }

    try:
        kudo_table.create(fields)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)
        await context.bot.send_message(
            chat_id=user.id, text="🤦4️⃣ An unknown error occurred, we're on it."
        )
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=user.id,
        text=(f"💌 Thank you for sending your appreciation to {name}!"),
    )

    return ConversationHandler.END


async def cancel_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_message(chat_id=user.id, text="Kudo operation canceled.")
    return ConversationHandler.END


async def catch_all(update: Update, context: CallbackContext):
    user = update.effective_user
    table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_PART_ID)

    try:
        existing = table.all(formula=f"{{Telegram ID}}={user.id}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)
        await context.bot.send_message(
            chat_id=user.id, text="🤦5️⃣ An unknown error occurred, we're on it."
        )
        return

    complement_text = (
        "To send kudos, hit /kudo."
        if existing
        else "If you want to join as an Alignooor, hit /join."
    )

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=("🤷 Command not understood. " + complement_text),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join", callback_data="/join")]]
            ),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception(e)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"join {update.effective_user.name}")
    query = update.callback_query

    if query.data == "/start":
        await start(update, context)
    if query.data == "/join":
        await join(update, context)
    if query.data == "/kudo":
        await join(start_kudo, context)


def main() -> None:
    # Create the Application and pass it your bot's token.
    tg_app = Application.builder().token(TG_BOT_TOK).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("join", join))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("kudo", start_kudo)],
        states={
            SAVE_KUDO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, unsafe_save_kudo)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_kudo),
            MessageHandler(filters.COMMAND, lambda update, context: None),
        ],
    )
    tg_app.add_handler(conv_handler)

    tg_app.add_handler(CallbackQueryHandler(button_callback))

    tg_app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_users)
    )

    tg_app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, catch_all))

    # Run the bot until the user presses Ctrl-C
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
