import asyncio
import random
import traceback
import os
import json
import base64
import requests
from pyrogram import Client
from pyrogram.enums import PollType
from pyrogram.raw import types, functions  # Добавлен functions для прямого invoke
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

        url = f"https://github.com{repo}/contents/progress.json"
        headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Pyrogram-PDD-Bot'
        }

        sha = ''
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                sha = resp.json().get('sha', '')
        except Exception as e:
            print(f"Не удалось получить SHA файла (возможно, он создается впервые): {e}")
            sha = ''

        payload = {
            'message': f'Обновление прогресса: билет {data["current_ticket"]}, вопрос {data["current_question"]}',
            'content': encoded,
            'sha': sha if sha else None
        }

        if not sha:
            payload.pop('sha', None)

        response = requests.put(url, json=payload, headers=headers)

        if response.status_code:
            print("Прогресс сохранён в репозиторий GitHub")
        else:
            print(f"Ошибка сохранения на GitHub: {response.status_code} -> {response.text}")

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

        # 1. Отдельно отправляем картинку
        if ticket.get('image_url'):
            try:
                await app.send_photo(CHANNEL_ID, ticket['image_url'])
                print("Картинка отправлена")
            except Exception as e:
                print(f"Не удалось отправить картинку: {e}")

        # 2. ПРЯМАЯ ОТПРАВКА НА СЕРВЕРА TELEGRAM ЧЕРЕЗ INVOKE (Полный обход багов любых библиотек)
        options = [f"{i + 1}. {a}" for i, a in enumerate(ticket['answers'])]

        answers_objects = []
        for i, a in enumerate(options):
            answers_objects.append(
                types.PollAnswer(
                    text=types.TextWithEntities(text=a, entities=[]),
                    option=str(i).encode('utf-8')
                )
            )

        poll_id = random.randint(1111111111111111, 9999999999999999)

        poll_object = types.Poll(
            id=poll_id,
            hash=poll_id,
            question=types.TextWithEntities(text=ticket['question'], entities=[]),
            answers=answers_objects,
            closed=False,
            public_voters=False,  # КРИТИЧЕСКИ ВАЖНО: Анонимное голосование, разрешенное в каналах
            multiple_choice=False,
            quiz=True,  # Режим викторины
            countries_iso2=[]
        )

        poll_media = types.InputMediaPoll(
            poll=poll_object,
            correct_answers=[int(ticket['correct_index'])],
            solution='Ознакомьтесь с объяснением в комментариях.',
            solution_entities=[]
        )

        print("Отправляем викторину напрямую через invoke(messages.SendMedia)...")
        # Получаем чистый объект назначения для raw-запроса
        peer = await app.resolve_peer(CHANNEL_ID)

        # Вызываем нативный метод Telegram API
        raw_result = await app.invoke(
            functions.messages.SendMedia(
                peer=peer,
                media=poll_media,
                message="",
                random_id=random.randint(11111111, 99999999)
            )
        )

        # Достаем ID созданного сообщения из логов ответа Telegram
        if hasattr(raw_result, "updates"):
            poll_message_id = next((u.id for u in raw_result.updates if hasattr(u, "id")), None)
        elif hasattr(raw_result, "id"):
            poll_message_id = raw_result.id
        else:
            poll_message_id = None

        print(f"Викторина успешно отправлена! ID сообщения: {poll_message_id}")

        await asyncio.sleep(4)

        explanation_text = f"||Правильный ответ: {ticket['correct_index'] + 1} — {ticket['explanation']}||"

        # 3. Отправка объяснения в комментарии
        if discussion_chat_id and poll_message_id:
            print("Ищем копию опроса в чате обсуждений...")
            discussion_msg = None
            async for message in app.get_chat_history(discussion_chat_id, limit=15):
                if message.forward_from_chat and message.forward_from_chat.id == channel_chat.id:
                    if message.forward_from_message_id == poll_message_id:
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
                await app.send_message(CHANNEL_ID, explanation_text, reply_to_message_id=poll_message_id)
                print("Объяснение отправлено ответом в канал (не нашли в обсуждениях)")
        else:
            # На случай если чат не привязан или не удалось вытянуть ID сообщения
            target_reply_id = poll_message_id if poll_message_id else None
            await app.send_message(CHANNEL_ID, explanation_text, reply_to_message_id=target_reply_id)
            print("Объяснение отправлено ответом в канал")

        # 4. Сохранение прогресса
        parser.save_progress()
        save_progress_to_github()

        with open('progress.json', 'r') as f:
            data = json.load(f)

        print(f"Прогресс сохранён локально: билет {data['current_ticket']}, вопрос {data['current_question']}")
        print(f"Пост отправлен! Билет {ticket['ticket']}, вопрос {ticket['number']}")
        return True

    except Exception as e:
        print(f'Ошибка во время выполнения send_quiz: {e}')
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
        print(f'Ошибка в функции main: {e}')
        print(traceback.format_exc())


if __name__ == '__main__':
    asyncio.run(main())
