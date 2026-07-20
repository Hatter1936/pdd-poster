import asyncio
import random
import traceback
import os
from pyrogram import Client
from pdd_parser import PDDParser

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '')  # Теперь строка, а не число
SESSION_STRING = os.environ.get('SESSION_STRING', '')

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("Ошибка: не заданы API_ID, API_HASH или CHANNEL_ID")
    exit(1)

if not SESSION_STRING:
    print("Ошибка: не задана SESSION_STRING")
    exit(1)

app = Client(
    "my_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)
parser = PDDParser('progress.json')


async def send_quiz():
    try:
        ticket = parser.get_next_question()
        if not ticket:
            print("Не удалось получить вопрос")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")

        if ticket.get('image_url'):
            try:
                await app.send_photo(CHANNEL_ID, ticket['image_url'])
                print("Картинка отправлена")
            except Exception as e:
                print(f"Не удалось отправить картинку: {e}")

        options = [f"{i + 1}. {a}" for i, a in enumerate(ticket['answers'])]

        poll_message = await app.send_poll(
            CHANNEL_ID,
            question=ticket['question'],
            options=options,
            type="quiz",
            correct_option_id=ticket['correct_index'],
            explanation="Ознакомьтесь с объяснением в комментариях."
        )

        await asyncio.sleep(2)

        explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
        await app.send_message(CHANNEL_ID, explanation_text, reply_to_message_id=poll_message.id)

        print(f"Пост отправлен! Билет {ticket['ticket']}, вопрос {ticket['number']}")
        return True

    except Exception as e:
        print(f'Ошибка: {e}')
        print(traceback.format_exc())
        return False


async def main():
    try:
        print("Подключаюсь к Telegram...")
        await app.start()
        print("Подключено!")

        me = await app.get_me()
        print(f"{me.first_name} (@{me.username})")

        # Проверяем, что канал существует
        try:
            chat = await app.get_chat(CHANNEL_ID)
            print(f"Канал найден: {chat.title}")
        except Exception as e:
            print(f"Ошибка: канал не найден - {e}")
            return

        await send_quiz()
        await app.stop()
        print('Отключено')

    except Exception as e:
        print(f'Ошибка: {e}')
        print(traceback.format_exc())


if __name__ == '__main__':
    asyncio.run(main())