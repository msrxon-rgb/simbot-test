import logging
import json
import os
import re
import asyncio
from typing import Dict, Any
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
# Muhim: pip install google-genai
from google import genai

# ============================================
# API KALITLAR (Railway Variables bilan bir xil bo'lishi shart)
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

# Gemini Klientini tekshirib ishga tushirish
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None

# ============================================
# LOGGING SOZLAMALARI
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_CHANNEL_LINK, WAITING_TOPIC = range(2)
USER_DATA_FILE = "user_profiles.json"
USER_PROFILES: Dict[str, Any] = {}

# ============================================
# MA'LUMOTLARNI SAQLASH
# ============================================

def load_profiles():
    global USER_PROFILES
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                USER_PROFILES = json.load(f)
        except Exception as e:
            logger.error(f"Fayl yuklashda xato: {e}")
            USER_PROFILES = {}

def save_profile(user_id: int, profile: Dict):
    USER_PROFILES[str(user_id)] = profile
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(USER_PROFILES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Saqlashda xato: {e}")

# ============================================
# YORDAMCHI FUNKSIYALAR
# ============================================

def clean_json_response(text: str) -> str:
    """Gemini qaytargan ```json ... ``` qismini olib tashlaydi"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'\s*```', '', text)
    return text.strip()

def main_keyboard():
    keyboard = [
        [KeyboardButton("📊 Kanalni o'rganish")],
        [KeyboardButton("🎲 Random post"), KeyboardButton("📝 Mavzu bo'yicha post")],
        [KeyboardButton("ℹ️ Yordam")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================
# GEMINI AI FUNKSIYALARI
# ============================================

async def analyze_style(posts: list) -> Dict:
    if not client: return {"error": "API Key yo'q"}
    
    text = "\n\n".join(posts)
    prompt = f"""
    Quyidagi Telegram postlar asosida kanal uslubini tahlil qil va FAQAT JSON qaytar:
    {text}
    JSON kalitlari: asosiy_mavzular, yozish_uslubi, emoji_darajasi, auditoriya.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        cleaned_text = clean_json_response(response.text)
        return json.loads(cleaned_text)
    except Exception as e:
        logger.error(f"Analiz xatosi: {e}")
        return {"yozish_uslubi": "Oddiy", "emoji_darajasi": "O'rtacha"}

async def generate_post(style: Dict, topic: str | None = None) -> str:
    if not client: return "❌ Gemini API kaliti ulanmagan."
    
    desc = f"Uslub: {style.get('yozish_uslubi')}. Emoji: {style.get('emoji_darajasi')}."
    task = f"Mavzu: {topic}" if topic else "Qiziqarli yangi post yoz."
    prompt = f"Kanal uslubi: {desc}\nTopshiriq: {task}\nFaqat o'zbekcha post matnini qaytar."

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"❌ Xatolik yuz berdi: {str(e)}"

# ============================================
# BOT HANDLERLARI
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 🤖 SMM AI botingiz tayyor.\n\n"
        "1. 'Kanalni o'rganish' tugmasini bosing.\n"
        "2. Kanal linkini yuboring.\n"
        "3. Men sizga mos postlar yozib beraman.",
        reply_markup=main_keyboard()
    )

async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kanal linkini yoki oxirgi postlarni yuboring:")
    return WAITING_CHANNEL_LINK

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda...")
    
    # Test uchun demo postlar (bu yerga scraper ulasangiz bo'ladi)
    demo_posts = ["Salom! Bugun yangi kun.", "Chegirmalar tugashiga 2 kun qoldi! 🔥"]
    
    style_data = await analyze_style(demo_posts)
    save_profile(update.effective_user.id, {"style": style_data})

    await msg.edit_text("✅ Tahlil yakunlandi! Endi post yaratishingiz mumkin.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def random_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in USER_PROFILES:
        await update.message.reply_text("Avval kanalni o'rgating!")
        return

    msg = await update.message.reply_text("📝 Post tayyorlanmoqda...")
    post = await generate_post(USER_PROFILES[user_id]["style"])
    await msg.delete()
    await update.message.reply_text(post)

async def topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Post mavzusini yozing:")
    return WAITING_TOPIC

async def topic_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    topic = update.message.text
    msg = await update.message.reply_text("📝 Post yozilmoqda...")
    post = await generate_post(USER_PROFILES[user_id]["style"], topic)
    await msg.delete()
    await update.message.reply_text(post)
    return ConversationHandler.END

# ============================================
# ASOSIY ISHGA TUSHIRISH
# ============================================

def main():
    load_profiles()
    
    if not TELEGRAM_BOT_TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation Handlerlar
    analyze_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📊 Kanalni o'rganish"), analyze_start)],
        states={WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]},
        fallbacks=[CommandHandler("start", start)]
    )

    topic_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📝 Mavzu bo'yicha post"), topic_start)],
        states={WAITING_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, topic_process)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(analyze_conv)
    app.add_handler(topic_conv)
    app.add_handler(MessageHandler(filters.Regex("🎲 Random post"), random_post))
    app.add_handler(MessageHandler(filters.Regex("ℹ️ Yordam"), start))

    print("Bot polling boshladi...")
    app.run_polling()

if __name__ == "__main__":
    main()
