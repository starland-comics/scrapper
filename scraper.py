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

# Черный список слов, которые выкидывают лигу в мусор
BLACKLIST = [
    "женщины", "u21", "u19", "u20", "молодеж", "юнош", "резерв", "любител", 
    "истмиан", "северная", "южная", "восточная", "западная", "регион", 
    "баскетбол", "волейбол", "теннис", "кибер"
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

def normalize_league_name(raw_name):
    name = raw_name.lower()
    
    # ТОЧНЫЕ СОВПАДЕНИЯ (отсекаем "Англия. Премьер-лига. Северная" и т.д.)
    if name == "англия. премьер-лига" or "премьер-лига. сезон" in name: return "АПЛ"
    if name == "испания. ла лига" or "ла лига. сезон" in name: return "Ла Лига"
    if name == "италия. серия а" or "серия а. сезон" in name: return "Серия А"
    if name == "германия. бундеслига" or "бундеслига. сезон" in name: return "Бундеслига"
    if name == "франция. лига 1" or "лига 1. сезон" in name: return "Лига 1"
    if name == "россия. премьер-лига" or "премьер-лига. сезон" in name and "россия" in name: return "РПЛ"
    
    if "испания. сегунда" in name: return "Ла Лига 2"
    if "россия. фнл" in name: return "ФНЛ"
    if "саудовская" in name: return "Саудовская Аравия"
    if "нидерланды. эредивизи" in name: return "Эредивизи"
    if "португалия. примейра" in name: return "Примейра"
    if "сша. mls" in name or "сша. млс" in name: return "MLS"
    if "англия. чемпионшип" in name: return "Чемпионшип"
    
    if "лига чемпионов" in name: return "Лига Чемпионов"
    if "лига европы" in name: return "Лига Европы"
    if "лига конференций" in name: return "Лига Конференций"
    
    if "чемпионат мира" in name: return "ЧМ"
    if "чемпионат европы" in name: return "ЧЕ"
    if "лига наций" in name: return "Лига Наций"
    
    return raw_name

def extract_leagues(data):
    leagues = {}
    for key, val in data.items():
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    cid = item.get("id") or item.get("sportId")
                    cname = item.get("name") or item.get("rusName")
                    if cid and cname and isinstance(cname, str):
                        leagues[cid] = cname
        elif isinstance(val, dict):
            for item in val.values():
                if isinstance(item, dict):
                    cid = item.get("id") or item.get("sportId")
                    cname = item.get("name") or item.get("rusName")
                    if cid and cname and isinstance(cname, str):
                        leagues[cid] = cname
    return leagues

async def main():
    print("🔄 [Scraper] Запуск...")
    
    list_url = f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru"
    data = await asyncio.to_thread(get_fonbet_data_sync, list_url)
    
    if data and "events" in data:
        events = data.get("events", [])
        leagues_map = extract_leagues(data)
        print(f"✅ Загружено названий лиг: {len(leagues_map)}")

        now = time.time()
        valid_events = []
        
        for ev in events:
            if ev.get("kind") == 1 and ev.get("team1") and ev.get("team2"):
                if ev.get("startTime", 0) > now - 10800:
                    league_id = ev.get("sportId")
                    raw_league_name = leagues_map.get(league_id, "")
                    
                    if not raw_league_name: continue
                    
                    l_name = raw_league_name.lower()
                    # Если есть запрещенные слова — пропускаем
                    if any(bad_word in l_name for bad_word in BLACKLIST):
                        continue

                    clean_name = normalize_league_name(raw_league_name)
                    
                    # Оставляем только те, что мы нормализовали (то есть целевые)
                    if clean_name != raw_league_name:
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