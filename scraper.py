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

# Строгий белый список ключевых слов для футбольных лиг
WHITELIST = [
    ("англия", "премьер-лига", "апл"),
    ("россия", "премьер-лига", "рпл"),
    ("россия", "фнл", "фнл"),
    ("испания", "ла лига", "ла лига"),
    ("испания", "сегунда", "ла лига 2"),
    ("италия", "серия а", "серия а"),
    ("германия", "бундеслига", "бундеслига"),
    ("франция", "лига 1", "лига 1"),
    ("англия", "чемпионшип", "чемпионшип"),
    ("саудовская", "", "саудовская аравия"),
    ("нидерланды", "эредивизи", "эредивизи"),
    ("португалия", "примейра", "примейра"),
    ("сша", "mls", "mls"),
    ("лига чемпионов", "", "лига чемпионов"),
    ("лига европы", "", "лига европы"),
    ("лига конференций", "", "лига конференций"),
    ("чемпионат мира", "", "чм"),
    ("чемпионат европы", "", "че"),
    ("лига наций", "", "лига наций")
]

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

def get_football_leagues(data):
    """Берем лиги СТРОГО из футбольного раздела (kind=1)"""
    leagues = {}
    sports = data.get("sports", [])
    if isinstance(sports, dict): sports = sports.values()
    
    for s in sports:
        if not isinstance(s, dict): continue
        # Футбол в Фонбете - это kind = 1
        if s.get("kind") == 1 or s.get("name") == "Футбол":
            regions = s.get("regions", [])
            if isinstance(regions, dict): regions = regions.values()
            for r in regions:
                if not isinstance(r, dict): continue
                comps = r.get("competitions", [])
                if isinstance(comps, dict): comps = comps.values()
                for c in comps:
                    if not isinstance(c, dict): continue
                    cid = c.get("id")
                    cname = c.get("name") or c.get("rusName")
                    if cid and cname:
                        leagues[cid] = cname
    return leagues

def get_clean_league_name(raw_name):
    name = raw_name.lower()
    
    # Жесткая отсечка мусора внутри лиг
    if "женщины" in name or "u21" in name or "u19" in name or "юнош" in name or "молодеж" in name:
        return None
    if "бундеслига 3" in name or "бундеслига-3" in name or "бундеслига 2" in name or "серия b" in name or "серия c" in name:
        return None

    for keys, _, clean_name in WHITELIST:
        if keys in name:
            return clean_name.upper()
            
    return None

async def main():
    print("🔄 [Scraper] Запуск...")
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if data and "events" in data:
        events = data.get("events", [])
        leagues_map = get_football_leagues(data)
        print(f"✅ Загружено футбольных лиг: {len(leagues_map)}")

        now = time.time()
        valid_events = []
        
        for ev in events:
            if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2"):
                if ev.get("startTime", 0) > now - 10800:
                    league_id = ev.get("sportId")
                    raw_league_name = leagues_map.get(league_id)
                    
                    if not raw_league_name: continue
                    
                    clean_name = get_clean_league_name(raw_league_name)
                    
                    # Если лига прошла фильтр, добавляем
                    if clean_name:
                        ev['league_name'] = clean_name
                        valid_events.append(ev)
        
        print(f"⚽ Матчей после фильтрации: {len(valid_events)}")
        
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