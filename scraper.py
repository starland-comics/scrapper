import asyncio
import time
import httpx
import json
import urllib.parse
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
    "РПЛ": 235, "ФНЛ": 236, "АПЛ": 39, "Чемпионшип": 40,
    "Ла Лига": 140, "Ла Лига 2": 141, "Серия А": 135,
    "Бундеслига": 78, "Лига 1": 61, "Эредивизи": 88,
    "Примейра": 94, "MLS": 253, "Саудовская Аравия": 307,
    "Лига Чемпионов": 2, "Лига Европы": 3, "Лига Конференций": 848,
}

WHITELIST = [
    (["россия", "премьер-лига"], "РПЛ"), (["россия", "фнл"], "ФНЛ"),
    (["англия", "премьер-лига"], "АПЛ"), (["испания", "ла лига"], "Ла Лига"),
    (["испания", "примера"], "Ла Лига"), (["испания", "сегунда"], "Ла Лига 2"),
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

def translate_en_to_ru(text):
    try:
        clean_text = text.replace(" FC", "").replace("FK ", "").replace(" CF", "").strip()
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={urllib.parse.quote(clean_text)}"
        r = cffi_requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            ru_name = data[0][0][0]
            ru_name = ru_name.replace(" Санкт-Петербург", "").replace(" Москва", "").replace(" Казань", "").strip()
            return ru_name
    except Exception:
        pass
    return text

async def fetch_api_football_teams(client, league_id, season):
    """Пробует разные сезоны, если базовый не работает."""
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    for s in [season, 2024, 2023, 2025]:
        params = {"league": league_id, "season": s}
        try:
            resp = await client.get(f"{API_FOOTBALL_BASE}/teams", headers=headers, params=params, timeout=20.0)
            if resp.status_code != 200:
                print(f"      ⚠️ API вернул {resp.status_code} (сезон {s})")
                continue
            
            data = resp.json()
            # Проверка на ошибки в ответе
            errors = data.get("errors")
            if errors and isinstance(errors, dict) and len(errors) > 0:
                print(f"      ⚠️ Ошибка API (сезон {s}): {errors}")
                continue
            
            teams = data.get("response", [])
            if not teams:
                print(f"      ⚠️ Пусто (сезон {s})")
                continue
            
            result = {}
            print(f"      🔄 Перевожу {len(teams)} команд на русский...")
            for i, t in enumerate(teams):
                team_info = t.get("team", {})
                name_en = team_info.get("name")
                logo = team_info.get("logo")
                if name_en and logo:
                    name_ru = await asyncio.to_thread(translate_en_to_ru, name_en)
                    result[name_ru] = logo
                    result[name_en] = logo
                if (i + 1) % 10 == 0:
                    print(f"         ...переведено {i + 1}/{len(teams)}")
            return result
        except Exception as e:
            print(f"      ⚠️ Исключение (сезон {s}): {e}")
            continue
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
    print(f"   Лиг уже скачано: {len(fetched_leagues)}")
    
    # ЗАЩИТА ОТ БАГА: если кэш пуст, но лиги помечены скачанными — сбрасываем
    if len(logo_cache) < 10 and len(fetched_leagues) > 0:
        print("⚠️ Кэш пуст, но лиги помечены как скачанные. Сбрасываю список лиг...")
        fetched_leagues = []
        try:
            async with httpx.AsyncClient() as client:
                await client.put(f"{FIREBASE_DB_URL}/fetched_leagues.json", json=[], timeout=15.0)
        except Exception: pass
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if not data or "events" not in data: 
        print("⚠️ Не удалось получить события Fonbet")
        return
    
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
    
    # Скачиваем логотипы
    async with httpx.AsyncClient() as client:
        for league_name, league_id in API_FOOTBALL_LEAGUES.items():
            if league_name in fetched_leagues: 
                print(f"⏭️ {league_name} — уже в кэше")
                continue
            
            print(f"📥 Загружаю команды для лиги: {league_name} (ID: {league_id})...")
            teams = await fetch_api_football_teams(client, league_id, 2024)
            if teams:
                logo_cache.update(teams)
                fetched_leagues.append(league_name)
                print(f"   ✅ Получено {len(teams)//2} уникальных команд")
            else:
                print(f"   ❌ Не удалось загрузить (проверь ключ/лигу/сезон)")
            await asyncio.sleep(1.5)
            
    try:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/team_logos.json", json=logo_cache, timeout=30.0)
            await client.put(f"{FIREBASE_DB_URL}/fetched_leagues.json", json=fetched_leagues, timeout=30.0)
        print(f"💾 Кэш сохранен в Firebase (всего {len(logo_cache)} записей)")
    except Exception: pass
    
    matches = {}
    found_count = 0
    total_teams_needed = 0
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        
        home_logo = logo_cache.get(ev["team1"], "")
        away_logo = logo_cache.get(ev["team2"], "")
        
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
    
    print(f"✅ Найдено логотипов: {found_count} из {total_teams_needed} команд")
    
    if matches:
        async with httpx.AsyncClient() as client:
            await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches, timeout=30.0)
        print(f"🔥 Успешно сохранено в Firebase!")

if __name__ == "__main__":
    asyncio.run(main())