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

# Добавлены все нужные лиги
API_FOOTBALL_LEAGUES = {
    "РПЛ": 235,
    "ФНЛ": 236,             # Russian First League
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
    "Саудовская Аравия": 307,   # Saudi Pro League
    "Лига Чемпионов": 2,
    "Лига Европы": 3,
    "Лига Конференций": 848,
    "ЧМ": 1,
    "ЧЕ": 4,
    "Лига Наций": 5,
}

# Точные переводы для сложных случаев (К→C, Ч→Ch и т.д.)
TEAM_OVERRIDES = {
    "Комо": "Como",
    "Челси": "Chelsea",
    "Чезена": "Cesena",
    "Читтаделла": "Cittadella",
    "Дженоа": "Genoa",
    "Ювентус": "Juventus",
    "Интер": "Inter",
    "Милан": "AC Milan",
    "Наполи": "Napoli",
    "Лацио": "Lazio",
    "Рома": "Roma",
    "Аталанта": "Atalanta",
    "Болонья": "Bologna",
    "Фиорентина": "Fiorentina",
    "Торино": "Torino",
    "Удинезе": "Udinese",
    "Верона": "Verona",
    "Монца": "Monza",
    "Лечче": "Lecce",
    "Кальяри": "Cagliari",
    "Эмполи": "Empoli",
    "Парма": "Parma",
    "Венеция": "Venezia",
    "Зенит": "Zenit",
    "Спартак": "Spartak Moscow",
    "Краснодар": "Krasnodar",
    "Динамо Москва": "Dinamo Moscow",
    "Локомотив Москва": "Lokomotiv Moscow",
    "ЦСКА": "CSKA Moscow",
    "Ростов": "Rostov",
    "Рубин": "Rubin Kazan",
    "Ахмат": "Akhmat Grozny",
    "Крылья Советов": "Krylia Sovetov",
    "Балтика": "Baltika",
    "Факел": "Fakel",
    "Оренбург": "Orenburg",
    "Акрон": "Akron",
    "Динамо Махачкала": "Dinamo Makhachkala",
    "Родина Москва": "Rodina Moscow",
    "Сочи": "Sochi",
    "Химки": "Khimki",
    "Пари НН": "Pari NN",
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
                    result[f"api_{name}"] = logo
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

def normalize(s):
    return s.lower().replace(" ", "").replace("-", "").replace(".", "")

def find_logo(team_name, cache):
    if not team_name: return ""
    
    # 1. Проверяем словарь точных переводов
    if team_name in TEAM_OVERRIDES:
        override_name = TEAM_OVERRIDES[team_name]
        if f"api_{override_name}" in cache:
            return cache[f"api_{override_name}"]
    
    # 2. Прямое совпадение (русское название)
    if f"api_{team_name}" in cache:
        return cache[f"api_{team_name}"]
    
    # 3. Транслитерация + точное совпадение
    trans_name = normalize(transliterate(team_name))
    best_match = ""
    best_ratio = 0.0
    
    for key, logo_url in cache.items():
        if not key.startswith("api_"): continue
        api_name = normalize(key.replace("api_", ""))
        
        # Точное совпадение после нормализации
        if api_name == trans_name:
            return logo_url
        
        # Префиксное совпадение (первые 4+ символа) — безопаснее, чем вхождение
        if len(trans_name) >= 4 and len(api_name) >= 4:
            if api_name.startswith(trans_name) or trans_name.startswith(api_name):
                return logo_url
        
        # Нечеткое сравнение только для длинных названий (>=6 символов)
        if len(trans_name) >= 6 and len(api_name) >= 6:
            ratio = difflib.SequenceMatcher(None, trans_name, api_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = logo_url
    
    # Высокий порог, чтобы не цеплять случайные совпадения
    if best_ratio >= 0.85:
        return best_match
    return ""

async def main():
    print("🔄 [Scraper] Запуск...")
    
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
    
    # Скачиваем логотипы для недостающих лиг
    async with httpx.AsyncClient() as client:
        for league_name, league_id in API_FOOTBALL_LEAGUES.items():
            if league_name in fetched_leagues: continue
            
            print(f"📥 Загружаю команды для лиги: {league_name} (ID: {league_id})...")
            teams = await fetch_api_football_teams(client, league_id)
            if teams:
                logo_cache.update(teams)
                fetched_leagues.append(league_name)
                print(f"   ✅ Получено {len(teams)} команд")
            else:
                print(f"   ⚠️ Не удалось получить (возможно, лига недоступна на бесплатном тарифе)")
            await asyncio.sleep(1.0)
    
    # Сохраняем кэши
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/team_logos.json", json=logo_cache, timeout=30.0)
            await client.put(f"{FIREBASE_DB_URL}/fetched_leagues.json", json=fetched_leagues, timeout=30.0)
        print("💾 Кэш сохранен в Firebase")
    except Exception: pass
    
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