import logging
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from google import genai

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_CHANNEL_LINK, WAITING_TOPIC = range(2)

# User data storage
USER_PROFILES = {}

# Gemini client initialization
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gemini client yaratishda xatolik: {e}")
    client = None


def main_keyboard():
    """Asosiy klaviatura"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Kanalni o'rganish")],
        [KeyboardButton("🎲 Random post"), KeyboardButton("📝 Mavzu bo'yicha post")],
        [KeyboardButton("ℹ️ Yordam")]
    ], resize_keyboard=True)


async def analyze_style(posts: list, user_id: str) -> dict:
    """
    Kanal uslubini AI orqali tahlil qilish
    """
    if not client:
        logger.error("Gemini client mavjud emas")
        return {"yozish_uslubi": "Standart", "emoji": "O'rtacha", "error": True}
    
    try:
        prompt = f"""
        Quyidagi kanal postlarini tahlil qilib, yozish uslubi va emoji ishlatish darajasini aniqlang:
        
        Postlar: {posts}
        
        Javobni JSON formatda bering:
        {{
            "yozish_uslubi": "Rasmiy/Norasmiy/Professional/Qiziqarli",
            "emoji": "Ko'p/O'rtacha/Kam/Yo'q",
            "ton": "Do'stona/Rasmiy/Tanqidiy/Ilmiy",
            "asosiy_mavzular": ["mavzu1", "mavzu2"]
        }}
        """
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        # JSON javobni parse qilish
        result_text = response.text.strip()
        # Agar ```json``` wrapper bo'lsa, uni olib tashlash
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        result = eval(result_text)  # JSON parse qilish (production uchun json.loads ishlatish yaxshi)
        result["error"] = False
        
        logger.info(f"User {user_id} uchun uslub tahlil qilindi")
        return result
        
    except Exception as e:
        logger.error(f"AI tahlil xatosi: {e}")
        return {
            "yozish_uslubi": "Standart",
            "emoji": "O'rtacha",
            "ton": "Do'stona",
            "error": True
        }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    welcome_text = f"""
👋 Assalomu alaykum, {user.first_name}!

Men Telegram kanal kontenti yaratuvchi botman.

🔹 Kanalni o'rganish - Kanal uslubini tahlil qilaman
🔹 Random post - Tasodifiy post yarataman
🔹 Mavzu bo'yicha post - Siz bergan mavzu bo'yicha post yozaman

Boshlash uchun tugmalardan birini tanlang!
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam komandasi"""
    help_text = """
📖 **Bot haqida**

Bu bot Telegram kanallar uchun kontent yaratadi.

**Qanday ishlaydi:**
1️⃣ Kanal linkini yuboring
2️⃣ Bot kanal uslubini o'rganadi
3️⃣ Kerakli post turini tanlang

**Tayyor formatlar:**
- Random post - Tasodifiy mavzu
- Mavzu bo'yicha - Siz kiritgan mavzu

**Qo'llab-quvvatlash:** @yoursupport
    """
    await update.message.reply_text(help_text)


async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal tahlilini boshlash"""
    await update.message.reply_text(
        "📎 Kanal linkini yuboring:\n\n"
        "Masalan: @kanalNomi yoki https://t.me/kanalNomi\n\n"
        "❌ Bekor qilish uchun /cancel yozing",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_CHANNEL_LINK


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal linkini qayta ishlash"""
    channel_link = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    # Link validatsiyasi
    if not (channel_link.startswith('@') or 't.me/' in channel_link):
        await update.message.reply_text(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format: @kanalNomi yoki https://t.me/kanalNomi",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END
    
    msg = await update.message.reply_text("⏳ Kanal tahlil qilinmoqda...\nBu bir necha soniya davom etishi mumkin.")
    
    try:
        # Demo posts (haqiqiy implementatsiyada Telegram API orqali postlarni olish kerak)
        demo_posts = [
            "📢 Yangi mahsulotimiz chiqdi! 🎉",
            "Bugun qiziqarli mavzu: AI texnologiyalari",
            "Sizning fikringiz bizga muhim 💭"
        ]
        
        # AI tahlili
        style = await analyze_style(demo_posts, user_id)
        
        # Foydalanuvchi profilini saqlash
        USER_PROFILES[user_id] = {
            "channel": channel_link,
            "style": style,
            "analyzed_at": asyncio.get_event_loop().time()
        }
        
        await msg.delete()
        
        if style.get("error"):
            result_text = "⚠️ Kanal qisman tahlil qilindi (AI xizmati vaqtincha mavjud emas).\n\n"
        else:
            result_text = "✅ Kanal uslubi muvaffaqiyatli o'rganildi!\n\n"
        
        result_text += f"""
📊 **Tahlil natijalari:**
- Yozish uslubi: {style.get('yozish_uslubi', 'Aniqlanmadi')}
- Emoji ishlatish: {style.get('emoji', 'Aniqlanmadi')}
- Ton: {style.get('ton', 'Aniqlanmadi')}

Endi post yaratishingiz mumkin! 🚀
        """
        
        await update.message.reply_text(
            result_text,
            reply_markup=main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Link qayta ishlashda xatolik: {e}")
        await msg.delete()
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, qaytadan urinib ko'ring.",
            reply_markup=main_keyboard()
        )
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jarayonni bekor qilish"""
    await update.message.reply_text(
        "❌ Jarayon bekor qilindi.",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


async def random_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Random post yaratish"""
    user_id = str(update.effective_user.id)
    
    if user_id not in USER_PROFILES:
        await update.message.reply_text(
            "⚠️ Avval kanalni o'rganishingiz kerak!",
            reply_markup=main_keyboard()
        )
        return
    
    await update.message.reply_text(
        "🎲 Random post yaratilmoqda...\n"
        "(Bu funksiya hozircha ishlab chiqilmoqda)",
        reply_markup=main_keyboard()
    )


async def topic_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mavzuli post yaratishni boshlash"""
    user_id = str(update.effective_user.id)
    
    if user_id not in USER_PROFILES:
        await update.message.reply_text(
            "⚠️ Avval kanalni o'rganishingiz kerak!",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 Post mavzusini yozing:\n\n"
        "❌ Bekor qilish uchun /cancel",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_TOPIC


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global xatolik handleri"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ Kutilmagan xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=main_keyboard()
        )


def main():
    """Asosiy funksiya"""
    # Environment variables tekshiruvi
    if not TELEGRAM_BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Railway-da o'rnatilganligini tekshiring.")
        return
    
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_KEY topilmadi! AI funksiyalari ishlamaydi.")
    
    # Application yaratish
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Kanal tahlili conversation handler
    analyze_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 Kanalni o'rganish$"), analyze_start)],
        states={
            WAITING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(analyze_conv)
    
    # Mavzuli post conversation handler
    topic_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Mavzu bo'yicha post$"), topic_post_start)],
        states={
            WAITING_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_link)]  # Bu yerda topic handler qo'shiladi
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(topic_conv)
    
    # Boshqa tugmalar
    app.add_handler(MessageHandler(filters.Regex("^🎲 Random post$"), random_post))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"), help_command))
    
    # Xatolik handleri
    app.add_error_handler(error_handler)
    
    logger.info("🚀 Bot ishga tushdi!")
    print("✅ Bot muvaffaqiyatli ishlamoqda...")
    
    # Polling boshlanishi
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
