import asyncio
import time
import httpx
import json
import difflib
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

API_FOOTBALL_LEAGUES = {
    "РПЛ": 235, "АПЛ": 39, "Чемпионшип": 40, "Ла Лига": 140, "Ла Лига 2": 141,
    "Серия А": 135, "Бундеслига": 78, "Лига 1": 61, "Эредивизи": 88,
    "Примейра": 94, "MLS": 253, "Лига Чемпионов": 2, "Лига Европы": 3, "Лига Конференций": 848,
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

RU_EN = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}

def transliterate(text):
    return ''.join(RU_EN.get(c.lower(), c) for c in text)

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
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": 2024}
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
                    result[f"api_{name}"] = logo  # Добавляем префикс api_ для защиты от мусора
            return result
    except Exception: pass
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

# Функция нечеткого поиска логотипа
def find_logo(team_name, cache):
    if not team_name: return ""
    
    # 1. Прямое совпадение
    if f"api_{team_name}" in cache: return cache[f"api_{team_name}"]
    
    trans_name = transliterate(team_name).lower().replace(" ", "")
    best_match = ""
    best_ratio = 0.0
    
    for key, logo_url in cache.items():
        if not key.startswith("api_"): continue # Игнорируем мусор
        api_name = key.replace("api_", "").lower().replace(" ", "")
        
        # 2. Прямое вхождение (если trans_name полностью входит в api_name)
        if trans_name in api_name or api_name in trans_name:
            return logo_url
            
        # 3. Нечеткое сравнение
        ratio = difflib.SequenceMatcher(None, trans_name, api_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = logo_url
            
    # Порог 0.8 отсекает случайный мусор, но пропускает опечатки (например, Krylia vs Krylya)
    if best_ratio >= 0.8:
        return best_match
    return ""

async def main():
    print("🔄 [Scraper] Запуск...")
    
    # 1. Загружаем кэши
    print("📥 Загружаю кэш...")
    logo_cache = {}
    fetched_leagues = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{FIREBASE_DB_URL}/team_logos.json", timeout=15.0)
            if resp.status_code == 200 and resp.json(): logo_cache = resp.json()
            
            resp2 = await client.get(f"{FIREBASE_DB_URL}/fetched_leagues.json", timeout=15.0)
            if resp2.status_code == 200 and resp2.json(): fetched_leagues = resp2.json()
    except Exception: pass
    print(f"   Команд в кэше: {len(logo_cache)}")
    print(f"   Лиг скачано: {len(fetched_leagues)}")
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if not data or "events" not in data: return
    
    events = data.get("events", [])
    league_map = {}
    for s in data.get("sports", []):
        if isinstance(s, dict) and s.get("kind") == "segment" and s.get("parentId") == 1:
            if s.get("id") and s.get("name"): league_map[int(s["id"])] = s["name"]
    
    valid_leagues = {}
    for lid, raw_name in league_map.items():
        clean = get_clean_league(raw_name)
        if clean: valid_leagues[lid] = clean
    
    now = time.time()
    valid_events = []
    for ev in events:
        if ev.get("kind") != 1 or not ev.get("team1") or not ev.get("team2"): continue
        if not (now - 10800 < ev.get("startTime", 0) < now + 604800): continue 
        if ev.get("sportId") not in valid_leagues: continue
        ev["_league"] = valid_leagues[ev["sportId"]]
        valid_events.append(ev)
    
    print(f"⚽ Матчей: {len(valid_events)}")
    if not valid_events: return
    
    sem = asyncio.Semaphore(20)
    tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
    results = await asyncio.gather(*tasks)
    
    # 2. Скачиваем логотипы ТОЛЬКО для тех лиг, которых еще нет в fetched_leagues
    async with httpx.AsyncClient() as client:
        for league_name, league_id in API_FOOTBALL_LEAGUES.items():
            if league_name in fetched_leagues: continue
            
            print(f"📥 Загружаю команды для лиги: {league_name}...")
            teams = await fetch_api_football_teams(client, league_id)
            if teams:
                logo_cache.update(teams)
                fetched_leagues.append(league_name)
                print(f"   ✅ Получено {len(teams)} команд")
            await asyncio.sleep(1.0)
            
    # Сохраняем кэши
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/team_logos.json", json=logo_cache, timeout=30.0)
            await client.put(f"{FIREBASE_DB_URL}/fetched_leagues.json", json=fetched_leagues, timeout=30.0)
        print("💾 Кэш сохранен в Firebase")
    except Exception: pass
    
    # 3. Формируем матчи
    matches = {}
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        matches[f"fon_{ev['id']}"] = {
            "title": f"{ev['team1']} - {ev['team2']}",
            "home": ev["team1"], "away": ev["team2"],
            "homeLogo": find_logo(ev["team1"], logo_cache),
            "awayLogo": find_logo(ev["team2"], logo_cache),
            "league": ev["_league"], "status": status, "score": score,
            "start_time": ev.get("startTime"), "odds": odds,
        }
    
    print(f"✅ Собрано матчей: {len(matches)}")
    if matches:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches, timeout=30.0)
        print(f"🔥 Успешно сохранено в Firebase!")

if __name__ == "__main__":
    asyncio.run(main())