#!/usr/bin/env python
# pylint: disable=unused-argument
# pylint: disable=logging-fstring-interpolation
# pylint: disable=broad-exception-caught
# pylint: disable=missing-class-docstring
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
TG_GROUP_ID = -int(os.environ["TG_GROUP_ID"])
TG_THREAD_ID = int(os.environ["TG_THREAD_ID"])

AIRTABLE_TOK = os.environ["AIRTABLE_TOK"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_DB_PART_ID = os.environ["AIRTABLE_DB_PART_ID"]
AIRTABLE_DB_VOTE_ID = os.environ["AIRTABLE_DB_VOTE_ID"]

airtable_api = Api(AIRTABLE_TOK)


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
    bot_username = context.bot.username
    message = f"""
🤗 Welcome to our newcomers\\!

To register to the game and be eligible for rewards, \
[send me a DM](https://t.me/{bot_username}?start)\\.

Please read the pinned message to learn more\\.
    """
    await context.bot.send_message(
        chat_id=TG_GROUP_ID,
        message_thread_id=TG_THREAD_ID,
        text=message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


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
        text=f"Hi {user.name}, ready to join the game? Just hit /join.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join", callback_data="/join")]]
        ),
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"join {update.effective_user.name}")
    user = update.effective_user
    part_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_PART_ID)
    fields = {
        "Telegram ID": user.id,
        "Telegram handle": user.username,
        "Telegram name": user.full_name,
    }

    try:
        existing = part_table.all(formula=f"{{Telegram ID}}={fields['Telegram ID']}")
        if not existing:
            part_table.create(fields)
    except Exception:
        logger.exception(f"join-existing {update.effective_user.name}")
        await context.bot.send_message(
            chat_id=user.id, text="🤦1️⃣ An unknown error occurred, we're on it."
        )
        return

    if existing:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "✅ You're already in!\n"
                "Hit /kudo "
                "when you're ready to start sending kudos."
            ),
        )
        return


async def start_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"kudo {update.effective_user.name}")
    user = update.effective_user
    part_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_PART_ID)
    kudo_table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_DB_VOTE_ID)

    try:
        existing_part = part_table.all(formula=f"{{Telegram ID}}={user.id}")
    except Exception:
        logger.exception(f"start_kudo-existing_part {update.effective_user.name}")
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
    except Exception:
        logger.exception(f"start_kudo-existing_kudos {update.effective_user.name}")
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
            "Please write the Telegram handle of the person you'd like to give a kudo to."
            "\nIf you don't want to give kudos anymore, just send /cancel."
        ),
    )
    context.user_data["part_id"] = part_id
    context.user_data["day"] = today
    return SAVE_KUDO


async def unsafe_save_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"save_kudo {update.effective_user.name}")
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
    except Exception:
        logger.exception(f"save_kudo-create {update.effective_user.name}")
        await context.bot.send_message(
            chat_id=user.id, text="🤦4️⃣ An unknown error occurred, we're on it."
        )
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=user.id,
        text=f"💌 Thank you for resgistering your appreciation to {name}!",
    )

    return ConversationHandler.END


async def cancel_kudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"cancel_kudo {update.effective_user.name}")
    user = update.effective_user
    await context.bot.send_message(chat_id=user.id, text="Kudo operation canceled.")
    return ConversationHandler.END


async def catch_all(update: Update, context: CallbackContext):
    if not update.message or update.message.chat.type != "private":
        return

    logger.info(f"catchall {update.effective_user.name}")
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
        else "If you want to join the game, hit /join."
    )

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=("🤷 Command not understood.\n" + complement_text),
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.info(f"cancel_kudo-no_dm {update.effective_user.name}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"join {update.effective_user.name}")
    query = update.callback_query

    if query.data == "/start":
        await start(update, context)
    if query.data == "/join":
        await join(update, context)
    if query.data == "/kudo":
        await join(start_kudo, context)


async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        user_info = f"user {user.id} ({user.username})"
    else:
        user_info = "unknown user"
    logging.info(f"Update from {user_info}: {update.to_dict()}")  #


class DmOrGroupThreadFilter(filters.BaseFilter):
    def __init__(self, group_id, thread_id=None):
        self.group_id = group_id
        self.thread_id = thread_id
        super().__init__(name=None, data_filter=False)

    def check_update(self, update: Update):
        message = update.message
        if message is None:
            return False
        is_dm = message.chat.type == "private"
        is_target_group = message.chat_id == self.group_id
        if self.thread_id:
            is_target_thread = message.message_thread_id == self.thread_id
            return is_dm or (is_target_group and is_target_thread)
        return is_dm or is_target_group


def main() -> None:
    # Create the Application and pass it your bot's token.
    tg_app = Application.builder().token(TG_BOT_TOK).build()

    msg_filter = DmOrGroupThreadFilter(group_id=TG_GROUP_ID, thread_id=TG_THREAD_ID)

    tg_app.add_handler(CommandHandler("greet", greet_new_users, filters=msg_filter))
    tg_app.add_handler(CommandHandler("start", start, filters=msg_filter))
    tg_app.add_handler(CommandHandler("join", join, filters=msg_filter))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("kudo", start_kudo, filters=msg_filter)],
        states={
            SAVE_KUDO: [
                MessageHandler(
                    msg_filter & filters.TEXT & ~filters.COMMAND, unsafe_save_kudo
                )
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_kudo, filters=msg_filter),
            MessageHandler(msg_filter & filters.COMMAND, unsafe_save_kudo),
        ],
    )
    tg_app.add_handler(conv_handler)

    tg_app.add_handler(CallbackQueryHandler(button_callback))

    tg_app.add_handler(MessageHandler(msg_filter, catch_all))

    tg_app.add_handler(MessageHandler(msg_filter, log_all_updates), group=1)

    # Run the bot until the user presses Ctrl-C
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
