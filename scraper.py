import asyncio
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fon.bet/",
}

def get_data(url):
    r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
    if r.status_code == 200:
        return r.json()
    return None

async def main():
    data = await asyncio.to_thread(get_data, f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru")
    if not data: 
        print("Нет данных")
        return
    
    # Собираем карту лиг
    league_map = {}
    for t in data.get("tournamentInfos", []):
        if isinstance(t, dict) and t.get("id") and t.get("caption"):
            league_map[int(t["id"])] = t["caption"]
            
    print(f"Лиг в справочнике: {len(league_map)}")
    
    events = data.get("events", [])
    foot_events = [ev for ev in events if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2")]
    print(f"Футбольных событий: {len(foot_events)}")
    
    sids = set(ev.get("sportId") for ev in foot_events)
    print(f"Уникальных sportId: {len(sids)}")
    
    # Смотрим, какие sportId есть в league_map
    found = [sid for sid in sids if sid in league_map]
    print(f"Из них есть в league_map: {len(found)}")
    
    print("\nПримеры футбольных событий:")
    for ev in foot_events[:15]:
        sid = ev.get("sportId")
        lname = league_map.get(sid, "НЕТ В СПРАВОЧНИКЕ")
        print(f"  sportId={sid} | Лига: {lname} | {ev.get('team1')} - {ev.get('team2')}")

if __name__ == "__main__":
    asyncio.run(main())