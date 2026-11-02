import requests
import json

url = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        # Выведем часть ответа, чтобы понять структуру
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    else:
        print("Не удалось. Ответ:", response.text[:300])
except Exception as e:
    print(f"Ошибка: {e}")