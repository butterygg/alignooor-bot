#!/usr/bin/env python
# pylint: disable=unused-argument
"""
Aligner Telegram Bot
"""
import datetime
import logging
import os

from pyairtable import Api
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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


async def greet_new_users(update: Update, context: CallbackContext):
    global last_greeting_time  # pylint: disable=global-statement
    now = datetime.datetime.now()
    if last_greeting_time is None or (now - last_greeting_time).total_seconds() > 3600:
        bot_username = context.bot.username
        if update.message.new_chat_members:
            message = f"""
🤗 Welcome to our newcomers\\!

To register as an Alignooor and be eligible for rewards, \
[send me a DM](https://t.me/{bot_username}?start) or hit Start\\.

Please read the pinned message to know more\\.
            """
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Start", callback_data="/start")]]
                ),
            )
            last_greeting_time = now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot: Bot = context.bot

    if update.effective_chat.type != "private" and update.message:
        await update.message.reply_markdown_v2(
            f"👋 Hi {context.bot.username}\\! "
            f"Let's continue our conversation [in DMs]"
            f"(https://t.me/{context.bot.username})\\."
        )

    await bot.send_message(
        chat_id=user.id,
        text=f"Hi {user.name}, ready to participate as an Alignooor? Just hit Join.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join", callback_data="/join")]]
        ),
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            chat_id=user.id, text="An unknown error occured, we're on it."
        )
    else:
        if existing:
            await context.bot.send_message(
                chat_id=user.id, text="✅ You're already in!"
            )
        else:
            await context.bot.send_message(
                chat_id=user.id, text="🎉 You're now registered as an Alignooor!"
            )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "/start":
        await start(update, context)
    if query.data == "/join":
        await join(update, context)


def main() -> None:
    # Create the Application and pass it your bot's token.
    tg_app = Application.builder().token(TG_BOT_TOK).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("join", join))

    tg_app.add_handler(CallbackQueryHandler(button_callback))

    tg_app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_users)
    )

    # Run the bot until the user presses Ctrl-C
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
