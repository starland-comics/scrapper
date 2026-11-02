import asyncio
import time
import httpx
import json
import urllib.parse
from curl_cffi import requests as cffi_requests

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"

OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events?vids%5B%5D=1"
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events"

FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

BLACKLIST_WORDS = [
    "люб", "жен", "u21", "u19", "u20", "юнош", "молод", "угл", "жк", "кк",
    "статистика", "победитель группы", "лига a", "лига b", "лига c"
]

# Исключаем сборные (чтобы Комо не находил Коморы)
INTL_LEAGUE_WORDS = [
    "world cup", "euro ", "european championship", "nations",
    "copa america", "africa cup", "asian cup", "gold cup",
    "olympic", "friendly international", "confederations"
]

# ТОЛЬКО критичные команды (остальные найдет умный поиск)
TEAM_OVERRIDES = {
    "Байер 04": "Bayer Leverkusen",
    "Майнц 05": "Mainz",
    "Интер Милан": "Inter",
    "Комо": "Como",
    "Атлетик Бильбао": "Athletic Bilbao",
    "Спортинг Лиссабон": "Sporting CP",
    "Крылья Советов": "Krylia Sovetov",
    "Брюгге": "Club Brugge",
    "Кёльн": "Koln",
    "Факел": "Fakel Voronezh",
    "Рубин": "Rubin Kazan",
    "Енисей": "Yenisey",
    "Акрон": "Akron Tolyatti",
    "Родина": "Rodina Moscow",
    "Алавес": "Alaves",
    "Венеция": "Venezia",
    "Витория Гимарайнш": "Vitoria Guimaraes",
    "Витория БА": "Vitoria Setubal",
    "Виктория Пльзень": "Viktoria Plzen",
    "Юнион Сен-Жиллуаз": "Union St. Gilloise",
    "Дармштадт 98": "Darmstadt",
    "Торренсе": "Torrent",
    "Синт-Трёйден": "Sint-Truiden",
    "Аль-Кадисия Хубар": "Al-Qadsiah",
    "Аль-Шабаб Рияд": "Al-Shabab",
    "Аль-Наср Рияд": "Al-Nassr",
    "Аль-Хиляль Рияд": "Al-Hilal",
    "Аль-Ахли Джидда": "Al-Ahli",
    "Аль-Иттихад Джидда": "Al-Ittihad",
    "Аль-Иттифак": "Al-Ettifaq",
    "Аль-Таавун": "Al-Taawoun",
    "Аль-Фатех": "Al-Fateh",
    "Аль-Фейха": "Al-Fayha",
    "Аль-Фейсали Харма": "Al-Faisaly",
    "Аль-Хазм": "Al-Hazem",
    "Эстеглаль Тегеран": "Esteghlal",
    "Тэджон Ситизен": "Daejeon Citizen",
    "Чонбук": "Jeonbuk",
    "Штурм": "Sturm Graz",
    "Камбур": "Cambuur",
    "ВПР Астана": "Astana",
    "Хромтау": "Khromtau",
    "Кайсар": "Kaisar",
    "Нью-Йорк Ред Буллс": "New York Red Bulls",
    "Лос-Анджелес Гэлакси": "LA Galaxy",
    "Текстильщик Иваново": "Tekstilshchik",
    "Памплона": "Osasuna",
    "Анайтасуна": "Anaitasuna",
    "Саламанка УДС": "Salamanca UDS",
    "Реус Реддис": "Reus",
    "Волна Ковернино": "Volna",
    "Конган": "Khon Kaen",
    "Сабах Баку": "Sabah",
    "Истанбул Башакшехир": "Istanbul Basaksehir",
    "Унив. Крайова": "Universitatea Craiova",
    "Интер Эскальдес": "Inter Club d'Escaldes"
}

def is_valid_match(team1, team2, league):
    text = f"{team1} {team2} {league}".lower()
    for word in BLACKLIST_WORDS:
        if word in text:
            return False
    return True

def translate_ru_to_en(text):
    try:
        params = {"client": "gtx", "sl": "ru", "tl": "en", "dt": "t", "q": text}
        r = cffi_requests.get(TRANSLATE_URL, params=params, timeout=5)
        if r.status_code == 200:
            translated = r.json()[0][0][0]
            for w in [" FC", "FC ", " FK", "FK ", " CF", "CF "]:
                translated = translated.replace(w, "")
            return translated.strip()
    except Exception:
        pass
    return text

def search_fotmob_logo(team_name):
    # Если есть в override — используем его
    if team_name in TEAM_OVERRIDES:
        queries = [TEAM_OVERRIDES[team_name]]
    else:
        queries = [team_name, translate_ru_to_en(team_name)]
    
    seen = set()
    for q in queries:
        if q in seen: continue
        seen.add(q)
        try:
            url = f"{FOTMOB_SEARCH_URL}?term={urllib.parse.quote(q)}&lang=ru"
            r = cffi_requests.get(url, headers=FOTMOB_HEADERS, impersonate="chrome120", timeout=10)
            if r.status_code == 200:
                data = r.json()
                candidates = []
                for group in data:
                    for item in group.get("suggestions", []):
                        if item.get("type") != "team":
                            continue
                        league = (item.get("leagueName") or "").lower()
                        # Отсекаем сборные
                        if any(w in league for w in INTL_LEAGUE_WORDS):
                            continue
                        if not item.get("id"):
                            continue
                        candidates.append({
                            "id": item.get("id"),
                            "score": item.get("score", 0)
                        })
                
                if candidates:
                    # Берем клуб с самым высоким рейтингом FotMob
                    candidates.sort(key=lambda x: x["score"], reverse=True)
                    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{candidates[0]['id']}.png"
        except Exception:
            pass
    
    return ""

def fetch_olimp_matches(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    for attempt in range(2):
        try:
            r = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=120)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"   ⚠️ Попытка {attempt + 1}: {str(e)[:100]}")
            time.sleep(1)
    return []

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
            await client.put(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=60.0)
    except Exception:
        pass

async def search_all_logos(teams, cache):
    """Параллельный поиск логотипов (10 одновременно)"""
    sem = asyncio.Semaphore(10)
    
    async def search_one(team):
        async with sem:
            logo = await asyncio.to_thread(search_fotmob_logo, team)
            cache[team] = logo or ""
    
    tasks = [search_one(team) for team in teams]
    await asyncio.gather(*tasks)

async def main():
    print("🔄 [Scraper] Запуск...")
    
    logo_cache = await firebase_get("team_logos") or {}
    print(f"📥 В кэше логотипов: {len(logo_cache)}")

    print("📥 Загружаю LIVE...")
    live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
    
    print("📥 Загружаю ЛИНИЮ...")
    line_data = fetch_olimp_matches(OLIMP_LINE_URL)
    
    all_matches = []
    
    def parse_olimp_data(data, status_type):
        count = 0
        for sport_group in data:
            sport = sport_group.get("payload", {}).get("sport", {})
            if str(sport.get("id")) == "1":
                comps = sport_group.get("payload", {}).get("competitionsWithEvents", [])
                for comp in comps:
                    comp_name = comp.get("competition", {}).get("name", "Футбол")
                    for ev in comp.get("events", []):
                        t1 = ev.get("team1Name", "")
                        t2 = ev.get("team2Name", "")
                        if is_valid_match(t1, t2, comp_name):
                            all_matches.append((ev, status_type, comp_name))
                            count += 1
        return count

    live_count = parse_olimp_data(live_data, "LIVE")
    line_count = parse_olimp_data(line_data, "Скоро")

    print(f"⚽ LIVE: {live_count} | Скоро: {line_count}")
    
    # Debug: показываем структуру первого LIVE-матча
    if live_count > 0:
        sample = next((m for m in all_matches if m[1] == "LIVE"), None)
        if sample:
            ev = sample[0]
            print(f"   DEBUG LIVE keys: {list(ev.keys())[:15]}")
            print(f"   DEBUG score1={ev.get('score1')}, score2={ev.get('score2')}, time={ev.get('time')}")

    # Параллельный поиск логотипов
    missing_teams = set()
    for ev, _, _ in all_matches:
        t1 = ev.get("team1Name")
        t2 = ev.get("team2Name")
        if t1 and t1 not in logo_cache: missing_teams.add(t1)
        if t2 and t2 not in logo_cache: missing_teams.add(t2)

    if missing_teams:
        print(f"🔎 Параллельный поиск логотипов для {len(missing_teams)} команд...")
        t0 = time.time()
        await search_all_logos(missing_teams, logo_cache)
        found = sum(1 for t in missing_teams if logo_cache.get(t))
        print(f"✅ Найдено {found} / {len(missing_teams)} за {time.time()-t0:.1f}s")

    await firebase_put("team_logos", logo_cache)

    matches_dict = {}
    for ev, status_type, league_name in all_matches:
        ev_id = ev.get("id")
        t1 = ev.get("team1Name")
        t2 = ev.get("team2Name")
        
        p1, px, p2 = None, None, None
        for out in ev.get("outcomes", []):
            group_name = out.get("groupName", "")
            short_name = out.get("shortName", "")
            if "Исход" in group_name or "Результат" in group_name:
                if short_name in ["П1", "1"]: p1 = out.get("probability")
                elif short_name in ["X", "Х", "Ничья"]: px = out.get("probability")
                elif short_name in ["П2", "2"]: p2 = out.get("probability")

        score = "VS"
        status_str = status_type
        if status_type == "LIVE":
            # Перебираем все возможные ключи для счета и минуты
            score1 = ev.get("score1") or ev.get("liveScore1") or ev.get("result1") or ev.get("homeScore") or 0
            score2 = ev.get("score2") or ev.get("liveScore2") or ev.get("result2") or ev.get("awayScore") or 0
            score = f"{score1} : {score2}"
            
            minute = ev.get("time") or ev.get("liveTime") or ev.get("minute") or ev.get("currentMinute") or ""
            if minute:
                status_str = f"LIVE {minute}'"

        time_display = status_str
        if status_type == "Скоро":
            start_ts = ev.get("startDateTime")
            if start_ts:
                dt = time.localtime(start_ts)
                time_display = time.strftime("%d.%m %H:%M", dt)

        matches_dict[f"olimp_{ev_id}"] = {
            "title": f"{t1} - {t2}",
            "home": t1, "away": t2,
            "homeLogo": logo_cache.get(t1, ""),
            "awayLogo": logo_cache.get(t2, ""),
            "league": league_name,
            "status": time_display,
            "score": score,
            "start_time": ev.get("startDateTime"),
            "odds": {"1": p1, "X": px, "2": p2}
        }

    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей")

if __name__ == "__main__":
    asyncio.run(main())