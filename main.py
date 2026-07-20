import asyncio
import random
import traceback
import os
from telethon import TelegramClient, types, functions
from telethon.types import MessageEntitySpoiler
from telethon.errors import AuthRestartError, FloodWaitError
from pdd_parser import PDDParser

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', 0))

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("Ошибка: не заданы API_ID, API_HASH или CHANNEL_ID")
    exit(1)

client = TelegramClient('session_name', API_ID, API_HASH)
parser = PDDParser('progress.json')


async def send_quiz():
    try:
        ticket = parser.get_next_question()

        if not ticket:
            print("Не удалось получить вопрос")
            return False

        print(f"Вопрос {ticket['number']} из билета {ticket['ticket']}")
        print(f"Вопрос: {ticket['question'][:50]}...")

        channel_entity = await client.get_entity(CHANNEL_ID)

        if ticket.get('image_url'):
            try:
                await client.send_file(channel_entity, file=ticket['image_url'])
                print("Картинка отправлена")
            except Exception as e:
                print(f"Не удалось отправить картинку: {e}")

        answers_with_numbers = []
        for i, a in enumerate(ticket['answers']):
            answers_with_numbers.append(f"{i + 1}. {a}")

        answers_objects = []
        for i, a in enumerate(answers_with_numbers):
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
            public_voters=False,
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

        print('Публикую опрос-викторину...')
        poll_message = await client.send_message(channel_entity, file=poll_media)

        await asyncio.sleep(3)

        explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
        text_length = len(explanation_text.encode('utf-16-le')) // 2
        spoiler_entities = [MessageEntitySpoiler(offset=0, length=text_length)]

        try:
            full_channel = await client(functions.channels.GetFullChannelRequest(channel=channel_entity))
            discussion_chat_id = full_channel.full_chat.linked_chat_id

            if discussion_chat_id:
                discussion_entity = await client.get_entity(discussion_chat_id)

                discussion_msg = None
                print("Ищу копию поста в чате обсуждений...")
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
                    print("Объяснение отправила в комментарии под спойлером!")
                else:
                    await client.send_message(
                        channel_entity,
                        message=explanation_text,
                        formatting_entities=spoiler_entities,
                        reply_to=poll_message.id
                    )
                    print("Объяснение отправлено ответом в канал (копия в обсуждении не нашлась)")
            else:
                await client.send_message(
                    channel_entity,
                    message=explanation_text,
                    formatting_entities=spoiler_entities,
                    reply_to=poll_message.id
                )
                print("Объяснение отправила в канал (чат обсуждений не привязан к каналу)")
        except Exception as e:
            print(f"Не удалось отправить в комментарии: {e}")
            await client.send_message(
                channel_entity,
                message=explanation_text,
                formatting_entities=spoiler_entities,
                reply_to=poll_message.id
            )
            print("Объяснение отправлено ответом в канал из-за ошибки")

        print(f"Пост успешно отправила! (Билет {ticket['ticket']}, вопрос {ticket['number']})")
        return True

    except FloodWaitError as e:
        print(f"Подождите {e.seconds} секунд")
        await asyncio.sleep(e.seconds)
        return False
    except Exception as e:
        print(f'Ошибка во время выполнения send_quiz: {e}')
        print(traceback.format_exc())
        return False


async def main():
    try:
        print("Подключаюсь к тг")
        await client.start()
        print("Подключилась к тг")

        me = await client.get_me()
        print(f"Вы вошли как: {me.first_name} (@{me.username}), господин")

        await send_quiz()

        await client.disconnect()
        print('Отключено')

    except AuthRestartError:
        print('Ошибка авторизации. Попробуй еще раз.')
    except Exception as e:
        print(f'Ошибка в функции main: {e}')
        print(traceback.format_exc())


if __name__ == '__main__':
    asyncio.run(main())