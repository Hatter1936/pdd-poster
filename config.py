import os

# Получаем переменные из окружения
API_ID = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # СТРОКА, не число!
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Преобразуем API_ID в число
try:
    API_ID = int(API_ID) if API_ID else 0
except ValueError:
    print(f"❌ Ошибка: API_ID должен быть числом, получено: {API_ID}")
    API_ID = 0

# CHANNEL_ID оставляем как строку - НЕ преобразуем в int!

# Проверка наличия переменных
print("📋 Проверка конфигурации:")
print(f"API_ID: {'✅' if API_ID else '❌'}")
print(f"API_HASH: {'✅' if API_HASH else '❌'}")
print(f"CHANNEL_ID: {'✅' if CHANNEL_ID else '❌'} (значение: {CHANNEL_ID})")
print(f"SESSION_STRING: {'✅' if SESSION_STRING else '❌'}")

if not API_ID or not API_HASH or not CHANNEL_ID:
    print("⚠️ ВНИМАНИЕ: Не все переменные окружения заданы корректно!")