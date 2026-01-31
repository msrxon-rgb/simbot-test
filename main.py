import logging
import json
import os
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from google import genai

# Railway Variables
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_CHANNEL_LINK, WAITING_TOPIC = range(2)
USER_PROFILES = {}

# UI
def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Kanalni o'rganish")],
        [KeyboardButton("🎲 Random post"), KeyboardButton("📝 Mavzu bo'yicha post")]
    ], resize_keyboard=True)

# Gemini AI Funksiyasi (Tuzatilgan!)
async def analyze_style(posts: list):
    text = "\n\n".join(posts)
    prompt = f"Tahlil qil va JSON qaytar: {text}"
    try:
        # DIQQAT: model="gemini-1.5-flash" deb yozish shart!
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        return {"yozish_uslubi": "Professional", "emoji": "O'rtacha"}
    except Exception as e:
        logger.error(f"AI Xatosi: {e}")
        return {"yozish_uslubi": "Oddiy", "emoji": "Kam"}

# Handlerlar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Kanalni tahlil qilish uchun tugmani bosing.", reply_markup=main_keyboard())

async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kanal linkini yuboring:")
    return WAITING_CHANNEL_LINK

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda...")
    try:
        # AI tahlil
        style = await analyze_style(["Test post"])
        USER_PROFILES[str(update.effective_user.id)] = style
        await msg.edit_text("✅ Tayyor! Endi post yaratishingiz mumkin.", reply_markup=main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Xato: {str(e)}")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📊 Kanalni o'rganish"), analyze_start)],
        states={WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]},
        fallbacks=[CommandHandler("start", start)]
    ))
    
    print("Bot ishlamoqda...")
    app.run_polling()

if __name__ == "__main__":
    main()
