import asyncio
import time
import httpx
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
API_FOOTBALL_KEY = "48a576d984d21c242b2dbea309b724e5"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

# ID лиг в API-Football
API_FOOTBALL_LEAGUES = {
    "РПЛ": 235,
    "АПЛ": 39,
    "Чемпионшип": 40,
    "Ла Лига": 140,
    "Ла Лига 2": 141,
    "Серия А": 135,
    "Бундеслига": 78,
    "Лига 1": 61,
    "Эредивизи": 88,
    "Примейра": 94,
    "MLS": 253,
    "Лига Чемпионов": 2,
    "Лига Европы": 3,
    "Лига Конференций": 848,
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

async def fetch_api_football_teams(client, league_id):
    """Запрашивает все команды лиги через API-Football и возвращает словарь {название: логотип}."""
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": 2024}  # 2024 — текущий сезон, можно изменить при необходимости
    try:
        resp = await client.get(f"{API_FOOTBALL_BASE}/teams", headers=headers, params=params, timeout=20.0)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("response", [])
            result = {}
            for t in teams:
                team_info = t.get("team", {})
                name = team_info.get("name")
                logo = team_info.get("logo")
                if name and logo:
                    result[name] = logo
            return result
    except Exception:
        pass
    return {}

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
    
    # 1. Загружаем кэш логотипов из Firebase
    print("📥 Загружаю кэш логотипов из Firebase...")
    logo_cache = {}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{FIREBASE_DB_URL}/team_logos.json", timeout=15.0)
            if resp.status_code == 200 and resp.json():
                logo_cache = resp.json()
    except Exception:
        pass
    print(f"   В кэше: {len(logo_cache)} команд")
    
    # 2. Получаем события с Фонбета
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
    
    # 3. Собираем кэфы
    sem = asyncio.Semaphore(20)
    tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
    results = await asyncio.gather(*tasks)
    
    # 4. Загружаем логотипы из API-Football для нужных лиг (если их еще нет в кэше)
    async with httpx.AsyncClient() as client:
        for league_name, league_id in API_FOOTBALL_LEAGUES.items():
            # Проверяем, есть ли уже логотипы для этой лиги в кэше (по названию команды)
            # Простой признак: если в кэше меньше 10 команд с этой лиги, загружаем
            # (упрощенно, чтобы не усложнять код)
            if len([k for k in logo_cache if k]) < 50: # Если кэш почти пуст, грузим все
                print(f"📥 Загружаю команды для лиги: {league_name} (ID: {league_id})...")
                teams = await fetch_api_football_teams(client, league_id)
                if teams:
                    logo_cache.update(teams)
                    print(f"   ✅ Получено {len(teams)} команд")
                await asyncio.sleep(1.0)  # Пауза между запросами
    
    # Сохраняем обновленный кэш в Firebase
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/team_logos.json", json=logo_cache, timeout=30.0)
        print("💾 Кэш логотипов сохранен в Firebase")
    except Exception:
        pass
    
    # 5. Формируем матчи
    # Простая транслитерация для поиска в кэше
    RU_EN = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
    def transliterate(text):
        return ''.join(RU_EN.get(c.lower(), c) for c in text)
    
    matches = {}
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        home_name = ev["team1"]
        away_name = ev["team2"]
        league = ev["_league"]
        
        # Ищем логотипы в кэше по английскому названию
        home_en = transliterate(home_name)
        away_en = transliterate(away_name)
        
        home_logo = logo_cache.get(home_name) or logo_cache.get(home_en) or ""
        away_logo = logo_cache.get(away_name) or logo_cache.get(away_en) or ""
        
        matches[f"fon_{ev['id']}"] = {
            "title": f"{home_name} - {away_name}",
            "home": home_name, "away": away_name,
            "homeLogo": home_logo,
            "awayLogo": away_logo,
            "league": league, "status": status, "score": score,
            "start_time": ev.get("startTime"), "odds": odds,
        }
    
    print(f"✅ Собрано матчей: {len(matches)}")
    
    if matches:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches, timeout=30.0)
        print(f"🔥 Успешно сохранено в Firebase!")

if __name__ == "__main__":
    asyncio.run(main())