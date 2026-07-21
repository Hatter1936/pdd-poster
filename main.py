import asyncio
import os
import requests
import re
import json
from pyrogram import Client
from pyrogram.errors import BroadcastPublicVotersForbidden
from config import API_ID, API_HASH, CHANNEL_ID
from pdd_parser import PDDParser

# Инициализируем клиента
app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH
)


async def send_quiz():
    parser = PDDParser()

    try:
        # Получаем следующий вопрос
        ticket = parser.get_next_question()

        if not ticket:
            print("Нет вопросов для публикации")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")

        # Проверяем, есть ли картинка
        image_path = None
        if ticket.get('image_url'):
            image_url = ticket['image_url']

            # Обрабатываем URL
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

        # Отправляем картинку если есть
        if image_path and os.path.exists(image_path):
            await app.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_path,
                caption=f"🚦 Билет {ticket['ticket']}, вопрос {ticket['number']}"
            )
            os.remove(image_path)
            print("Картинка отправлена")
            await asyncio.sleep(1)  # Небольшая пауза между сообщениями

        # Отправляем опрос с ПРАВИЛЬНЫМИ параметрами
        print("Отправляем опрос-викторину...")

        # Важно: для каналов эти параметры должны быть такими:
        poll_message = await app.send_poll(
            chat_id=CHANNEL_ID,
            question=ticket['question'],
            options=ticket['answers'],
            type="quiz",  # Режим викторины
            correct_option_id=ticket['correct_index'],  # Индекс правильного ответа
            explanation="ℹ️ Ознакомьтесь с объяснением в комментариях.",  # Текст в лампочке
            explanation_parse_mode="html",
            is_anonymous=False,  # Должно быть False для каналов
            public_voters=False,  # КРИТИЧЕСКИ ВАЖНО: False для каналов
            open_period=None,
            close_date=None,
            is_closed=False,
            disable_notification=False
        )

        print(f"✅ Опрос отправлен! ID: {poll_message.id}")

        # Даем время на синхронизацию с группой комментариев
        await asyncio.sleep(3)

        # Отправляем объяснение в комментарии
        try:
            # Получаем информацию о канале
            chat_full = await app.get_chat(CHANNEL_ID)

            # Проверяем наличие группы комментариев
            if hasattr(chat_full, 'linked_chat') and chat_full.linked_chat:
                discussion_group_id = chat_full.linked_chat.id
                print(f"Группа обсуждения найдена: {discussion_group_id}")

                # Отправляем объяснение под спойлером
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
                    chat_id=CHANNEL_ID,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )

        except Exception as e:
            print(f"Ошибка при отправке комментария: {e}")
            # Пробуем отправить как обычное сообщение в канал
            try:
                spoiler_text = f"<tg-spoiler><b>📖 Объяснение:</b>\n\n{ticket['explanation']}</tg-spoiler>"
                await app.send_message(
                    chat_id=CHANNEL_ID,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )
            except Exception as e2:
                print(f"Не удалось отправить объяснение: {e2}")

        return True

    except BroadcastPublicVotersForbidden:
        print("❌ Ошибка: Опросы с публичными голосами запрещены в каналах")
        print("Убедитесь, что public_voters=False и is_anonymous=False")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")

        # Запускаем клиент
        await app.start()

        print("✅ Подключено!")

        me = await app.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username})")

        # Отправляем викторину
        await send_quiz()

        await app.stop()
        print("Отключено")

    except Exception as e:
        print(f"Ошибка в main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())