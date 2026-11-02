import requests
import json
import time

OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/sports-with-competitions-with-events"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

r = requests.get(OLIMP_LINE_URL, headers=HEADERS, timeout=15)
print(f"Статус: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print(f"Количество групп (видов спорта): {len(data)}\n")
    
    for group in data:
        payload = group.get("payload", {})
        sport = payload.get("sport", {})
        sport_id = sport.get("id")
        sport_name = sport.get("name")
        event_count = sport.get("eventCount", 0)
        
        print(f"Sport ID: {sport_id} | {sport_name} | Матчей: {event_count}")
        
        # Если это футбол — выводим список турниров
        if sport_id == "1" or sport_name == "Футбол":
            comps = payload.get("competitionsWithEvents", [])
            print(f"   ➡️ Турниров в линии: {len(comps)}")
            for comp in comps[:10]:
                comp_info = comp.get("competition", {})
                events = comp.get("events", [])
                print(f"      - {comp_info.get('name')} | Матчей: {len(events)}")
                if events:
                    ev = events[0]
                    print(f"        Пример: {ev.get('team1Name')} - {ev.get('team2Name')}")
            print()