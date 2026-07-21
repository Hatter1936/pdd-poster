import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")