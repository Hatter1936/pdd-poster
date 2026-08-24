import asyncio
import os
import sys
import random
import subprocess
from telethon import TelegramClient, types, functions
from telethon.errors import BroadcastPublicVotersForbiddenError, SessionPasswordNeededError, RPCError
from telethon.types import MessageEntitySpoiler
from telethon.sessions import StringSession
import traceback

try:
    from config import API_ID, API_HASH, CHANNEL_ID, SESSION_STRING
except ImportError as e:
    print(f"❌ Ошибка импорта config.py: {e}")
    sys.exit(1)

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("❌ Критическая ошибка: Неправильные данные в config.py")
    sys.exit(1)

from pdd_parser import PDDParser

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient('pdd_session', API_ID, API_HASH)


async def save_progress_to_github(parser):
    """Сохраняет прогресс в репозиторий через git"""
    try:
        token = os.environ.get('GITHUB_TOKEN')
        repo = os.environ.get('GITHUB_REPOSITORY')
        
        if not token or not repo:
            print("⚠️ GITHUB_TOKEN или GITHUB_REPOSITORY не найдены, пропускаю сохранение в репозиторий")
            return
        
        print("📤 Сохраняю прогресс в репозиторий...")
        remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], check=True, capture_output=True)
        subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions'], check=True, capture_output=True)
        subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions@github.com'], check=True, capture_output=True)
        subprocess.run(['git', 'add', 'progress.json'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Обновлён прогресс: билет {parser.current_ticket}, вопрос {parser.current_question}'], check=True, capture_output=True)
        subprocess.run(['git', 'push'], check=True, capture_output=True)
        print("✅ Прогресс сохранён в репозиторий")
    except Exception as e:
        print(f"⚠️ Не удалось сохранить прогресс в репозиторий: {e}")


async def send_quiz():
    parser = PDDParser()
    try:
        print("\n" + "="*60)
        print("📌 НАЧАЛО ОТПРАВКИ ПОСТА")
        print("="*60)
        
        ticket = parser.get_next_question()
        if not ticket:
            print("❌ Нет вопросов для публикации, господин")
            return False

        print(f"\n📝 Вопрос {ticket['number']} из билета {ticket['ticket']}")
        print(f"📄 Текст вопроса: {ticket['question'][:150]}...")
        print(f"📊 Количество ответов: {len(ticket['answers'])}")
        print(f"✅ Правильный ответ (индекс): {ticket['correct_index']}")
        print(f"🖼️ Картинка: {ticket.get('image_url', 'Нет')}")

        channel_entity = await client.get_entity(CHANNEL_ID)
        print(f"✅ Канал найден: {channel_entity.title}")

        if ticket.get('image_url'):
            image_url = ticket['image_url']
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://drom.ru' + image_url

            try:
                print(f"\n🖼️ Отправляю картинку: {image_url}")
                await client.send_file(channel_entity, file=image_url)
                print("✅ Картинка отправлена")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"⚠️ Не удалось отправить картинку: {e}")

        print("\n📊 Формирую викторину...")
        poll_answers = []
        MAX_ANSWER_LENGTH = 100

        for i, answer in enumerate(ticket['answers']):
            if len(answer) > MAX_ANSWER_LENGTH:
                answer = answer[:MAX_ANSWER_LENGTH - 3] + '...'
                print(f"   ✂️ Ответ {i+1} обрезан до {MAX_ANSWER_LENGTH} символов")
            
            numbered_answer = f"{i + 1}. {answer}"
            poll_answers.append(
                types.PollAnswer(
                    text=numbered_answer,
                    option=bytes([i])
                )
            )
            print(f"   Ответ {i+1}: {numbered_answer[:50]}... (длина: {len(numbered_answer)})")

        if len(ticket['question']) > 255:
            ticket['question'] = ticket['question'][:252] + '...'
            print(f"✂️ Вопрос обрезан до 255 символов")

        poll_id = random.randint(1, 999999999)
        poll = types.Poll(
            id=poll_id,
            question=ticket['question'],
            answers=poll_answers,
            public_voters=False,
            multiple_choice=False,
            quiz=True
        )

        print("\n📤 Отправляю викторину в канал...")
        try:
            poll_message = await client.send_message(
                channel_entity,
                file=types.InputMediaPoll(
                    poll=poll,
                    correct_answers=[bytes([ticket['correct_index']])],
                    solution="Ознакомьтесь с объяснением в комментариях.",
                    solution_entities=[]
                )
            )
            print(f"✅ Викторина отправлена! ID: {poll_message.id}")
        except RPCError as e:
            print(f"❌ Ошибка при отправке викторины: {e}")
            print("🔄 Переход к следующему вопросу...")
            parser.save_progress()
            await save_progress_to_github(parser)
            return await send_quiz()

        await asyncio.sleep(5)

        print("\n🔍 Ищу группу обсуждения...")
        full_channel = await client(functions.channels.GetFullChannelRequest(channel_entity))
        discussion_chat_id = full_channel.full_chat.linked_chat_id

        if not discussion_chat_id:
            print("⚠️ Группа обсуждения не найдена, отправляю объяснение в канал")
            explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
            await client.send_message(
                channel_entity,
                message=explanation_text,
                reply_to=poll_message.id
            )
            print("✅ Объяснение отправлено в канал")
            parser.save_progress()
            await save_progress_to_github(parser)
            return True

        discussion_entity = await client.get_entity(discussion_chat_id)
        print(f"✅ Группа обсуждения найдена: {discussion_entity.title}")

        print("\n🔍 Ищу копию опроса в группе обсуждения...")
        discussion_msg = None
        async for msg in client.iter_messages(discussion_entity, limit=30):
            if msg.fwd_from and msg.fwd_from.channel_post == poll_message.id:
                discussion_msg = msg
                print(f"✅ Найдена копия опроса! ID: {msg.id}")
                break

        if not discussion_msg:
            print("⚠️ Копия опроса не найдена в группе, отправляю в канал")
            explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
            await client.send_message(
                channel_entity,
                message=explanation_text,
                reply_to=poll_message.id
            )
            print("✅ Объяснение отправлено в канал")
            parser.save_progress()
            await save_progress_to_github(parser)
            return True

        print("\n📤 Отправляю объяснение в комментарии...")
        explanation_text = f"Правильный ответ: {ticket['correct_index'] + 1}\n{ticket['explanation']}"
        text_length = len(explanation_text)

        await client.send_message(
            discussion_entity,
            message=explanation_text,
            formatting_entities=[MessageEntitySpoiler(offset=0, length=text_length)],
            reply_to=discussion_msg.id
        )
        print("✅ Объяснение отправлено в комментарии под спойлером!")

        parser.save_progress()
        await save_progress_to_github(parser)
        print("✅ Прогресс сохранён")

        print("\n" + "="*60)
        print("🎉 ПОСТ УСПЕШНО ОТПРАВЛЕН!")
        print("="*60)
        return True

    except BroadcastPublicVotersForbiddenError:
        print("❌ Ошибка: Для каналов public_voters=False")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


async def main():
    try:
        print("\n" + "="*60)
        print("🚀 ЗАПУСК БОТА")
        print("="*60)
        
        print("\n🔌 Подключаюсь к Telegram...")
        
        if SESSION_STRING:
            print("   Использую строку сессии")
            await client.start()
        else:
            print("   Использую файл сессии (требуется ввод)")
            await client.start(
                phone=lambda: input("📱 Введите номер телефона (в формате +7...): "),
                code_callback=lambda: input("🔑 Введите код из Telegram: "),
                password=lambda: input("🔒 Введите пароль двухфакторной аутентификации: ")
            )

        print("✅ Подключено к Telegram!")

        me = await client.get_me()
        print(f"👤 Вы вошли как: {me.first_name} (@{me.username})")

        channel = await client.get_entity(CHANNEL_ID)
        print(f"📢 Канал найден: {channel.title}")

        await send_quiz()
        
        await client.disconnect()
        print("\n🔌 Отключено от Telegram")
        print("="*60)

    except SessionPasswordNeededError:
        print("🔒 Требуется пароль двухфакторной аутентификации")
        password = input("Введите пароль: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
