"""
Ideation Bot (@ideated_bot)
Main entry point for Python Telegram Bot generating dynamic Singapore Straits Times news-backed app ideas.
"""

import os
import sys
import logging
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import st_scraper
import idea_generator

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def build_theme_keyboard() -> InlineKeyboardMarkup:
    """Builds an InlineKeyboardMarkup containing theme buttons mapped to Straits Times sections."""
    keyboard = []
    row = []
    
    for key, info in st_scraper.THEME_MAP.items():
        row.append(
            InlineKeyboardButton(
                text=info["name"], callback_data=f"theme_{key}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


def build_back_keyboard() -> InlineKeyboardMarkup:
    """Builds a 'Back to Themes' inline keyboard button."""
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start, presenting the main theme selection menu."""
    welcome_text = (
        "🇸🇬 <b>Welcome to Ideation Bot (@ideated_bot)!</b>\n\n"
        "I dynamically scrape the latest <b>Straits Times news articles (published in the last 1 year)</b> "
        "and generate novel, evidence-based application ideas for Singapore!\n\n"
        "Each suggestion features:\n"
        "• 📌 <b>Big Picture Overview</b>\n"
        "• 🟢 <b>Potential User Journeys</b>\n"
        "• 👥 <b>Potential Target Users</b>\n"
        "• 📰 <b>Clickable Straits Times News Citations</b>\n\n"
        "👇 <b>Select a theme to scrape live ST news & generate ideas:</b>"
    )

    if update.message:
        await update.message.reply_text(
            text=welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=build_theme_keyboard(),
        )
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=build_theme_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help, explaining how to use the bot and listing available commands."""
    help_text = (
        "ℹ️ <b>How to use the IDP Ideation Bot?</b>\n\n"
        "1️⃣ Send /start to see the list of news themes (Environment, Health, Transport, etc).\n"
        "2️⃣ Tap a theme button — I'll scrape live Straits Times articles from that section "
        "(published in the last 1 year).\n"
        "3️⃣ I'll generate up to 5 novel app ideas, each grounded in a real news article, with:\n"
        "   • 📌 A big picture overview\n"
        "   • 🧭 A smooth-path and a hard-path user journey\n"
        "   • 👥 Potential target users\n"
        "   • 📰 A clickable citation back to the source article\n"
        "4️⃣ Use the 🔙 <b>Back to Main Menu</b> button to pick another theme, or send /start again.\n\n"
        "<b>Commands:</b>\n"
        "/start — show the theme menu\n"
        "/help — show this message\n"
        "/end — say goodbye and wrap up"
    )
    await update.message.reply_text(text=help_text, parse_mode=ParseMode.HTML)


async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /end, sending a thank-you message and closing out the session."""
    await update.message.reply_text(
        text=(
            "🙏 <b>Thanks for using the IDP Ideation Bot!</b>\n\n"
            "Hope today's ideas were useful. Whenever you're ready for more, "
            "just send /start to pick a theme again. See you next time!"
        ),
        parse_mode=ParseMode.HTML,
    )


async def theme_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles theme button clicks, scrapes live Straits Times articles, and returns 5 dynamic app ideas."""
    query = update.callback_query
    data = query.data

    if data == "main_menu":
        await start_command(update, context)
        return

    if data.startswith("theme_"):
        theme_key = data.replace("theme_", "")
        theme_info = st_scraper.THEME_MAP.get(theme_key)
        theme_name = theme_info["name"] if theme_info else "Theme"

        # Show Telegram loading notification
        await query.answer(f"🔍 Scraping latest Straits Times news for {theme_name}...", show_alert=False)

        # Notify in chat while scraping
        loading_msg = await query.edit_message_text(
            text=f"🔄 <i>Please wait for a minute for the ideas to be generated.</i>",
            parse_mode=ParseMode.HTML,
        )

        # Scrape live articles from Straits Times
        articles = st_scraper.get_live_articles_for_theme(theme_key, max_articles=5)

        if not articles:
            await query.edit_message_text(
                text=f"⚠️ <b>Could not retrieve live Straits Times articles for {theme_name} right now.</b>\n\nPlease try again in a few moments or select another theme.",
                parse_mode=ParseMode.HTML,
                reply_markup=build_back_keyboard(),
            )
            return

        # Generate dynamic app ideas as a list of Telegram messages (header + one per idea)
        messages = idea_generator.format_live_ideas_chunks(theme_key, articles)

        # First message replaces the "scraping..." loading text
        await query.edit_message_text(
            text=messages[0],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
            reply_markup=build_back_keyboard() if len(messages) == 1 else None,
        )

        # Remaining messages sent one at a time; 'Back to Main Menu' button on the last one
        for i, msg in enumerate(messages[1:], start=1):
            is_last = i == len(messages) - 1
            await query.message.reply_text(
                text=msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
                reply_markup=build_back_keyboard() if is_last else None,
            )


def main() -> None:
    """Starts the Telegram bot."""
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error(
            "❌ TELEGRAM_BOT_TOKEN is missing or set to placeholder value!\n"
            "Please open the .env file in your project directory and replace\n"
            "'your_telegram_bot_token_here' with your actual bot token from @BotFather."
        )
        print("\n" + "=" * 65)
        print(" ERROR: TELEGRAM_BOT_TOKEN is not configured.")
        print(" 1. Open the '.env' file in this folder.")
        print(" 2. Set TELEGRAM_BOT_TOKEN=your_token_from_botfather")
        print(" 3. Run 'python main.py' again.")
        print("=" * 65 + "\n")
        sys.exit(1)

    # Initialize Telegram Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("end", end_command))
    application.add_handler(CallbackQueryHandler(start_command, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(theme_callback_handler, pattern="^theme_"))

    print("\n🚀 Ideation Bot (@ideated_bot) is running with LIVE Straits Times Web Scraping!")
    print("Press Ctrl+C to stop the bot.\n")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
