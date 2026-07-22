import asyncio
from telethon.sessions import StringSession
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 35427169  # Ваш API_ID
API_HASH = "d8c13b9712a9ad0337db06ab41f3333a"  # Ваш API_HASH


async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)

    try:
        await client.start(
            phone=lambda: input("Введите номер телефона: "),
            code_callback=lambda: input("Введите код: "),
            password=lambda: input("Введите пароль 2FA: ")
        )
        print("SESSION_STRING:")
        print(client.session.save())
    except SessionPasswordNeededError:
        password = input("Введите пароль 2FA: ")
        await client.sign_in(password=password)
        print("SESSION_STRING:")
        print(client.session.save())
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())