import asyncio
import random
import traceback
import os
from telethon import TelegramClient, types, functions
from telethon.errors import AuthRestartError
from config import API_ID, API_HASH, CHANNEL_ID

# Инициализируем клиента юзербота
client = TelegramClient('session_name', API_ID, API_HASH)


def get_ticket():
    """
    Данные вашего билета ПДД.
    """
    return {
        'question': 'По какой траектории Вам разрешается выполнить поворот налево?',
        'answers': ['1. Только по А', '2. Только по Б', '3. По любой из указанных'],
        'correct_index': 1,  # Индекс правильного ответа (0 - первый, 1 - второй)
        'explanation': 'При повороте налево на данном перекрестке вы можете выбрать любую траекторию.',
        'image_url': r'C:\Users\User\Pictures\347653751514314.jpg'  # Ваш локальный путь к картинке
    }


async def send_quiz():
    try:
        ticket = get_ticket()
        print('Формируем пост-викторину...')

        # Получаем структуру канала
        channel_entity = await client.get_entity(CHANNEL_ID)

        # 1. ОТПРАВЛЯЕМ ИЗОБРАЖЕНИЕ БИЛЕТА
        if ticket.get('image_url') and os.path.exists(ticket['image_url']):
            print('Отправляем изображение билета...')
            await client.send_file(channel_entity, file=ticket['image_url'])
        else:
            print('Предупреждение: Локальный файл картинки не найден, отправляем только опрос.')

        # 2. СОБИРАЕМ ВАРИАНТЫ ОТВЕТОВ ОПРОСА
        answers_objects = []
        for i, a in enumerate(ticket['answers']):
            answers_objects.append(
                types.PollAnswer(
                    text=types.TextWithEntities(text=a, entities=[]),
                    option=str(i).encode('utf-8')
                )
            )

        # 3. СОБИРАЕМ ОБЪЕКТ POLL (СТРОГО ПО СХЕМЕ TELETHON)
        poll_object = types.Poll(
            id=random.randint(1111111111111111, 9999999999999999),
            hash=random.randint(1111111111111111, 9999999999999999),
            question=types.TextWithEntities(text=ticket['question'], entities=[]),
            answers=answers_objects,
            closed=False,
            public_voters=False,
            multiple_choice=False,
            quiz=True,
            countries_iso2=[]
        )

        # 4. ФОРМИРУЕМ МЕДИА-ПАКЕТ КВИЗА (ИНСТРУКЦИЯ ВНУТРИ ЛАМПОЧКИ)
        poll_media = types.InputMediaPoll(
            poll=poll_object,
            correct_answers=[int(ticket['correct_index'])],
            solution='Ознакомьтесь с объяснением в комментариях.',
            solution_entities=[]
        )

        # 5. ПУБЛИКУЕМ НАТИВНЫЙ ОПРОС-ВИКТОРНУ В КАНАЛ
        print('Публикуем нативный опрос-викторину...')
        poll_message = await client.send_message(channel_entity, file=poll_media)

        # 6.ОТПРАВКА ОБЪЯСНЕНИЯ ПОД СПОЙЛЕРОМ В КОММЕНТАРИИ
        print('Ожидаем синхронизации с чатом обсуждений...')
        await asyncio.sleep(4)  # Даем Telegram время переслать пост в связанный чат

        # Запрашиваем ID связанного чата комментариев
        full_channel = await client(functions.channels.GetFullChannelRequest(channel=channel_entity))
        discussion_chat_id = full_channel.full_chat.linked_chat_id

        if discussion_chat_id:
            discussion_entity = await client.get_entity(discussion_chat_id)

            # Ищем автоматическую копию нашего опроса внутри чата комментариев
            print('Ищем пост в группе обсуждения...')
            discussion_msg = None
            async for msg in client.iter_messages(discussion_entity, limit=15):
                if msg.fwd_from and msg.fwd_from.channel_post == poll_message.id:
                    discussion_msg = msg
                    break

            # Если копия найдена, пишем ответ на нее, что создает комментарий под постом
            if discussion_msg:
                print('Отправляем объяснение под спойлером в комментарии...')
                spoiler_text = f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>"
                await client.send_message(
                    discussion_entity,
                    message=spoiler_text,
                    reply_to=discussion_msg.id,
                    parse_mode='html'  # HTML-режим активирует тег спойлера
                )
                print("Успех: Объяснение отправлено в комментарии под спойлером!")
            else:
                print("Предупреждение: Не нашли пост в обсуждении. Шлем обычным ответом в ленту.")
                await client.send_message(channel_entity, f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>",
                                          reply_to=poll_message.id, parse_mode='html')
        else:
            print("Ошибка: К каналу не привязана группа обсуждения (комментарии выключены в настройках).")
            await client.send_message(channel_entity, f"<tg-spoiler>{ticket['explanation']}</tg-spoiler>",
                                      reply_to=poll_message.id, parse_mode='html')

        return True

    except Exception as e:
        print(f'Ошибка во время выполнения send_quiz: {e}')
        print(traceback.format_exc())
        return False


async def main():
    try:
        print("Подключаемся к Telegram...")
        await client.start(
            phone=lambda: input("Введите номер телефона (в формате +7...): "),
            code_callback=lambda: input("Введите код из Telegram: "),
            password=lambda: input("Введите пароль двухэтапной аутентификации (если есть): ")
        )
        print("Подключено к Telegram")

        me = await client.get_me()
        print(f"Вход выполнен как: {me.first_name} (@{me.username})")

        await send_quiz()
        await client.disconnect()
        print('Сессия закрыта. Отключено.')

    except AuthRestartError:
        print('Ошибка авторизации. Попробуйте еще раз.')
    except Exception as e:
        print(f'Ошибка в функции main: {e}')


if __name__ == '__main__':
    asyncio.run(main())
