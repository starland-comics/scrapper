import requests
import json

url = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        found = False
        
        for sport_data in data:
            sport = sport_data.get("payload", {}).get("sport", {})
            
            # Ищем футбол (обычно id = "1" или name = "Футбол")
            if sport.get("id") == "1" or sport.get("name") == "Футбол":
                print("✅ НАЙДЕН ФУТБОЛ!")
                comps = sport_data.get("payload", {}).get("competitionsWithEvents", [])
                
                if comps:
                    # Берем первый турнир и первый матч
                    first_event = comps[0]["events"][0]
                    print("📋 СТРУКТУРА ФУТБОЛЬНОГО МАТЧА:")
                    print(json.dumps(first_event, indent=2, ensure_ascii=False))
                    found = True
                    break
        
        if not found:
            print("⚠️ В лайве сейчас нет футбола. Попробуй посмотреть линию (не лайв).")
            
    else:
        print(f"Ошибка: {response.status_code}")
except Exception as e:
    print(f"Ошибка: {e}")