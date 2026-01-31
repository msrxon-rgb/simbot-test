import logging
import os
import asyncio
import json
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from google import genai

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
WAITING_CHANNEL_LINK, WAITING_TOPIC = range(2)
USER_PROFILES = {}

# Gemini Client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gemini xatosi: {e}")
    client = None

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Kanalni o'rganish")],
        [KeyboardButton("🎲 Random post"), KeyboardButton("📝 Mavzu bo'yicha post")],
        [KeyboardButton("ℹ️ Yordam")]
    ], resize_keyboard=True)

# AI javobini tozalash funksiyasi
def clean_json(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'\s*```', '', text)
    return text.strip()

async def analyze_style(posts: list):
    if not client: return {"yozish_uslubi": "Standart", "error": True}
    
    prompt = f"Ushbu postlar asosida kanal uslubini JSON formatda tahlil qil: {posts}. Kalitlar: yozish_uslubi, emoji, ton"
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        data = json.loads(clean_json(response.text))
        return data
    except Exception as e:
        logger.error(f"AI Analiz xatosi: {e}")
        return {"yozish_uslubi": "Standart", "emoji": "O'rtacha", "ton": "Do'stona"}

# --- Handlerlar ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Salom {update.effective_user.first_name}! SMM AI botga xush kelibsiz.",
        reply_markup=main_keyboard()
    )

async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📎 Kanal linkini yuboring (@kanal yoki link):", reply_markup=ReplyKeyboardRemove())
    return WAITING_CHANNEL_LINK

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    link = update.message.text
    
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda...")
    
    # Demo tahlil
    style = await analyze_style(["Yangi post!", "Ajoyib kun! ✨"])
    USER_PROFILES[user_id] = {"style": style}
    
    await msg.delete()
    await update.message.reply_text(
        f"✅ Kanal o'rganildi!\nUslub: {style.get('yozish_uslubi')}\nEmoji: {style.get('emoji')}",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def topic_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in USER_PROFILES:
        await update.message.reply_text("⚠️ Avval kanalni o'rganish tugmasini bosing!")
        return ConversationHandler.END
    
    await update.message.reply_text("📝 Post mavzusini yozing:", reply_markup=ReplyKeyboardRemove())
    return WAITING_TOPIC

async def process_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    topic = update.message.text
    style = USER_PROFILES[user_id]['style']
    
    msg = await update.message.reply_text("✍️ Post yozilmoqda...")
    
    try:
        prompt = f"Ushbu uslubda: {style}. Mavzu: {topic}. Faqat post matnini yoz."
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        await msg.delete()
        await update.message.reply_text(response.text, reply_markup=main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Xato: {e}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=main_keyboard())
    return ConversationHandler.END

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("BOT_TOKEN topilmadi!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Kanal tahlili
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 Kanalni o'rganish$"), analyze_start)],
        states={WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Mavzu bo'yicha post
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Mavzu bo'yicha post$"), topic_post_start)],
        states={WAITING_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_topic)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🎲 Random post$"), lambda u, c: u.message.reply_text("Mavzu kiriting!")))
    
    print("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
