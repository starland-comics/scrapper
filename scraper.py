import asyncio
import time
import httpx
import json
import urllib.parse
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
FOTMOB_BASE = "https://www.fotmob.com/api/data"

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fotmob.com/",
}

WHITELIST = [
    (["россия", "премьер-лига"], "РПЛ"),
    (["россия", "фнл"], "ФНЛ"),
    (["англия", "премьер-лига"], "АПЛ"),
    (["испания", "ла лига"], "Ла Лига"),
    (["испания", "примера"], "Ла Лига"),
    (["испания", "сегунда"], "Ла Лига 2"),
    (["италия", "серия а"], "Серия А"),
    (["германия", "бундеслига"], "Бундеслига"),
    (["франция", "лига 1"], "Лига 1"),
    (["саудовская"], "Саудовская Аравия"),
    (["нидерланды", "эредивизи"], "Эредивизи"),
    (["португалия", "примейра"], "Примейра"),
    (["сша", "mls"], "MLS"),
    (["англия", "чемпионшип"], "Чемпионшип"),
    (["лига чемпионов"], "Лига Чемпионов"),
    (["лига европы"], "Лига Европы"),
    (["лига конференций"], "Лига Конференций"),
    (["чемпионат мира"], "ЧМ"),
    (["чемпионат европы"], "ЧЕ"),
    (["лига наций"], "Лига Наций"),
]

BLACKLIST = [
    "женщины", "жен.", "u21", "u19", "u20", "u23", "юнош", "молодеж", "молодёж", "резерв",
    "ла лига 2", "ла лига 3", "примера rfef", "сегунда b", "терсера",
    "бундеслига 2", "бундеслига 3", "бундеслига-2", "бундеслига-3",
    "серия b", "серия c", "серия d", "истмиан", "северная", "южная", "восточная", "западная",
    "регион", "любител", "товарищеск", "баскетбол", "волейбол", "хоккей", "теннис", "кибер",
    "борьб", "бокс", "мма", "ufc", "футзал", "пляжный",
]

def get_clean_league(raw_name):
    if not raw_name or not isinstance(raw_name, str): return None
    name = raw_name.lower().strip()
    for bad in BLACKLIST:
        if bad in name: return None
    for keywords, clean in WHITELIST:
        if all(kw in name for kw in keywords): return clean
    return None

def get_fonbet_data_sync(url):
    try:
        r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=15)
        if r.status_code == 200: return r.json()
    except Exception: pass
    return None

def search_fotmob_sync(team_name):
    """Ищет команду в FotMob и возвращает URL логотипа."""
    try:
        # FotMob search endpoint
        query = urllib.parse.quote(team_name)
        url = f"https://apigw.fotmob.com/searchapi/suggest?term={query}&lang=ru"
        
        r = cffi_requests.get(url, headers=FOTMOB_HEADERS, impersonate="chrome120", timeout=10)
        if r.status_code != 200:
            return None
        
        data = r.json()
        suggestions = data.get("suggestions", [])
        
        for sugg in suggestions:
            # Ищем тип "team"
            if sugg.get("type") == "team":
                team_id = sugg.get("id")
                if team_id:
                    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
    except Exception:
        pass
    return None

async def firebase_get(path):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{FIREBASE_DB_URL}/{path}.json", timeout=15.0)
            return resp.json()
    except Exception:
        return None

async def firebase_put(path, data):
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=30.0)
    except Exception:
        pass

async def get_team_logo(team_name, cache):
    if not team_name: return ""
    if team_name in cache and cache[team_name]:
        return cache[team_name]
    
    logo = await asyncio.to_thread(search_fotmob_sync, team_name)
    
    if logo:
        cache[team_name] = logo
        print(f"  ✅ {team_name}")
    else:
        cache[team_name] = ""
        print(f"  ⚠️ {team_name}")
    
    return logo or ""

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
            if odds["1"] and odds["X"] and odds["2"]: break
        
        if not odds["1"]: return None
        
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
    
    # Загружаем кэш логотипов из Firebase
    print("📥 Загружаю кэш логотипов...")
    logo_cache = await firebase_get("team_logos") or {}
    print(f"   В кэше: {len(logo_cache)} команд")
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if not data or "events" not in data: 
        print("⚠️ Не удалось получить список событий.")
        return
    
    events = data.get("events", [])
    print(f"🔍 Всего событий: {len(events)}")
    
    league_map = {}
    for s in data.get("sports", []):
        if not isinstance(s, dict): continue
        if s.get("kind") != "segment": continue
        if s.get("parentId") != 1: continue
        sid = s.get("id")
        sname = s.get("name")
        if sid and sname: league_map[int(sid)] = sname
    
    valid_leagues = {}
    for lid, raw_name in league_map.items():
        clean = get_clean_league(raw_name)
        if clean: valid_leagues[lid] = clean
    
    print(f"✅ Целевых лиг: {len(valid_leagues)}")
    
    now = time.time()
    valid_events = []
    for ev in events:
        if ev.get("kind") != 1 or not ev.get("team1") or not ev.get("team2"): continue
        start = ev.get("startTime", 0)
        if not (now - 10800 < start < now + 604800): continue 
        sport_id = ev.get("sportId")
        if sport_id not in valid_leagues: continue
        ev["_league"] = valid_leagues[sport_id]
        valid_events.append(ev)
    
    print(f"⚽ Матчей: {len(valid_events)}")
    if not valid_events: return
    
    sem = asyncio.Semaphore(20)
    tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
    results = await asyncio.gather(*tasks)
    
    # Собираем уникальные имена команд
    unique_teams = set()
    for ev in valid_events:
        unique_teams.add(ev["team1"])
        unique_teams.add(ev["team2"])
    
    # Ищем логотипы для тех, кого нет в кэше
    missing_teams = [t for t in unique_teams if not logo_cache.get(t)]
    print(f"🔎 Нужно найти логотипов: {len(missing_teams)}")
    
    if missing_teams:
        print("⏳ Ищу логотипы в FotMob...")
        for i, team in enumerate(missing_teams):
            await get_team_logo(team, logo_cache)
            if i < len(missing_teams) - 1:
                await asyncio.sleep(0.5)  # Пауза 0.5 сек
    
    print("✅ Поиск логотипов завершен")
    
    # Формируем матчи
    matches = {}
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        home_name = ev["team1"]
        away_name = ev["team2"]
        
        matches[f"fon_{ev['id']}"] = {
            "title": f"{home_name} - {away_name}",
            "home": home_name, "away": away_name,
            "homeLogo": logo_cache.get(home_name) or "",
            "awayLogo": logo_cache.get(away_name) or "",
            "league": ev["_league"], "status": status, "score": score,
            "start_time": ev.get("startTime"), "odds": odds,
        }
    
    print(f"✅ Собрано матчей: {len(matches)}")
    
    if matches:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches, timeout=30.0)
        await firebase_put("team_logos", logo_cache)
        print(f"🔥 Успешно сохранено в Firebase!")

if __name__ == "__main__":
    asyncio.run(main())
