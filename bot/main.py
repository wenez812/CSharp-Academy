import os, asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import httpx

TOKEN=os.getenv('BOT_TOKEN','')
WEBAPP_URL=os.getenv('WEBAPP_URL','')
API_URL=os.getenv('API_URL','http://backend:8000')
if not TOKEN: raise RuntimeError('Set BOT_TOKEN in .env')
if not WEBAPP_URL: raise RuntimeError('Set WEBAPP_URL in .env to your HTTPS web app URL')
bot=Bot(TOKEN); dp=Dispatcher()

def webapp_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🚀 Открыть C# Academy',web_app=WebAppInfo(url=WEBAPP_URL))]])

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer('Привет! Это C# Academy — учебный курс от основ C# до ASP.NET Core и деплоя.\n\nВнутри: короткие объяснения, примеры, 2 практических задания на урок и редактор кода. Начни с первого урока и двигайся постепенно.',reply_markup=webapp_keyboard())

@dp.message(Command('course'))
async def course(message: Message): await message.answer('Открывай уроки в веб-приложении:',reply_markup=webapp_keyboard())

@dp.message(Command('progress'))
async def progress(message: Message):
    try:
        async with httpx.AsyncClient(timeout=5) as c: r=await c.get(API_URL+'/api/progress',headers={'X-Telegram-Init-Data':''})
        # API intentionally validates Telegram WebApp initData; bot progress is read from DB by user ID below.
        from pathlib import Path
        import sqlite3
        db_path=os.getenv('DB_PATH','/app/data/academy.sqlite3')
        conn=sqlite3.connect(db_path); rows=conn.execute('SELECT COUNT(*),SUM(completed) FROM progress WHERE user_id=?',(str(message.from_user.id),)).fetchone(); conn.close()
        total=28; done=rows[1] or 0
        await message.answer(f'📊 Твой прогресс: {done}/{total} уроков ({round(done/total*100)}%).\n\nПродолжай обучение:',reply_markup=webapp_keyboard())
    except Exception:
        await message.answer('Не удалось прочитать прогресс. Открой курс и попробуй ещё раз.',reply_markup=webapp_keyboard())

@dp.message(Command('review'))
async def review(message: Message):
    await message.answer('Повторение: возвращайся к темам, которые показались сложными. В веб-приложении нажми «Повторить сложные темы».',reply_markup=webapp_keyboard())

@dp.message(Command('help'))
async def help_cmd(message: Message):
    await message.answer('/start — открыть курс\n/course — открыть уроки\n/progress — посмотреть прогресс\n/review — повторение тем')

async def main(): await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())
