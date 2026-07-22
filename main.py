import asyncio
import os
import sys
import random
from telethon import TelegramClient, types, functions
from telethon.errors import BroadcastPublicVotersForbiddenError, SessionPasswordNeededError
from telethon.types import MessageEntitySpoiler
from telethon.sessions import StringSession

try:
    from config import API_ID, API_HASH, CHANNEL_ID, SESSION_STRING
except ImportError as e:
    print(f"Ошибка импорта config.py: {e}")
    sys.exit(1)

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("Критическая ошибка: Неправильные данные в config.py")
    sys.exit(1)

from pdd_parser import PDDParser

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient('pdd_session', API_ID, API_HASH)


async def send_quiz():
    parser = PDDParser()
    try:
        ticket = parser.get_next_question()
        if not ticket:
            print("Нет вопросов для публикации, господин")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")
        channel_entity = await client.get_entity(CHANNEL_ID)
        print(f"Канал найден: {channel_entity.title}")

        if ticket.get('image_url'):
            image_url = ticket['image_url']
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://drom.ru' + image_url

            try:
                print(f"Отправляю картинку: {image_url}")
                await client.send_file(channel_entity, file=image_url)
                print("Картинка отправлена")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Не удалось отправить картинку: {e}")

        print("Отправляю викторину...")

        poll_answers = []
        for i, answer in enumerate(ticket['answers']):
            numbered_answer = f"{i + 1}. {answer}"
            poll_answers.append(
                types.PollAnswer(
                    text=numbered_answer,
                    option=bytes([i])
                )
            )

        # Пробуем с hash
        try:
            poll = types.Poll(
                id=random.randint(1, 999999999),
                hash=random.randint(1, 999999999),
                question=ticket['question'],
                answers=poll_answers,
                public_voters=False,
                multiple_choice=False,
                quiz=True
            )
            print("Использую hash")
        except:
            poll = types.Poll(
                id=random.randint(1, 999999999),
                question=ticket['question'],
                answers=poll_answers,
                public_voters=False,
                multiple_choice=False,
                quiz=True
            )
            print("Использую без hash")

        poll_message = await client.send_message(
            channel_entity,
            file=types.InputMediaPoll(
                poll=poll,
                correct_answers=[bytes([ticket['correct_index']])],
                solution="Ознакомьтесь с объяснением в комментариях.",
                solution_entities=[]
            )
        )

        print(f"Викторина отправлена, господин! ID: {poll_message.id}")
        await asyncio.sleep(5)

        full_channel = await client(functions.channels.GetFullChannelRequest(channel_entity))
        discussion_chat_id = full_channel.full_chat.linked_chat_id

        if not discussion_chat_id:
            print("Группа обсуждения не найдена")
            return False

        discussion_entity = await client.get_entity(discussion_chat_id)

        discussion_msg = None
        async for msg in client.iter_messages(discussion_entity, limit=30):
            if msg.fwd_from and msg.fwd_from.channel_post == poll_message.id:
                discussion_msg = msg
                break

        if not discussion_msg:
            print("Копия опроса не найдена в группе")
            return False

        explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
        text_length = len(explanation_text)

        await client.send_message(
            discussion_entity,
            message=explanation_text,
            formatting_entities=[MessageEntitySpoiler(offset=0, length=text_length)],
            reply_to=discussion_msg.id
        )

        print("Объяснение отправлено в комментарии под спойлером, господин")
        return True

    except BroadcastPublicVotersForbiddenError:
        print("Ошибка: Для каналов public_voters=False")
        return False
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    try:
        print("Подключаюсь к Telegram...")

        if SESSION_STRING:
            await client.start()
        else:
            await client.start(
                phone=lambda: input("Введите номер телефона (в формате +7...): "),
                code_callback=lambda: input("Введите код из Telegram: "),
                password=lambda: input("Введите пароль двухфакторной аутентификации: ")
            )

        print("Подключено, господин")

        me = await client.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username})")

        channel = await client.get_entity(CHANNEL_ID)
        print(f"Канал найден: {channel.title}")

        await send_quiz()
        await client.disconnect()
        print("Отключено, господин")

    except SessionPasswordNeededError:
        print("Требуется пароль двухфакторной аутентификации")
        password = input("Введите пароль: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())