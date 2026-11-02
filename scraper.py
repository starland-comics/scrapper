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

# ТОЛЬКО ТВОИ ЛИГИ
TARGET_LEAGUES = {
    47: "АПЛ",
    87: "Ла Лига",
    54: "Серия А",
    53: "Бундеслига",
    55: "Лига 1",
    42: "Лига Чемпионов",
    73: "Лига Европы",
    1509: "Лига Конференций",
    11935: "РПЛ",
    96: "ФНЛ",
    130: "MLS",
    11919: "Саудовская Аравия",
    88: "Чемпионшип",
    57: "Эредивизи",
    61: "Примейра",
    92: "Ла Лига 2",
    110: "ЧМ",
    111: "ЧЕ",
    112: "Лига Наций"
}

def get_fonbet_data_sync(url):
    try:
        r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

async def fetch_odds_and_score(event_id, sem):
    async with sem:
        url = f"{BASE_URL}/events/event?eventId={event_id}&scopeMarket=1600&lang=ru"
        data = await asyncio.to_thread(get_fonbet_data_sync, url)
        if not data: return None
        
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
        
        # Достаем счет и статус
        event_info = data.get("event", {})
        score1 = event_info.get("score1")
        score2 = event_info.get("score2")
        minute = event_info.get("time", "")
        place = event_info.get("place", "line")
        
        score_str = f"{score1} : {score2}" if score1 is not None and place == "live" else "VS"
        status_str = f"LIVE {minute}'" if place == "live" else "Скоро"
        
        return odds, score_str, status_str

async def main():
    print("🔄 [Scraper] Запуск...")
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if data and "events" in data:
        events = data.get("events", [])
        print(f"🔍 Всего событий: {len(events)}")

        now = time.time()
        valid_events = []
        
        for ev in events:
            if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2"):
                start = ev.get("startTime", 0)
                # Берем матчи на ближайшие 2 дня
                if start > now - 10800 and start < now + 172800: 
                    sport_id = ev.get("sportId")
                    # Фильтруем ТОЛЬКО по ID лиг
                    if sport_id in TARGET_LEAGUES:
                        ev['league_name'] = TARGET_LEAGUES[sport_id]
                        valid_events.append(ev)
        
        print(f"⚽ Матчей из списка: {len(valid_events)}")
        
        sem = asyncio.Semaphore(20)
        tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
        results = await asyncio.gather(*tasks)
        
        matches = {}
        for ev, res in zip(valid_events, results):
            if res:
                odds, score, status = res
                matches[f"fon_{ev['id']}"] = {
                    "title": f"{ev['team1']} - {ev['team2']}",
                    "home": ev['team1'], "away": ev['team2'],
                    "homeLogo": f"https://static.fon.bet/team_logos/{ev.get('team1Id')}.png",
                    "awayLogo": f"https://static.fon.bet/team_logos/{ev.get('team2Id')}.png",
                    "league": ev['league_name'], 
                    "status": status, "score": score,
                    "start_time": ev.get("startTime"), "odds": odds
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