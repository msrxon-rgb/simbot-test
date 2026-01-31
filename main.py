import logging
import json
import os
import re
from typing import Dict, Any
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
# Yangi SDK: pip install google-genai
from google import genai 

# ============================================
# API KALITLAR (Railway variables bilan moslash)
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN") # Railwaydagi nom bilan bir xil
GEMINI_API_KEY = os.getenv("GEMINI_KEY")    # Railwaydagi nom bilan bir xil

client = genai.Client(api_key=GEMINI_API_KEY)

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
# DATA SAQLASH
# ============================================

def load_profiles():
    global USER_PROFILES
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                USER_PROFILES = json.load(f)
        except:
            USER_PROFILES = {}

def save_profiles():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(USER_PROFILES, f, ensure_ascii=False, indent=2)

# ============================================
# AI JAVOBINI TOZALASH (MUHIM!)
# ============================================

def clean_json_response(text: str) -> str:
    """Gemini qaytargan ```json ... ``` qismini tozalaydi"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'\s*```', '', text)
    return text.strip()

# ============================================
# GEMINI AI FUNKSIYALARI
# ============================================

async def analyze_style(posts: list) -> Dict:
    text = "\n\n".join(posts)
    prompt = f"""
    Quyidagi Telegram postlar asosida kanal uslubini tahlil qil va FAQAT JSON qaytar:
    {text}
    JSON kalitlari: asosiy_mavzular, yozish_uslubi, post_uzunligi, emoji_darajasi, post_tuzilishi, maqsadli_auditoriya, asosiy_xususiyatlar
    """
    
    try:
        # Yangi SDK uslubi
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        cleaned_text = clean_json_response(response.text)
        data = json.loads(cleaned_text)
        data["sample_posts"] = posts[:5]
        return data
    except Exception as e:
        logger.error(f"AI Analizda xato: {e}")
        return {"asosiy_mavzular": "Umumiy", "yozish_uslubi": "Oddiy"}

async def generate_post(style: Dict, topic: str | None = None) -> str:
    desc = f"Mavzular: {style.get('asosiy_mavzular')}. Uslub: {style.get('yozish_uslubi')}. Emoji: {style.get('emoji_darajasi')}."
    task = f"Mavzu: {topic}" if topic else "Shu uslubda yangi, qiziqarli post yoz."
    prompt = f"Kanal uslubi tahlili: {desc}\n\nTopshiriq: {task}\n\nFaqat post matnini yoz. O'zbek tilida."

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"❌ Xatolik yuz berdi: {str(e)}"

# ============================================
# BOT HANDLERLAR
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) not in USER_PROFILES:
        USER_PROFILES[str(user_id)] = {}
    
    await update.message.reply_text(
        "Assalomu alaykum! 🤖 SMM AI botga xush kelibsiz.\nKanalingiz linkini bering, men uni o'rganib chiqaman.",
        reply_markup=main_keyboard()
    )

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text # Oddiy linkni normalize qilish funksiyangiz ishlaydi
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda, kuting...")
    
    # Demo o'rniga AI tahlilni chaqiramiz
    posts = [
        "🚀 Bugun yangi loyiha boshladik!",
        "💡 Maslahat: Har kuni 10 daqiqa o'zingizga vaqt ajrating.",
        "🔥 Chegirmalar boshlandi!"
    ]
    
    style_data = await analyze_style(posts)
    USER_PROFILES[str(update.effective_user.id)] = {"style": style_data}
    save_profiles()

    await msg.edit_text("✅ Kanal uslubi muvaffaqiyatli saqlandi! Endi post yaratishingiz mumkin.")
    return ConversationHandler.END

# Qolgan funksiyalarni (main_keyboard, random_post va h.k.) o'z holicha qoldiring
# Faqat USER_PROFILES[str(user_id)] shaklida chaqirishni unutmang.

def main():
    load_profiles()
    # Tokenni tekshirish
    if not TELEGRAM_BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlerlarni qo'shish (Sizning kodingizdagidek...)
    app.add_handler(CommandHandler("start", start))
    
    # ConversationHandlerlar...
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📊 Kanalni o'rganish"), analyze_start)],
        states={
            WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(conv_handler)
    
    # Boshqa xabarlar uchun
    app.add_handler(MessageHandler(filters.Regex("🎲 Random post"), random_post))
    app.add_handler(MessageHandler(filters.Regex("ℹ️ Yordam"), help_cmd))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
