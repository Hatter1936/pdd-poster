import asyncio
import os
import sys
import requests
import json
from pyrogram import Client
from pyrogram.errors import BroadcastPublicVotersForbidden, SessionPasswordNeeded

try:
    from config import API_ID, API_HASH, CHANNEL_ID, SESSION_STRING
except ImportError as e:
    print(f"❌ Ошибка импорта config.py: {e}")
    sys.exit(1)

# Проверяем конфиг перед запуском
if not API_ID or not API_HASH or not CHANNEL_ID:
    print("❌ Критическая ошибка: Неправильные данные в config.py")
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {'***' if API_HASH else '❌'}")
    print(f"CHANNEL_ID: {CHANNEL_ID}")
    sys.exit(1)

from pdd_parser import PDDParser

# Инициализируем клиента
app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING if SESSION_STRING else None
)


async def send_quiz():
    parser = PDDParser()

    try:
        ticket = parser.get_next_question()

        if not ticket:
            print("Нет вопросов для публикации")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")

        # Скачиваем картинку
        image_path = None
        if ticket.get('image_url'):
            image_url = ticket['image_url']

            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://drom.ru' + image_url

            try:
                print(f"Скачиваем картинку: {image_url}")
                response = requests.get(image_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if response.status_code == 200:
                    temp_image = f"temp_{ticket['number']}.jpg"
                    with open(temp_image, 'wb') as f:
                        f.write(response.content)
                    image_path = temp_image
                    print("Картинка скачана")
            except Exception as e:
                print(f"Не удалось скачать картинку: {e}")

        # Отправляем картинку
        if image_path and os.path.exists(image_path):
            await app.send_photo(
                chat_id=CHANNEL_ID,  # CHANNEL_ID теперь строка
                photo=image_path,
                caption=f"🚦 Билет {ticket['ticket']}, вопрос {ticket['number']}"
            )
            os.remove(image_path)
            print("Картинка отправлена")
            await asyncio.sleep(1)

        # Отправляем опрос
        print("Отправляем опрос-викторину...")

        poll_message = await app.send_poll(
            chat_id=CHANNEL_ID,  # CHANNEL_ID теперь строка
            question=ticket['question'],
            options=ticket['answers'],
            type="quiz",
            correct_option_id=ticket['correct_index'],
            explanation="ℹ️ Ознакомьтесь с объяснением в комментариях.",
            explanation_parse_mode="html",
            is_anonymous=False,
            public_voters=False,
            open_period=None,
            close_date=None,
            is_closed=False,
            disable_notification=False
        )

        print(f"✅ Опрос отправлен! ID: {poll_message.id}")

        await asyncio.sleep(3)

        # Отправляем объяснение
        try:
            chat_full = await app.get_chat(CHANNEL_ID)  # CHANNEL_ID теперь строка

            if hasattr(chat_full, 'linked_chat') and chat_full.linked_chat:
                discussion_group_id = chat_full.linked_chat.id
                print(f"Группа обсуждения найдена: {discussion_group_id}")

                spoiler_text = f"<tg-spoiler><b>📖 Объяснение:</b>\n\n{ticket['explanation']}</tg-spoiler>"

                await app.send_message(
                    chat_id=discussion_group_id,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )
                print("✅ Объяснение отправлено в комментарии под спойлером!")
            else:
                print("⚠️ Группа обсуждения не найдена, отправляем в канал")
                spoiler_text = f"<tg-spoiler><b>📖 Объяснение:</b>\n\n{ticket['explanation']}</tg-spoiler>"
                await app.send_message(
                    chat_id=CHANNEL_ID,  # CHANNEL_ID теперь строка
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )

        except Exception as e:
            print(f"Ошибка при отправке комментария: {e}")
            try:
                spoiler_text = f"<tg-spoiler><b>📖 Объяснение:</b>\n\n{ticket['explanation']}</tg-spoiler>"
                await app.send_message(
                    chat_id=CHANNEL_ID,  # CHANNEL_ID теперь строка
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )
            except Exception as e2:
                print(f"Не удалось отправить объяснение: {e2}")

        return True

    except BroadcastPublicVotersForbidden:
        print("❌ Ошибка: Опросы с публичными голосами запрещены в каналах")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")

        if SESSION_STRING:
            print("Используем SESSION_STRING для авторизации")
            await app.start()
        else:
            print("⚠️ SESSION_STRING не найден, пробуем обычную авторизацию")
            await app.start()

        print("✅ Подключено!")

        me = await app.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username})")

        # Проверяем доступ к каналу (CHANNEL_ID теперь строка)
        try:
            channel = await app.get_chat(CHANNEL_ID)
            print(f"✅ Канал найден: {channel.title}")
        except Exception as e:
            print(f"❌ Ошибка доступа к каналу: {e}")
            return

        await send_quiz()
        await app.stop()
        print("Отключено")

    except SessionPasswordNeeded:
        print("❌ Требуется пароль двухфакторной аутентификации")
        print("Создайте SESSION_STRING с паролем или обновите сессию")
    except Exception as e:
        print(f"Ошибка в main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())