import asyncio
import random
import traceback
import os
from pyrogram import Client, types, filters
from pyrogram.errors import AuthRestartError, BroadcastPublicVotersForbidden
from config import API_ID, API_HASH, CHANNEL_ID
from pdd_parser import PDDParser

# Инициализируем клиента
app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=os.environ.get("SESSION_STRING")  # Опционально, для автоматического входа
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

        # Получаем канал
        channel = await app.get_chat(CHANNEL_ID)
        print(f"Канал найден: {channel.title}")

        # Проверяем, есть ли картинка
        image_path = None
        if ticket.get('image_url'):
            # Парсим URL картинки и скачиваем её
            image_url = ticket['image_url']
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://drom.ru' + image_url

            try:
                import requests
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    # Сохраняем временно
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
                caption=f"Билет {ticket['ticket']}, вопрос {ticket['number']}"
            )
            # Удаляем временный файл
            os.remove(image_path)
            print("Картинка отправлена")

        # Создаем опрос с правильными параметрами
        print("Отправляем опрос...")

        poll_message = await app.send_poll(
            chat_id=CHANNEL_ID,
            question=ticket['question'],
            options=ticket['answers'],
            type="quiz",
            correct_option_id=ticket['correct_index'],
            explanation="Ознакомьтесь с объяснением в комментариях.",
            explanation_parse_mode="html",
            is_anonymous=False,  # Для каналов нужно False
            public_voters=False,  # ВАЖНО: для каналов обязательно False
            open_period=None,  # Бессрочно
            close_date=None,
            is_closed=False
        )

        print(f"Опрос отправлен! ID: {poll_message.id}")

        # Ожидаем немного для синхронизации
        await asyncio.sleep(3)

        # Отправляем объяснение в комментарии под спойлером
        try:
            # Получаем информацию о канале для доступа к комментариям
            chat_full = await app.get_chat(CHANNEL_ID)

            if hasattr(chat_full, 'linked_chat_id') and chat_full.linked_chat_id:
                discussion_group_id = chat_full.linked_chat_id
                print(f"Группа обсуждения найдена: {discussion_group_id}")

                # Отправляем объяснение как ответ на опрос
                spoiler_text = f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>"

                await app.send_message(
                    chat_id=discussion_group_id,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )
                print("Объяснение отправлено в комментарии под спойлером!")
            else:
                print("Группа обсуждения не найдена, отправляем в канал")
                spoiler_text = f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>"
                await app.send_message(
                    chat_id=CHANNEL_ID,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )

        except Exception as e:
            print(f"Ошибка при отправке комментария: {e}")
            # Пробуем отправить в канал как ответ
            try:
                spoiler_text = f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>"
                await app.send_message(
                    chat_id=CHANNEL_ID,
                    text=spoiler_text,
                    parse_mode="html",
                    reply_to_message_id=poll_message.id
                )
            except:
                pass

        return True

    except BroadcastPublicVotersForbidden:
        print("Ошибка: Опросы с публичными голосами запрещены в каналах")
        print("Убедитесь, что public_voters=False")
        return False
    except Exception as e:
        print(f"Ошибка: {e}")
        traceback.print_exc()
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")

        # Если есть SESSION_STRING, используем её
        session_string = os.environ.get("SESSION_STRING")
        if session_string:
            await app.start()
        else:
            # Иначе запрашиваем авторизацию
            await app.start()

        print("Подключено!")

        me = await app.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username})")

        # Отправляем викторину
        await send_quiz()

        await app.stop()
        print("Отключено")

    except Exception as e:
        print(f"Ошибка в main: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())