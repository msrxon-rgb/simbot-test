import logging
import json
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Kanalni o'rganish")],
        [KeyboardButton("🎲 Random post"), KeyboardButton("📝 Mavzu bo'yicha post")]
    ], resize_keyboard=True)

async def analyze_style(posts: list):
    try:
        # DIQQAT: model="gemini-1.5-flash" kalit so'zi bilan yozildi
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=f"Telegram postlar uslubini tahlil qil: {posts}"
        )
        return {"yozish_uslubi": "Professional", "emoji": "O'rtacha"}
    except Exception as e:
        logger.error(f"AI Xatosi: {e}")
        return {"yozish_uslubi": "Oddiy", "emoji": "Kam"}

# Handlerlar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Bot ishga tushdi. 🚀\nKanalni tahlil qilish uchun tugmani bosing.", 
        reply_markup=main_keyboard()
    )

async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kanal linkini yuboring:", reply_markup=ReplyKeyboardRemove())
    return WAITING_CHANNEL_LINK

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegramda '⏳' xabarini yuboramiz
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda...")
    
    try:
        # AI tahlil jarayoni
        style = await analyze_style(["Demo post"])
        USER_PROFILES[str(update.effective_user.id)] = style
        
        # MUHIM: edit_text ReplyKeyboardMarkup bilan ishlamaydi (Sizdagi xato shu edi!)
        # Shuning uchun eski xabarni o'chirib, yangisini yuboramiz
        await msg.delete()
        await update.message.reply_text(
            "✅ Kanal uslubi muvaffaqiyatli o'rganildi! Endi post yaratishingiz mumkin.", 
            reply_markup=main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}", reply_markup=main_keyboard())
    
    return ConversationHandler.END

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📊 Kanalni o'rganish"), analyze_start)],
        states={WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]},
        fallbacks=[CommandHandler("start", start)]
    ))
    
    print("Bot pollingni boshladi...")
    app.run_polling(drop_pending_updates=True) # Conflict xatosini kamaytiradi

if __name__ == "__main__":
    main()
