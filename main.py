import asyncio
import random
import traceback
import os
import json
import base64
import requests
from telethon import TelegramClient, types, functions
from telethon.sessions import StringSession  # ИСПРАВЛЕНО: Добавлен импорт для работы со строкой сессии
from telethon.types import MessageEntitySpoiler
from telethon.errors import AuthRestartError

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

# ИСПРАВЛЕНО: Правильная инициализация клиента Telethon через StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

from pdd_parser import PDDParser

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

        # ИСПРАВЛЕНО: Корректный URL для обращения к API GitHub
        url = f"https://github.com{repo}/contents/progress.json"

        headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Telethon-PDD-Bot'
        }

        sha = ''
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                sha = resp.json().get('sha', '')
        except:
            sha = ''

        payload = {
            'message': f'Обновление прогресса: билет {data["current_ticket"]}, вопрос {data["current_question"]}',
            'content': encoded,
            'sha': sha if sha else None
        }

        if not sha:
            payload.pop('sha', None)

        response = requests.put(url, json=payload, headers=headers)

        # ИСПРАВЛЕНО: Правильная логическая проверка статус-кодов (200 или 201)
        if response.status_code == 200 or 201:
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

        channel_entity = await client.get_entity(CHANNEL_ID)

        # 1. Отдельно отправляем изображение билета
        if ticket.get('image_url'):
            try:
                await client.send_file(channel_entity, file=ticket['image_url'])
                print("Картинка отправлена")
            except Exception as e:
                print(f"Не удалось отправить картинку: {e}")

        # 2. Формируем варианты ответов опроса
        options = [f"{i + 1}. {a}" for i, a in enumerate(ticket['answers'])]
        answers_objects = []
        for i, a in enumerate(options):
            answers_objects.append(
                types.PollAnswer(
                    text=types.TextWithEntities(text=a, entities=[]),
                    option=str(i).encode('utf-8')
                )
            )

        # 3. Собираем сам объект Poll (public_voters=False ГАРАНТИРУЕТ анонимность)
        poll_id = random.randint(1111111111111111, 9999999999999999)
        poll_object = types.Poll(
            id=poll_id,
            hash=poll_id,
            question=types.TextWithEntities(text=ticket['question'], entities=[]),
            answers=answers_objects,
            closed=False,
            public_voters=False,  # Только анонимные викторины разрешены в каналах!
            multiple_choice=False,
            quiz=True,
            countries_iso2=[]
        )

        poll_media = types.InputMediaPoll(
            poll=poll_object,
            correct_answers=[int(ticket['correct_index'])],
            solution='Ознакомьтесь с объяснением в комментариях.',
            solution_entities=[]
        )

        # 4. Публикуем нативный опрос-викторину в канал
        print('Публикуем опрос-викторину...')
        poll_message = await client.send_message(channel_entity, file=poll_media)
        print("Опрос отправлен")

        # Даем Telegram время переслать пост в чат обсуждений
        await asyncio.sleep(4)

        # 5. Текст объяснения (в одну строчку без \n)
        explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1} — {ticket['explanation']}"
        text_length = len(explanation_text.encode('utf-16-le')) // 2
        spoiler_entities = [MessageEntitySpoiler(offset=0, length=text_length)]

        try:
            full_channel = await client(functions.channels.GetFullChannelRequest(channel=channel_entity))
            discussion_chat_id = full_channel.full_chat.linked_chat_id

            if discussion_chat_id:
                discussion_entity = await client.get_entity(discussion_chat_id)
                discussion_msg = None

                async for msg in client.iter_messages(discussion_entity, limit=15):
                    if msg.fwd_from and msg.fwd_from.channel_post == poll_message.id:
                        discussion_msg = msg
                        break

                if discussion_msg:
                    await client.send_message(
                        discussion_entity,
                        message=explanation_text,
                        formatting_entities=spoiler_entities,
                        reply_to=discussion_msg.id
                    )
                    print("Объяснение отправлено в комментарии под спойлером!")
                else:
                    await client.send_message(channel_entity, message=explanation_text,
                                              formatting_entities=spoiler_entities, reply_to=poll_message.id)
                    print("Объяснение отправлено в канал (не нашли пост в чате)")
            else:
                await client.send_message(channel_entity, message=explanation_text,
                                          formatting_entities=spoiler_entities, reply_to=poll_message.id)
                print("Объяснение отправлено в канал (чат обсуждений не привязан)")
        except Exception as e:
            print(f"Ошибка отправки комментария: {e}")
            await client.send_message(channel_entity, message=explanation_text, formatting_entities=spoiler_entities,
                                      reply_to=poll_message.id)

        # 6. Сохранение прогресса
        parser.save_progress()
        save_progress_to_github()
        return True
    except Exception as e:
        print(f'Ошибка во время выполнения send_quiz: {e}')
        print(traceback.format_exc())
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")
        await client.connect()
        print("Подключено!")
        await send_quiz()
        await client.disconnect()
        print('Отключено')
    except AuthRestartError:
        print('Ошибка авторизации. Попробуй еще раз.')
    except Exception as e:
        print(f'Ошибка в функции main: {e}')


if __name__ == '__main__':
    asyncio.run(main())
