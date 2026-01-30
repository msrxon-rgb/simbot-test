import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import google.generativeai as genai

# Railway Variables bo'limidan olinadigan kalitlar
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class SimbotStates(StatesGroup):
    waiting_for_link = State()
    main_menu = State()
    waiting_for_content = State()

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🤖 **Simbot AI-ga xush kelibsiz!**\n\n"
        "Men kanal uslubini o'rganib, sizga postlar tayyorlayman.\n"
        "🔗 **Iltimos, kanal linkini yuboring:**"
    )
    await state.set_state(SimbotStates.waiting_for_link)

@dp.message(SimbotStates.waiting_for_link)
async def handle_link(message: types.Message, state: FSMContext):
    if "t.me/" in message.text:
        await message.answer("🔍 Kanal uslubi tahlil qilinmoqda...")
        await state.update_data(style_link=message.text)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Post yozish", callback_data="write_post")]
        ])
        await message.answer("✅ Tayyor! Endi post yozishimiz mumkin.", reply_markup=kb)
        await state.set_state(SimbotStates.main_menu)
    else:
        await message.answer("⚠️ Iltimos, to'g'ri kanal linkini yuboring.")

@dp.callback_query(F.data == "write_post")
async def ask_content(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🖋 Post mazmunini yuboring:")
    await state.set_state(SimbotStates.waiting_for_content)

@dp.message(SimbotStates.waiting_for_content)
async def create_post(message: types.Message, state: FSMContext):
    content = message.text
    await state.update_data(last_content=content)
    msg = await message.answer("⏳ AI ishlamoqda...")
    data = await state.get_data()
    prompt = f"Professional SMM uslubida post yoz. Mazmun: {content}. Kanal: {data.get('style_link')}"
    
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Qayta yozish", callback_data="rewrite")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="main_menu")]
        ])
        await msg.edit_text(response.text, reply_markup=kb)
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data == "rewrite")
async def rewrite(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer("🔄 Yangilanmoqda...")
    prompt = f"Ushbu postni boshqacha variantda qayta yoz: {data.get('last_content')}"
    response = await asyncio.to_thread(model.generate_content, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Qayta yozish", callback_data="rewrite")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="main_menu")]
    ])
    await callback.message.edit_text(response.text, reply_markup=kb)

@dp.callback_query(F.data == "main_menu")
async def menu(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Post yozish", callback_data="write_post")]
    ])
    await callback.message.answer("🏠 Asosiy menyu:", reply_markup=kb)
    await state.set_state(SimbotStates.main_menu)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
