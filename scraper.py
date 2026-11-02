import requests
import json

# Открытый эндпоинт 1xBet (может потребоваться актуальное зеркало)
url = "https://1xbet.com/LineFeed/GetSportsShortZip?lng=ru&tz=3&country=1&partner=51&gr=70"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Ищем команды и их логотипы
        # Структура может меняться, но обычно команды лежат в объектах с ключами "O1", "O2" или "T1", "T2"
        # Ищем поля со словом "logo" или "image"
        
        # Просто выведем первые 500 символов, чтобы понять структуру
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
    else:
        print(f"Ошибка: {response.status_code}")
except Exception as e:
    print(f"Ошибка запроса: {e}")