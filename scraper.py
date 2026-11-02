import asyncio
import time
import httpx
import json
import urllib.parse
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
LOGO_BASE = "https://cdn-ec.bk6bba-resources.ru/ContentCommon/Logotypes/TeamLogos/Football"

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

RU_EN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}

def transliterate(text):
    return ''.join(RU_EN.get(c.lower(), c) for c in text)

WHITELIST = [
    (["россия", "премьер-лига"], "РПЛ", "Russia"),
    (["россия", "фнл"], "ФНЛ", "Russia"),
    (["англия", "премьер-лига"], "АПЛ", "England"),
    (["испания", "ла лига"], "Ла Лига", "Spain"),
    (["испания", "примера"], "Ла Лига", "Spain"),
    (["испания", "сегунда"], "Ла Лига 2", "Spain"),
    (["италия", "серия а"], "Серия А", "Italy"),
    (["германия", "бундеслига"], "Бундеслига", "Germany"),
    (["франция", "лига 1"], "Лига 1", "France"),
    (["саудовская"], "Саудовская Аравия", "Saudi Arabia"),
    (["нидерланды", "эредивизи"], "Эредивизи", "Netherlands"),
    (["португалия", "примейра"], "Примейра", "Portugal"),
    (["сша", "mls"], "MLS", "USA"),
    (["англия", "чемпионшип"], "Чемпионшип", "England"),
    (["лига чемпионов"], "Лига Чемпионов", "Europe"),
    (["лига европы"], "Лига Европы", "Europe"),
    (["лига конференций"], "Лига Конференций", "Europe"),
    (["чемпионат мира"], "ЧМ", "World"),
    (["чемпионат европы"], "ЧЕ", "Europe"),
    (["лига наций"], "Лига Наций", "Europe"),
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
    if not raw_name or not isinstance(raw_name, str): return None, None
    name = raw_name.lower().strip()
    for bad in BLACKLIST:
        if bad in name: return None, None
    for keywords, clean, country in WHITELIST:
        if all(kw in name for kw in keywords):
            return clean, country
    return None, None

def get_fonbet_data_sync(url):
    try:
        r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=15)
        if r.status_code == 200: return r.json()
    except Exception: pass
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
        clean_name, country = get_clean_league(raw_name)
        if clean_name and country:
            valid_leagues[lid] = (clean_name, country)
    
    print(f"✅ Целевых лиг: {len(valid_leagues)}")
    
    now = time.time()
    valid_events = []
    for ev in events:
        if ev.get("kind") != 1 or not ev.get("team1") or not ev.get("team2"): continue
        start = ev.get("startTime", 0)
        if not (now - 10800 < start < now + 604800): continue 
        sport_id = ev.get("sportId")
        if sport_id not in valid_leagues: continue
        ev["_league"], ev["_country"] = valid_leagues[sport_id]
        valid_events.append(ev)
    
    print(f"⚽ Матчей: {len(valid_events)}")
    if not valid_events: return
    
    sem = asyncio.Semaphore(20)
    tasks = [fetch_odds_and_score(ev["id"], sem) for ev in valid_events]
    results = await asyncio.gather(*tasks)
    
    matches = {}
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        
        home_name = ev["team1"]
        away_name = ev["team2"]
        country = ev["_country"]
        
        # Генерируем URL логотипов на основе шаблона
        home_en = transliterate(home_name).replace(" ", "")
        away_en = transliterate(away_name).replace(" ", "")
        
        home_logo = f"{LOGO_BASE}/{country}/{home_en}.png" if country != "Europe" else ""
        away_logo = f"{LOGO_BASE}/{country}/{away_en}.png" if country != "Europe" else ""
        
        matches[f"fon_{ev['id']}"] = {
            "title": f"{home_name} - {away_name}",
            "home": home_name, "away": away_name,
            "homeLogo": home_logo,
            "awayLogo": away_logo,
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
