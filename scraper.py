import asyncio
import time
import httpx
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
LOGO_BASE_URL = "https://raw.githubusercontent.com/luukhopman/football-logos/master/logos"

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
}

# ИСПРАВЛЕНО: названия папок в точности как в репозитории
LEAGUE_FOLDERS = {
    "РПЛ": "Russia - Premier League",
    "АПЛ": "England - Premier League",
    "Чемпионшип": "England - Championship",
    "Ла Лига": "Spain - La Liga",
    "Ла Лига 2": "Spain - La Liga 2",
    "Серия А": "Italy - Serie A",
    "Бундеслига": "Germany - Bundesliga",
    "Лига 1": "France - Ligue 1",
    "Эредивизи": "Netherlands - Eredivisie",
    "Примейра": "Portugal - Primeira Liga",
    "MLS": "USA - MLS",
    "Лига Чемпионов": "Europe - UEFA Champions League",
    "Лига Европы": "Europe - UEFA Europa League",
    # Для остальных лиг (ФНЛ, Саудовская Аравия, Лига Конференций и т.д.)
    # в этом репозитории логотипов может не быть, поэтому они останутся с заглушками
}

# Словарь переводов названий команд с русского на английский
# В репозитории файлы называются по-английски
TEAM_TRANSLATIONS = {
    # РПЛ
    "Зенит": "Zenit",
    "Спартак": "Spartak Moscow",
    "ЦСКА": "CSKA Moscow",
    "Динамо Москва": "Dynamo Moscow",
    "Локомотив Москва": "Lokomotiv Moscow",
    "Краснодар": "Krasnodar",
    "Ростов": "Rostov",
    "Рубин": "Rubin Kazan",
    "Ахмат": "Akhmat Grozny",
    "Крылья Советов": "Krylia Sovetov",
    "Балтика": "Baltika",
    "Факел": "Fakel",
    "Оренбург": "Orenburg",
    "Акрон": "Akron",
    "Динамо Махачкала": "Dynamo Makhachkala",
    "Родина Москва": "Rodina Moscow",
    # АПЛ
    "Арсенал": "Arsenal",
    "Челси": "Chelsea",
    "Ливерпуль": "Liverpool",
    "Манчестер Сити": "Manchester City",
    "Манчестер Юнайтед": "Manchester United",
    "Тоттенхэм": "Tottenham",
    "Ньюкасл": "Newcastle",
    "Астон Вилла": "Aston Villa",
    "Брайтон": "Brighton",
    "Вест Хэм": "West Ham",
    "Эвертон": "Everton",
    "Кристал Пэлас": "Crystal Palace",
    "Брентфорд": "Brentford",
    "Фулхэм": "Fulham",
    "Вулверхэмптон": "Wolves",
    "Борнмут": "Bournemouth",
    "Ноттингем Форест": "Nottingham Forest",
    "Лестер": "Leicester",
    "Ипсвич": "Ipswich",
    "Саутгемптон": "Southampton",
    # Ла Лига
    "Реал Мадрид": "Real Madrid",
    "Барселона": "Barcelona",
    "Атлетико": "Atletico Madrid",
    "Севилья": "Sevilla",
    "Реал Сосьедад": "Real Sociedad",
    "Атлетик Бильбао": "Athletic Bilbao",
    "Вильярреал": "Villarreal",
    "Бетис": "Real Betis",
    "Валенсия": "Valencia",
    "Жирона": "Girona",
    "Осасуна": "Osasuna",
    "Сельта": "Celta Vigo",
    "Райо Вальекано": "Rayo Vallecano",
    "Мальорка": "Mallorca",
    "Лас-Пальмас": "Las Palmas",
    "Алавес": "Alaves",
    "Хетафе": "Getafe",
    "Эспаньол": "Espanyol",
    "Леганес": "Leganes",
    "Вальядолид": "Real Valladolid",
    # Серия А
    "Ювентус": "Juventus",
    "Милан": "AC Milan",
    "Интер": "Inter",
    "Наполи": "Napoli",
    "Рома": "Roma",
    "Лацио": "Lazio",
    "Аталанта": "Atalanta",
    "Фиорентина": "Fiorentina",
    "Болонья": "Bologna",
    "Торино": "Torino",
    "Удинезе": "Udinese",
    "Дженоа": "Genoa",
    "Лечче": "Lecce",
    "Кальяри": "Cagliari",
    "Верона": "Verona",
    "Эмполи": "Empoli",
    "Парма": "Parma",
    "Комо": "Como",
    "Венеция": "Venezia",
    "Монца": "Monza",
    # Бундеслига
    "Бавария": "Bayern Munich",
    "Боруссия Дортмунд": "Borussia Dortmund",
    "Лейпциг": "RB Leipzig",
    "Байер": "Bayer Leverkusen",
    "Айнтрахт Франкфурт": "Eintracht Frankfurt",
    "Штутгарт": "Stuttgart",
    "Фрайбург": "Freiburg",
    "Вольфсбург": "Wolfsburg",
    "Боруссия Мёнхенгладбах": "Borussia Monchengladbach",
    "Майнц": "Mainz",
    "Аугсбург": "Augsburg",
    "Вердер": "Werder Bremen",
    "Хоффенхайм": "Hoffenheim",
    "Унион Берлин": "Union Berlin",
    "Санкт-Паули": "St. Pauli",
    "Хайденхайм": "Heidenheim",
    "Хольштайн Киль": "Holstein Kiel",
    "Бохум": "Bochum",
    # Лига 1
    "ПСЖ": "Paris Saint-Germain",
    "Марсель": "Marseille",
    "Монако": "Monaco",
    "Лион": "Lyon",
    "Лилль": "Lille",
    "Ницца": "Nice",
    "Ренн": "Rennes",
    "Ланс": "Lens",
    "Страсбур": "Strasbourg",
    "Тулуза": "Toulouse",
    "Монпелье": "Montpellier",
    "Брест": "Brest",
    "Нант": "Nantes",
    "Реймс": "Reims",
    "Гавр": "Le Havre",
    "Осер": "Auxerre",
    "Анже": "Angers",
    "Сент-Этьен": "Saint-Etienne",
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
    
    matches = {}
    for ev, res in zip(valid_events, results):
        if not res: continue
        odds, score, status = res
        
        home_name = ev["team1"]
        away_name = ev["team2"]
        league = ev["_league"]
        
        league_folder = LEAGUE_FOLDERS.get(league, "")
        if league_folder:
            # Переводим названия команд на английский
            home_en = TEAM_TRANSLATIONS.get(home_name, home_name)
            away_en = TEAM_TRANSLATIONS.get(away_name, away_name)
            
            # Кодируем пробелы для URL
            home_encoded = home_en.replace(" ", "%20")
            away_encoded = away_en.replace(" ", "%20")
            
            home_logo = f"{LOGO_BASE_URL}/{league_folder}/{home_encoded}.png"
            away_logo = f"{LOGO_BASE_URL}/{league_folder}/{away_encoded}.png"
        else:
            home_logo = ""
            away_logo = ""
        
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