import asyncio
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

def get_data(url):
    r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
    if r.status_code == 200:
        return r.json()
    return None

async def main():
    print("🔍 ДИАГНОСТИКА Fonbet...")
    data = await asyncio.to_thread(get_data, f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru")
    
    if not data:
        print("❌ Не удалось получить данные")
        return
    
    # 1. Смотрим tournamentInfos
    ti = data.get("tournamentInfos", [])
    print(f"\n=== tournamentInfos (тип: {type(ti).__name__}, элементов: {len(ti) if hasattr(ti, '__len__') else '?'}) ===")
    if isinstance(ti, list) and ti:
        print("Первый элемент:")
        print(json.dumps(ti[0], ensure_ascii=False, indent=2)[:800])
    
    # 2. Смотрим sports
    sp = data.get("sports", [])
    print(f"\n=== sports (тип: {type(sp).__name__}, элементов: {len(sp) if hasattr(sp, '__len__') else '?'}) ===")
    if isinstance(sp, list) and sp:
        print("Первый элемент (sports[0]):")
        print(json.dumps(sp[0], ensure_ascii=False, indent=2)[:1500])
    
    # 3. Ищем первое событие и смотрим что у него в sportId
    events = data.get("events", [])
    print(f"\n=== events (элементов: {len(events)}) ===")
    if events:
        first_ev = events[0]
        print(f"Пример события: id={first_ev.get('id')}, sportId={first_ev.get('sportId')}, kind={first_ev.get('kind')}")
        print(f"team1={first_ev.get('team1')}, team2={first_ev.get('team2')}")
        
        # Найдем sportId для футбольного события
        for ev in events[:50]:
            if ev.get("kind") == 1:
                print(f"\nПервое футбольное событие: sportId={ev.get('sportId')}")
                print(f"   {ev.get('team1')} - {ev.get('team2')}")
                break

if __name__ == "__main__":
    asyncio.run(main())