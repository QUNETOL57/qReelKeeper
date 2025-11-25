import os
import re
import logging
import asyncio
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
from collections.abc import Generator
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


@contextmanager
def managed_video_file(video_path: Optional[Path]) -> Generator[Optional[Path]]:
    """Контекстный менеджер для автоматического удаления видео файла"""
    try:
        yield video_path
    finally:
        if video_path and video_path.exists():
            try:
                video_path.unlink()
                logger.info(f"Файл {video_path.name} удален из локального хранилища")
            except OSError as e:
                logger.error(f"Ошибка при удалении файла {video_path}: {e}")


def is_instagram_url(url: str) -> bool:
    instagram_patterns = [
        r'https?://(www\.)?instagram\.com/.*',
        r'https?://(www\.)?instagr\.am/.*',
    ]
    return any(re.match(pattern, url) for pattern in instagram_patterns)


async def download_instagram_video(url: str, user_id: int) -> dict[str, bool | str]:
    output_template = str(DOWNLOADS_DIR / f"{user_id}_%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        def download() -> dict[str, bool | str]:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return {
                    'success': True,
                    'filename': filename,
                    'title': info.get('title', 'video'),
                }
        
        result = await asyncio.to_thread(download)
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании видео: {e}")
        return {
            'success': False,
            'error': str(e)
        }


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = (
        "🎥 Привет! Я бот для скачивания видео из Instagram.\n\n"
        "📝 Просто отправь мне ссылку на пост/reels/story из Instagram, "
        "и я скачаю видео и отправлю его тебе.\n\n"
        "Поддерживаемые форматы:\n"
        "• instagram.com/p/...\n"
        "• instagram.com/reel/...\n"
        "• instagram.com/stories/...\n\n"
        "Просто отправь ссылку!"
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_message = (
        "ℹ️ Как использовать бота:\n\n"
        "1. Найди видео в Instagram\n"
        "2. Скопируй ссылку на пост\n"
        "3. Отправь ссылку мне\n"
        "4. Жди, пока я скачаю и отправлю видео\n\n"
        "Примеры ссылок:\n"
        "• https://www.instagram.com/p/ABC123/\n"
        "• https://www.instagram.com/reel/XYZ789/"
    )
    await update.message.reply_text(help_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id
    
    logger.info(f"Получено сообщение от {user_name} (ID: {user_id}): {user_message}")
    
    if not is_instagram_url(user_message):
        await update.message.reply_text(
            "❌ Это не похоже на ссылку Instagram.\n"
            "Пожалуйста, отправьте корректную ссылку на пост, reels или story.\n\n"
            "Пример: https://www.instagram.com/p/ABC123/"
        )
        return
    
    status_message = await update.message.reply_text("⏳ Начинаю скачивание видео...")
    
    result = await download_instagram_video(user_message, user_id)
    
    if not result['success']:
        await status_message.edit_text(
            f"❌ Ошибка при скачивании видео:\n{result['error']}\n\n"
            "Возможные причины:\n"
            "• Видео недоступно или удалено\n"
            "• Аккаунт приватный\n"
            "• Неверная ссылка\n"
            "• Это фото, а не видео"
        )
        return
    
    video_path = Path(result['filename'])
    
    with managed_video_file(video_path):
        try:
            if not video_path.exists():
                await status_message.edit_text("❌ Ошибка: файл не найден после скачивания")
                return
            
            file_size = video_path.stat().st_size
            max_size = 50 * 1024 * 1024  # 50 МБ - лимит Telegram для ботов
            
            if file_size > max_size:
                await status_message.edit_text(
                    f"❌ Файл слишком большой ({file_size / (1024*1024):.1f} МБ).\n"
                    f"Максимальный размер: {max_size / (1024*1024):.0f} МБ"
                )
                return
            
            await status_message.edit_text("📤 Отправляю видео...")
            
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"🎬 {result['title'][:100]}\n\n<a href=\"{user_message}\">Оригинал</a>",
                    supports_streaming=True,
                    parse_mode="HTML"
                )
            
            await status_message.delete()
            logger.info(f"Видео успешно отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения от {user_name} (ID: {user_id}): {e}", exc_info=True)
            await status_message.edit_text(
                "😔 Произошла ошибка при обработке вашего запроса.\n"
                "Пожалуйста, попробуйте ещё раз или отправьте /help для справки."
            )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Критическая ошибка: {context.error}", exc_info=context.error)
    
    if update and update.message:
        await update.message.reply_text(
            "😔 Произошла критическая ошибка при обработке вашего сообщения.\n"
            "Пожалуйста, попробуйте ещё раз."
        )


def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        logger.critical(f"Не удалось создать приложение: {e}", exc_info=True)
        raise
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("Бот запущен и готов к работе!")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Критическая ошибка при работе бота: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
