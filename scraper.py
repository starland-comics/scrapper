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

def get_fonbet_data_sync(url):
    try:
        r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️ Ошибка запроса: {e}")
    return None

async def fetch_odds_and_score(event_id, sem):
    async with sem:
        url = f"{BASE_URL}/events/event?eventId={event_id}&scopeMarket=1600&lang=ru"
        data = await asyncio.to_thread(get_fonbet_data_sync, url)
        if not data: return None
        
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
        
        event_info = data.get("event", {})
        score1 = event_info.get("score1")
        score2 = event_info.get("score2")
        minute = event_info.get("time", "")
        place = event_info.get("place", "line")
        
        score_str = f"{score1} : {score2}" if score1 is not None and place == "live" else "VS"
        status_str = f"LIVE {minute}'" if place == "live" else "Скоро"
        
        return odds, score_str, status_str

def extract_leagues(data):
    """Умный парсер лиг (поддерживает и списки, и словари)."""
    leagues = {}
    
    # 1. Пытаемся достать из tournamentInfos
    infos = data.get("tournamentInfos", [])
    if isinstance(infos, dict): infos = infos.values()
    for t in infos:
        if isinstance(t, dict):
            t_id = t.get("id")
            t_name = t.get("name") or t.get("rusName")
            if t_id and t_name:
                leagues[t_id] = t_name

    # 2. Пытаемся достать из sports -> regions -> competitions
    sports = data.get("sports", [])
    if isinstance(sports, dict): sports = sports.values()
    for s in sports:
        if not isinstance(s, dict): continue
        # kind=1 это футбол
        if s.get("kind") == 1 or s.get("name") == "Футбол":
            regions = s.get("regions", [])
            if isinstance(regions, dict): regions = regions.values()
            for r in regions:
                if not isinstance(r, dict): continue
                comps = r.get("competitions", [])
                if isinstance(comps, dict): comps = comps.values()
                for c in comps:
                    if not isinstance(c, dict): continue
                    c_id = c.get("id")
                    c_name = c.get("name") or c.get("rusName")
                    if c_id and c_name:
                        leagues[c_id] = c_name
    return leagues

async def main():
    print("🔄 [Scraper] Запуск...")
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if data and "events" in data:
        events = data.get("events", [])
        print(f"🔍 Всего событий: {len(events)}")
        
        # Загружаем лиги динамически
        leagues_map = extract_leagues(data)
        print(f"✅ Загружено названий лиг: {len(leagues_map)}")

        now = time.time()
        valid_events = []
        for ev in events:
            # kind == 1 — это футбол (жесткий фильтр, отсекает регби и т.д.)
            if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2"):
                if ev.get("startTime", 0) > now - 10800:
                    valid_events.append(ev)
        
        print(f"⚽ Футбольных матчей: {len(valid_events)}")
        
        if not valid_events:
            print("⚠️ Футбольные матчи не найдены. Проверь фильтр kind.")
        
        sem = asyncio.Semaphore(20)
        tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
        results = await asyncio.gather(*tasks)
        
        matches = {}
        for ev, res in zip(valid_events, results):
            if res:
                odds, score, status = res
                league_id = int(ev.get("sportId", 0))
                # Если лигу не нашли — пишем "Футбол", но матч оставляем!
                league_name = leagues_map.get(league_id, "Футбол")
                
                matches[f"fon_{ev['id']}"] = {
                    "title": f"{ev['team1']} - {ev['team2']}",
                    "home": ev['team1'], "away": ev['team2'],
                    "homeLogo": f"https://static.fon.bet/team_logos/{ev.get('team1Id')}.png",
                    "awayLogo": f"https://static.fon.bet/team_logos/{ev.get('team2Id')}.png",
                    "league": league_name, "status": status, "score": score,
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
