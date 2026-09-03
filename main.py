import asyncio
import os
import sys
import random
import subprocess
import traceback
import json
from datetime import datetime
from telethon import TelegramClient, types, functions
from telethon.errors import BroadcastPublicVotersForbiddenError, SessionPasswordNeededError, RPCError, FloodWaitError
from telethon.types import MessageEntitySpoiler
from telethon.sessions import StringSession
from pdd_parser import PDDParser

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0)) if os.environ.get("CHANNEL_ID", "").lstrip('-').isdigit() else 0
SESSION_STRING = os.environ.get("SESSION_STRING", "")

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("ERROR: Missing API credentials")
    sys.exit(1)

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient('pdd_session', API_ID, API_HASH)

async def send_file_with_retry(entity, file_path, max_retries=2, delay=3):
    for attempt in range(max_retries):
        try:
            if file_path.startswith('http'):
                result = await client.send_file(entity, file=file_path, force_document=False)
            else:
                result = await client.send_file(entity, file=file_path)
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(delay)
    return None

async def save_progress_to_github():
    try:
        token = os.environ.get('GITHUB_TOKEN')
        repo = os.environ.get('GITHUB_REPOSITORY')
        if not token or not repo:
            return
        remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], check=True, capture_output=True)
        subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions'], check=True, capture_output=True)
        subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions@github.com'], check=True, capture_output=True)
        subprocess.run(['git', 'add', 'progress.json'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Progress update {datetime.now().isoformat()}'], check=True, capture_output=True)
        subprocess.run(['git', 'push'], check=True, capture_output=True)
    except Exception:
        pass

async def send_quiz():
    parser = PDDParser()
    max_attempts = 50
    
    for attempt in range(max_attempts):
        try:
            ticket = parser.get_next_question()
            if not ticket:
                print("No more questions available")
                return False

            channel_entity = await client.get_entity(CHANNEL_ID)

            if ticket.get('image_url'):
                image_url = ticket['image_url']
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://drom.ru' + image_url
                try:
                    await send_file_with_retry(channel_entity, image_url)
                    await asyncio.sleep(1)
                except Exception:
                    pass

            poll_answers = []
            for i, answer in enumerate(ticket['answers']):
                numbered_answer = f"{i + 1}. {answer}"
                if len(numbered_answer.encode('utf-8')) > 100:
                    numbered_answer = numbered_answer[:90] + '...'
                option = i.to_bytes(1, 'big') if i < 256 else b'\xff'
                poll_answers.append(
                    types.PollAnswer(
                        text=numbered_answer,
                        option=option
                    )
                )

            question_text = ticket['question']
            if len(question_text.encode('utf-8')) > 255:
                question_text = question_text[:250] + '...'

            poll_id = random.randint(1, 999999999)
            poll = types.Poll(
                id=poll_id,
                question=question_text,
                answers=poll_answers,
                public_voters=False,
                multiple_choice=False,
                quiz=True
            )

            correct_index = ticket['correct_index']
            if correct_index > 255:
                correct_bytes = b'\xff'
            else:
                correct_bytes = bytes([correct_index])

            try:
                poll_message = await client.send_message(
                    channel_entity,
                    file=types.InputMediaPoll(
                        poll=poll,
                        correct_answers=[correct_bytes],
                        solution="Explanation in comments",
                        solution_entities=[]
                    )
                )
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                continue
            except RPCError as e:
                print(f"RPC Error: {e}")
                parser.save_progress()
                await save_progress_to_github()
                continue

            await asyncio.sleep(2)

            try:
                full_channel = await client(functions.channels.GetFullChannelRequest(channel_entity))
                discussion_chat_id = full_channel.full_chat.linked_chat_id
            except Exception:
                discussion_chat_id = None

            explanation_text = f"Correct answer: {ticket['correct_index'] + 1}\n{ticket['explanation']}"

            if not discussion_chat_id:
                await client.send_message(
                    channel_entity,
                    message=explanation_text,
                    reply_to=poll_message.id
                )
                parser.save_progress()
                await save_progress_to_github()
                return True

            try:
                discussion_entity = await client.get_entity(discussion_chat_id)
                discussion_msg = None
                async for msg in client.iter_messages(discussion_entity, limit=100):
                    if msg.fwd_from and msg.fwd_from.channel_post == poll_message.id:
                        discussion_msg = msg
                        break

                if discussion_msg:
                    text_length = len(explanation_text)
                    await client.send_message(
                        discussion_entity,
                        message=explanation_text,
                        formatting_entities=[MessageEntitySpoiler(offset=0, length=text_length)],
                        reply_to=discussion_msg.id
                    )
                else:
                    await client.send_message(
                        channel_entity,
                        message=explanation_text,
                        reply_to=poll_message.id
                    )
            except Exception:
                await client.send_message(
                    channel_entity,
                    message=explanation_text,
                    reply_to=poll_message.id
                )

            parser.save_progress()
            await save_progress_to_github()
            return True

        except BroadcastPublicVotersForbiddenError:
            return False
        except Exception as e:
            print(f"Error in send_quiz attempt {attempt + 1}: {e}")
            traceback.print_exc()
            parser.save_progress()
            await save_progress_to_github()
            await asyncio.sleep(5)
            continue
    
    return False

async def main():
    try:
        if SESSION_STRING:
            await client.start()
        else:
            await client.start(
                phone=lambda: input("Enter phone number: "),
                code_callback=lambda: input("Enter code: "),
                password=lambda: input("Enter 2FA password: ")
            )

        success = await send_quiz()
        await client.disconnect()
        sys.exit(0 if success else 1)

    except SessionPasswordNeededError:
        password = input("Enter 2FA password: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
