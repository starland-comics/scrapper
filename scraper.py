import asyncio
import time
import httpx
import json
import urllib.parse
import difflib
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
API_FOOTBALL_KEY = "48a576d984d21c242b2dbea309b724e5"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
SPORTSDBS_BASE = "https://www.thesportsdb.com/api/v1/json/3"

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

API_FOOTBALL_LEAGUES = {
    "РПЛ": 235, "ФНЛ": 236, "АПЛ": 39, "Чемпионшип": 40,
    "Ла Лига": 140, "Ла Лига 2": 141, "Серия А": 135,
    "Бундеслига": 78, "Лига 1": 61, "Эредивизи": 88,
    "Примейра": 94, "MLS": 253, "Саудовская Аравия": 307,
    "Лига Чемпионов": 2, "Лига Европы": 3, "Лига Конференций": 848,
}

WHITELIST = [
    (["россия", "премьер-лига"], "РПЛ"), (["россия", "фнл"], "ФНЛ"),
    (["англия", "премьер-лига"], "АПЛ"), (["испания", "ла лига"], "Лига Испании"),
    (["испания", "примера"], "Лига Испании"), (["испания", "сегунда"], "Сегунда"),
    (["италия", "серия а"], "Серия А"), (["германия", "бундеслига"], "Бундеслига"),
    (["франция", "лига 1"], "Лига 1"), (["саудовская"], "Саудовская Аравия"),
    (["нидерланды", "эредивизи"], "Эредивизи"), (["португалия", "примейра"], "Примейра"),
    (["сша", "mls"], "MLS"), (["англия", "чемпионшип"], "Чемпионшип"),
    (["лига чемпионов"], "Лига Чемпионов"), (["лига европы"], "Лига Европы"),
    (["лига конференций"], "Лига Конференций"), (["чемпионат мира"], "ЧМ"),
    (["чемпионат европы"], "ЧЕ"), (["лига наций"], "Лига Наций"),
]

BLACKLIST = [
    "женщины", "жен.", "u21", "u19", "u20", "u23", "юнош", "молодеж", "молодёж", "резерв",
    "ла лига 2", "ла лига 3", "примера rfef", "сегунда b", "терсера",
    "бундеслига 2", "бундеслига 3", "бундеслига-2", "бундеслига-3",
    "серия b", "серия c", "серия d", "истмиан", "северная", "южная", "восточная", "западная",
    "регион", "любител", "товарищеск", "баскетбол", "волейбол", "хоккей", "теннис", "кибер",
    "борьб", "бокс", "мма", "ufc", "футзал", "пляжный", "афк", "afc",
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

def translate_text(text, sl, tl):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={urllib.parse.quote(text)}"
        r = cffi_requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()[0][0][0]
    except Exception:
        pass
    return text

async def fetch_api_football_teams(client, league_id):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    for s in [2024, 2023, 2025, 2022]:
        params = {"league": league_id, "season": s}
        try:
            resp = await client.get(f"{API_FOOTBALL_BASE}/teams", headers=headers, params=params, timeout=20.0)
            if resp.status_code != 200: continue
            data = resp.json()
            errors = data.get("errors")
            if errors and isinstance(errors, dict) and len(errors) > 0: continue
            teams = data.get("response", [])
            if not teams: continue
            result = {}
            print(f"      🔄 Перевожу {len(teams)} команд (сезон {s})...")
            for i, t in enumerate(teams):
                team_info = t.get("team", {})
                name_en = team_info.get("name")
                logo = team_info.get("logo")
                if name_en and logo:
                    name_ru = await asyncio.to_thread(translate_text, name_en, "en", "ru")
                    name_ru = name_ru.replace(" Санкт-Петербург", "").replace(" Москва", "").strip()
                    result[f"ru_{name_ru}"] = logo
                    result[f"en_{name_en}"] = logo
                if (i + 1) % 20 == 0:
                    print(f"         ...{i + 1}/{len(teams)}")
            return result
        except Exception:
            continue
    return {}

async def search_sportsdb(client, name_en):
    """Fallback: ищем в TheSportsDB (бесплатно, без лимитов)."""
    try:
        url = f"{SPORTSDBS_BASE}/searchteams.php?t={urllib.parse.quote(name_en)}"
        resp = await client.get(url, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams") or []
            for t in teams:
                logo = t.get("strTeamBadge") or t.get("strTeamLogo")
                if logo and logo.startswith("http"):
                    return logo
    except Exception:
        pass
    return None

def normalize(s):
    return s.lower().replace(" ", "").replace("-", "").replace(".", "").replace("'", "")

def find_logo(team_name, cache):
    if not team_name: return ""
    
    # 1. Прямое совпадение по русскому ключу
    if f"ru_{team_name}" in cache:
        return cache[f"ru_{team_name}"]
    
    norm_input = normalize(team_name)
    best_logo = ""
    best_score = 0
    
    for key, logo in cache.items():
        if not (key.startswith("ru_") or key.startswith("en_")):
            continue
        
        # Ключ кэша — без префикса
        key_clean = key[3:]
        norm_key = normalize(key_clean)
        
        # 2. Префиксное совпадение (первые 5+ символов)
        if len(norm_input) >= 5 and len(norm_key) >= 5:
            prefix = norm_input[:5]
            if norm_key.startswith(prefix) or norm_input.startswith(norm_key[:5]):
                score = 0.9
                if score > best_score:
                    best_score = score
                    best_logo = logo
                continue
        
        # 3. Нечёткое сравнение
        if len(norm_input) >= 4 and len(norm_key) >= 4:
            ratio = difflib.SequenceMatcher(None, norm_input, norm_key).ratio()
            # Более мягкий порог для длинных названий
            threshold = 0.75 if len(norm_input) >= 8 else 0.85
            if ratio > threshold and ratio > best_score:
                best_score = ratio
                best_logo = logo
    
    return best_logo

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
    
    # Скачиваем лиги через API-Football
    async with httpx.AsyncClient() as client:
        for league_name, league_id in API_FOOTBALL_LEAGUES.items():
            if league_name in fetched_leagues: 
                print(f"⏭️ {league_name} — уже в кэше")
                continue
            
            print(f"📥 Загружаю команды для лиги: {league_name}...")
            teams = await fetch_api_football_teams(client, league_id)
            if teams:
                logo_cache.update(teams)
                fetched_leagues.append(league_name)
                print(f"   ✅ Получено {len(teams)//2} уникальных команд")
            await asyncio.sleep(1.5)
    
    # Находим отсутствующие команды
    missing_teams = set()
    for ev in valid_events:
        if not find_logo(ev["team1"], logo_cache): missing_teams.add(ev["team1"])
        if not find_logo(ev["team2"], logo_cache): missing_teams.add(ev["team2"])
    
    if missing_teams:
        print(f"🔎 Не найдено в кэше: {len(missing_teams)} команд. Ищу в TheSportsDB...")
        async with httpx.AsyncClient() as client:
            for i, team in enumerate(missing_teams):
                # Переводим RU -> EN для TheSportsDB
                team_en = await asyncio.to_thread(translate_text, team, "ru", "en")
                logo = await search_sportsdb(client, team_en)
                if logo:
                    logo_cache[f"ru_{team}"] = logo
                    print(f"   ✅ {team} ({team_en})")
                else:
                    print(f"   ⚠️ {team} ({team_en})")
                await asyncio.sleep(0.3)
    
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/team_logos.json", json=logo_cache, timeout=30.0)
            await client.put(f"{FIREBASE_DB_URL}/fetched_leagues.json", json=fetched_leagues, timeout=30.0)
        print(f"💾 Кэш сохранен ({len(logo_cache)} записей)")
    except Exception: pass
    
    matches = {}
    found_count = 0
    total_teams_needed = 0
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        
        home_logo = find_logo(ev["team1"], logo_cache)
        away_logo = find_logo(ev["team2"], logo_cache)
        
        total_teams_needed += 2
        if home_logo: found_count += 1
        if away_logo: found_count += 1
            
        matches[f"fon_{ev['id']}"] = {
            "title": f"{ev['team1']} - {ev['team2']}",
            "home": ev["team1"], "away": ev["team2"],
            "homeLogo": home_logo,
            "awayLogo": away_logo,
            "league": ev["_league"], "status": status, "score": score,
            "start_time": ev.get("startTime"), "odds": odds,
        }
    
    print(f"✅ Итого логотипов: {found_count} из {total_teams_needed} команд ({found_count*100//max(1,total_teams_needed)}%)")
    
    if matches:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches, timeout=30.0)
        print(f"🔥 Успешно сохранено в Firebase!")

if __name__ == "__main__":
    asyncio.run(main())