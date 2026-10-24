import asyncio
import re
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, URLInputFile
from playwright.async_api import async_playwright

# ВАШИ ДАННЫЕ
BOT_TOKEN = "8857801173:AAF9zEETX-u0jstujrZzJ6LToNucB1bMmnA"
LOGIN = "qizjxbejsid"  
PASSWORD = "Polpol1212!"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_links = {}

# 1. Авторизация
async def ensure_auth():
    state_file = "auth_state.json"
    if os.path.exists(state_file):
        return  
    
    print("Авторизация...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://fapfolder.club/signin", wait_until="networkidle")
        await page.fill('input[placeholder="Ваш E-mail или Логин"]', LOGIN)
        await page.fill('input[placeholder="Пароль"]', PASSWORD)
        await page.click('button:has-text("Войти")')
        
        await page.wait_for_timeout(5000)
        await context.storage_state(path=state_file)
        await browser.close()
        print("Авторизация успешна!")

# 2. Сбор медиа
async def scrape_media(url: str, media_type: str):
    media_urls = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="auth_state.json")
        page = await context.new_page()

        def handle_response(response):
            if response.request.resource_type in ["image", "media"]:
                u = response.url
                if any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".mp4"]):
                    if u not in media_urls and "avatar" not in u and "logo" not in u:
                        media_urls.append(u)

        page.on("response", handle_response)
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000) 

        # Жмем "Больше" 3 раза
        for _ in range(3):
            try:
                btn = page.locator("text=Больше")
                if await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(2000)
            except:
                break

        await browser.close()
    return media_urls

# 3. Обработка в Telegram
@dp.message(F.text.contains("fapfolder.club/groups/"))
async def handle_link(message: Message):
    url = message.text.strip()
    match = re.search(r"/groups/([^/]+)", url)
    if not match:
        await message.answer("Неверная ссылка.")
        return
    group_name = match.group(1)
    user_links[message.from_user.id] = group_name

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Фотки", callback_data="photos"),
         InlineKeyboardButton(text="🎥 Видео", callback_data="videos")]
    ])
    await message.answer(f"Группа: {group_name}. Что качаем?", reply_markup=keyboard)

@dp.callback_query(F.data.in_({"photos", "videos"}))
async def send_media(callback: CallbackQuery):
    group_name = user_links.get(callback.from_user.id)
    if not group_name:
        await callback.answer("Кинь ссылку.")
        return

    await callback.message.edit_text("⏳ Ищу файлы, жди...")
    media_type = callback.data
    base_url = f"https://fapfolder.club/groups/{group_name}/{media_type}"

    try:
        await ensure_auth()
        media_urls = await scrape_media(base_url, media_type)
        
        if not media_urls:
            await callback.message.edit_text("Ничего не найдено. Может, аккаунт не подписан на группу?")
            return

        sent = 0
        for i in range(0, min(len(media_urls), 40), 10):
            chunk = media_urls[i:i+10]
            group = []
            for u in chunk:
                if media_type == "photos":
                    group.append(InputMediaPhoto(media=URLInputFile(u)))
                else:
                    group.append(InputMediaVideo(media=URLInputFile(u)))
            
            await bot.send_media_group(chat_id=callback.from_user.id, media=group)
            sent += len(chunk)
            await asyncio.sleep(3)

        await callback.message.edit_text(f"✅ Готово! Отправлено: {sent}")

    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {e}")

async def main():
    print("Бот запускается...")
    await ensure_auth() 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())