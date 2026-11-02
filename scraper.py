import asyncio
import time
import httpx
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

# Белый список названий лиг (в нижнем регистре)
WHITELIST = [
    ("англия", "премьер-лига", "АПЛ"),
    ("россия", "премьер-лига", "РПЛ"),
    ("россия", "фнл", "ФНЛ"),
    ("испания", "ла лига", "Ла Лига"),
    ("испания", "сегунда", "Ла Лига 2"),
    ("италия", "серия а", "Серия А"),
    ("германия", "бундеслига", "Бундеслига"),
    ("франция", "лига 1", "Лига 1"),
    ("англия", "чемпионшип", "Чемпионшип"),
    ("саудовская", "", "Саудовская Аравия"),
    ("нидерланды", "эредивизи", "Эредивизи"),
    ("португалия", "примейра", "Примейра"),
    ("сша", "mls", "MLS"),
    ("лига чемпионов", "", "Лига Чемпионов"),
    ("лига европы", "", "Лига Европы"),
    ("лига конференций", "", "Лига Конференций"),
    ("чемпионат мира", "", "ЧМ"),
    ("чемпионат европы", "", "ЧЕ"),
    ("лига наций", "", "Лига Наций")
]

def get_fonbet_data_sync(url):
    try:
        r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def get_clean_league_name(raw_name):
    if not raw_name: return None
    name = raw_name.lower()
    # Жесткая отсечка мусора
    if any(x in name for x in ["женщины", "u21", "u19", "юнош", "молодеж", "бундеслига 3", "серия b", "серия c"]):
        return None

    for keys, _, clean_name in WHITELIST:
        if keys in name:
            return clean_name
    return None

async def fetch_event_details(event_id, sem):
    async with sem:
        url = f"{BASE_URL}/events/event?eventId={event_id}&scopeMarket=1600&lang=ru"
        data = await asyncio.to_thread(get_fonbet_data_sync, url)
        if not data: return None
        
        event_info = data.get("event", {})
        # Фонбет отдает название лиги в поле "competition" или "sport"
        raw_league = event_info.get("competition", "")
        if not raw_league: raw_league = event_info.get("sport", "")
        
        clean_name = get_clean_league_name(raw_league)
        if not clean_name: return None
        
        # Достаем кэфы
        odds = {"1": None, "X": None, "2": None}
        for cf in data.get("customFactors", []):
            for f in cf.get("factors", []):
                fid, v = f.get("f"), f.get("v")
                if fid == 921: odds["1"] = v
                elif fid == 922: odds["X"] = v
                elif fid == 923: odds["2"] = v
            if odds["1"] and odds["X"] and odds["2"]:
                break
        
        if not odds["1"]: return None
        
        score1 = event_info.get("score1")
        score2 = event_info.get("score2")
        minute = event_info.get("time", "")
        place = event_info.get("place", "line")
        
        score_str = f"{score1} : {score2}" if score1 is not None and place == "live" else "VS"
        status_str = f"LIVE {minute}'" if place == "live" else "Скоро"
        
        return {
            "league": clean_name,
            "odds": odds,
            "score": score_str,
            "status": status_str
        }

async def main():
    print("🔄 [Scraper] Запуск...")
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if data and "events" in data:
        events = data.get("events", [])
        print(f"🔍 Всего событий: {len(events)}")

        now = time.time()
        valid_events = []
        
        # Берем только футбол (kind=1) на ближайшие 2 дня
        for ev in events:
            if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2"):
                start = ev.get("startTime", 0)
                if start > now - 10800 and start < now + 172800: 
                    valid_events.append(ev)
        
        print(f"⚽ Футбольных матчей (2 дня): {len(valid_events)}")
        
        sem = asyncio.Semaphore(20)
        tasks = [fetch_event_details(ev["id"], sem) for ev in valid_events]
        results = await asyncio.gather(*tasks)
        
        matches = {}
        for ev, res in zip(valid_events, results):
            if res:
                matches[f"fon_{ev['id']}"] = {
                    "title": f"{ev['team1']} - {ev['team2']}",
                    "home": ev['team1'], "away": ev['team2'],
                    "homeLogo": f"https://static.fon.bet/team_logos/{ev.get('team1Id')}.png",
                    "awayLogo": f"https://static.fon.bet/team_logos/{ev.get('team2Id')}.png",
                    "league": res['league'], 
                    "status": res['status'], "score": res['score'],
                    "start_time": ev.get("startTime"), "odds": res['odds']
                }
        
        if matches:
            async with httpx.AsyncClient() as client:
                await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches)
            print(f"🔥 Успешно сохранено {len(matches)} матчей в Firebase!")
        else:
            print("⚠️ Кэфов не найдено.")
    else:
        print("⚠️ Не удалось получить список событий.")

if __name__ == "__main__":
    asyncio.run(main())