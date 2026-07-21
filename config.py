import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
SESSION_STRING = os.environ.get("SESSION_STRING", "")

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("⚠️ ВНИМАНИЕ: Не все переменные окружения заданы!")
    print(f"API_ID: {'✅' if API_ID else '❌'}")
    print(f"API_HASH: {'✅' if API_HASH else '❌'}")
    print(f"CHANNEL_ID: {'✅' if CHANNEL_ID else '❌'}")
    print(f"SESSION_STRING: {'✅' if SESSION_STRING else '❌'}")