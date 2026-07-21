import asyncio
import random
import traceback
import os
import json
import base64
import requests
from pyrogram import Client
from pdd_parser import PDDParser

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '')
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


def save_progress_to_github():
    try:
        token = os.environ.get('GITHUB_TOKEN', '')
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        if not token or not repo:
            return
        with open('progress.json', 'r') as f:
            data = json.load(f)
        content = json.dumps(data, indent=4)
        encoded = base64.b64encode(content.encode()).decode()
        url = f"https://api.github.com/repos/{repo}/contents/progress.json"
        headers = {'Authorization': f'token {token}', 'Content-Type': 'application/json'}
        try:
            resp = requests.get(url, headers=headers)
            sha = resp.json().get('sha', '') if resp.status_code == 200 else ''
        except:
            sha = ''
        payload = {
            'message': f'Обновление прогресса: билет {data["current_ticket"]}, вопрос {data["current_question"]}',
            'content': encoded,
            'sha': sha
        }
        response = requests.put(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print("Прогресс сохранён в репозиторий")
        else:
            print(f"Ошибка сохранения: {response.status_code}")
    except Exception as e:
        print(f"Ошибка сохранения в репозиторий: {e}")


async def send_quiz():
    try:
        ticket = parser.get_next_question()
        if not ticket:
            print("Не удалось получить вопрос")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")

        channel_chat = await app.get_chat(CHANNEL_ID)
        discussion_chat_id = channel_chat.linked_chat.id if channel_chat.linked_chat else None

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
            correct_option_id=int(ticket['correct_index']),
            explanation="Ознакомьтесь с объяснением в комментариях.",
            is_anonymous=True
        )
        print("Викторина отправлена")

        await asyncio.sleep(4)

        explanation_text = f"||Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}||"

        if discussion_chat_id:
            print("Ищем копию опроса в чате обсуждений...")
            discussion_msg = None
            async for message in app.get_chat_history(discussion_chat_id, limit=15):
                if message.forward_from_chat and message.forward_from_chat.id == channel_chat.id:
                    if message.forward_from_message_id == poll_message.id:
                        discussion_msg = message
                        break

            if discussion_msg:
                await app.send_message(
                    chat_id=discussion_chat_id,
                    text=explanation_text,
                    reply_to_message_id=discussion_msg.id
                )
                print("Объяснение отправлено в комментарии под спойлером!")
            else:
                await app.send_message(CHANNEL_ID, explanation_text, reply_to_message_id=poll_message.id)
                print("Объяснение отправлено ответом в канал")
        else:
            await app.send_message(CHANNEL_ID, explanation_text, reply_to_message_id=poll_message.id)
            print("Объяснение отправлено ответом в канал")

        parser.save_progress()
        save_progress_to_github()

        with open('progress.json', 'r') as f:
            data = json.load(f)
        print(f"Прогресс сохранён: билет {data['current_ticket']}, вопрос {data['current_question']}")
        print(f"Пост отправлен! Билет {ticket['ticket']}, вопрос {ticket['number']}")
        return True

    except Exception as e:
        print(f'Ошибка: {e}')
        print(traceback.format_exc())
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")
        await app.start()
        print("Подключено!")

        me = await app.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username})")

        chat = await app.get_chat(CHANNEL_ID)
        print(f"Канал найден: {chat.title}")

        await send_quiz()

        try:
            await app.stop()
        except:
            pass
        print('Отключено')

    except Exception as e:
        print(f'Ошибка: {e}')
        print(traceback.format_exc())


if __name__ == '__main__':
    asyncio.run(main())