import requests
import json

# Эндпоинт для линии (прематч), судя по документации - с /line/top/
url = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events?vids%5B%5D="
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        found = False
        
        for sport_data in data:
            sport = sport_data.get("payload", {}).get("sport", {})
            
            # Ищем футбол (ID "1" или название "Футбол")
            if sport.get("id") == "1" or sport.get("name") == "Футбол":
                print("✅ НАЙДЕН ФУТБОЛ В ЛИНИИ!")
                comps = sport_data.get("payload", {}).get("competitionsWithEvents", [])
                
                if comps:
                    # Берем первый турнир и первый матч для примера
                    first_event = comps[0]["events"][0]
                    print("\n📋 СТРУКТУРА МАТЧА (ЛОГОТИПЫ + КОЭФФИЦИЕНТЫ):")
                    print(json.dumps(first_event, indent=2, ensure_ascii=False))
                    found = True
                    break
        
        if not found:
            print("⚠️ Футбол не найден в линии. Возможно, нужно передать другой параметр vids.")
            
    else:
        print("Ответ сервера:", response.text[:500])
        
except Exception as e:
    print(f"Ошибка: {e}")