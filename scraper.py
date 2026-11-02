import asyncio
import time
import httpx
import json
import urllib.parse
from curl_cffi import requests as cffi_requests

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"

# ФУТБОЛ = vids[]=1. Для лайва работает, для линии - нет (выдает 400)
OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events?vids%5B%5D=1"
# ДЛЯ ЛИНИИ УБИРАЕМ vids, чтобы не было 400
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events"

FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

# СЛОВАРЬ ТОЧНЫХ НАЗВАНИЙ (ВСЕ КЛУБЫ ИЗ ТВОЕГО СПИСКА)
TEAM_OVERRIDES = {
    "Байер 04": "Bayer Leverkusen",
    "Майнц 05": "Mainz",
    "Интер Милан": "Inter",
    "Комо": "Como",
    "Атлетик Бильбао": "Athletic Bilbao",
    "Флитвуд Таун": "Fleetwood Town",
    "Суонси Сити": "Swansea City",
    "Рексэм": "Wrexham",
    "Кардифф Сити": "Cardiff City",
    "Виктория БА": "Viktoria Plzen",
    "Эльферсберг": "Elversberg",
    "Унион Берлин": "Union Berlin",
    "Шальке 04": "Schalke 04",
    "Хольштайн Киль": "Holstein Kiel",
    "Левски София": "Levski Sofia",
    "Неймеген": "NEC Nijmegen",
    "Юнион Сен-Жиллуаз": "Union St. Gilloise",
    "Арарат-Армения": "Ararat-Armenia",
    "Хапоэль Беэр-Шева": "Hapoel Be'er Sheva",
    "Лех Познан": "Lech Poznan",
    "Линкольн Ред Импс": "Lincoln Red Imps",
    "Хайдук Сплит": "Hajduk Split",
    "Интер Эскальдес": "Inter Club d'Escaldes",
    "Мьельбю": "Mjallby",
    "Унив. Крайова": "Universitatea Craiova",
    "Эгнатия": "Egnatia",
    "Иберия 1999": "Iberia 1999",
    "Синт-Трёйден": "Sint-Truiden",
    "Кауно Жальгирис": "Kauno Zalgiris",
    "Аль-Сиб": "Al-Sib",
    "Аль-Шорта": "Al-Shorta",
    "Аль-Кадисия Хубар": "Al-Qadsiah",
    "Шанхай Порт": "Shanghai Port",
    "Джохор Дарул Такзим": "Johor Darul Ta'zim",
    "Конган": "Khon Kaen",
    "Кёто Санга": "Kyoto Sanga",
    "Порт": "Porto",
    "Эстеглаль Тегеран": "Esteghlal",
    "Аль-Шамаль": "Al-Shamal",
    "Аль-Хиляль Рияд": "Al-Hilal",
    "Шабаб Аль-Ахли Дубай": "Shabab Al-Ahli",
    "Шахтёр Донецк": "Shakhtar Donetsk",
    "Спортинг Лиссабон": "Sporting CP",
    "Слован Братислава": "Slovan Bratislava",
    "Сабах Баку": "Sabah",
    "ПСВ Эйндховен": "PSV",
    "Спарта Роттердам": "Sparta Rotterdam",
    "Алверка": "Alverca",
    "Виктория Гимарайнш": "Vitoria Guimaraes",
    "Каза Пиа": "Casa Pia",
    "Эштрелла Амадора": "Estrela Amadora",
    "Волна Ковернино": "Volna",
    "Волга Ульяновск": "Volga Ulyanovsk",
    "Динамо Махачкала": "Dinamo Makhachkala",
    "Локомотив Москва": "Lokomotiv Moscow",
    "Родина": "Rodina Moscow",
    "Акрон": "Akron Tolyatti",
    "ЦСКА Москва": "CSKA Moscow",
    "Спартак Москва": "Spartak Moscow",
    "Динамо Москва": "Dinamo Moscow",
    "Арсенал Тула": "Arsenal Tula",
    "Торпедо Москва": "Torpedo Moscow",
    "Текстильщик Иваново": "Tekstilshchik",
    "Велес Москва": "Veles",
    "Аль-Холуд": "Al-Kholood",
    "Аль-Халидж": "Al-Khaleej",
    "Абха": "Abha",
    "Аль-Шабаб Рияд": "Al-Shabab",
    "Аль-Рияд": "Al-Riyadh",
    "Аль-Наср Рияд": "Al-Nassr",
    "Неом": "Neom",
    "Аль-Дирийя": "Al-Diriyah",
    "ДС Юнайтед": "DC United",
    "Нью-Йорк Ред Буллс": "New York Red Bulls",
    "Атланта Юнайтед": "Atlanta United",
    "Интер Майами": "Inter Miami",
    "Нью-Ингланд Революшн": "New England Revolution",
    "Филадельфия Юнион": "Philadelphia Union",
    "Ванкувер Уайткэпс": "Vancouver Whitecaps",
    "Колорадо Рэпидс": "Colorado Rapids",
    "Сан-Диего": "San Diego FC",
    "Лос-Анджелес Гэлакси": "LA Galaxy",
    "Остин": "Austin FC",
    "Миннесота Юнайтед": "Minnesota United",
    "Сан-Хосе Эрктвейкс": "San Jose Earthquakes",
    "Сент-Луис Сити": "St. Louis City",
    "Коджаелиспор": "Kocaelispor",
    "Амедспор": "Amedspor",
    "Истанбул Башакшехир": "Istanbul Basaksehir",
    "Эрзурумспор": "Erzurumspor",
    "Чурум": "Corum",
    "Альянспор": "Alyanspor"
}

BLACKLIST_WORDS = ["люб", "жен", "u21", "u19", "u20", "юнош", "молод", "угл", "жк", "кк", "статистика"]

def is_valid_match(team1, team2, league):
    text = f"{team1} {team2} {league}".lower()
    for word in BLACKLIST_WORDS:
        if word in text:
            return False
    return True

def search_fotmob_logo(team_name):
    search_query = TEAM_OVERRIDES.get(team_name, team_name)
    try:
        url = f"{FOTMOB_SEARCH_URL}?term={urllib.parse.quote(search_query)}&lang=ru"
        r = cffi_requests.get(url, headers=FOTMOB_HEADERS, impersonate="chrome120", timeout=10)
        if r.status_code == 200:
            data = r.json()
            for group in data:
                for item in group.get("suggestions", []):
                    if item.get("type") == "team":
                        team_id = item.get("id")
                        if team_id:
                            return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
    except Exception:
        pass
    return ""

def fetch_olimp_matches(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    
    for attempt in range(3):
        try:
            print(f"   Попытка {attempt + 1}/3...")
            # УВЕЛИЧЕН ТАЙМАУТ ДО 120 СЕКУНД
            r = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=120)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"   ⚠️ Статус {r.status_code}")
        except Exception as e:
            print(f"   ⚠️ Ошибка попытки {attempt + 1}: {str(e)[:150]}")
            time.sleep(3)
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

async def main():
    print("🔄 [Scraper] Запуск...")
    
    logo_cache = await firebase_get("team_logos") or {}
    print(f"📥 В кэше логотипов: {len(logo_cache)}")

    print("📥 Загружаю LIVE с Olimpbet...")
    live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
    print(f"   Получено групп: {len(live_data) if live_data else 0}")
    
    print("📥 Загружаю ЛИНИЮ с Olimpbet (ожидание до 2 минут)...")
    line_data = fetch_olimp_matches(OLIMP_LINE_URL)
    print(f"   Получено групп: {len(line_data) if line_data else 0}")
    
    all_matches = []
    
    def parse_olimp_data(data, status_type):
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

    parse_olimp_data(live_data, "LIVE")
    parse_olimp_data(line_data, "Скоро")

    print(f"⚽ Найдено валидных матчей: {len(all_matches)}")

    missing_teams = set()
    for ev, _, _ in all_matches:
        t1 = ev.get("team1Name")
        t2 = ev.get("team2Name")
        if t1 and t1 not in logo_cache: missing_teams.add(t1)
        if t2 and t2 not in logo_cache: missing_teams.add(t2)

    if missing_teams:
        print(f"🔎 Ищу логотипы в FotMob для {len(missing_teams)} команд...")
        for team in missing_teams:
            logo = await asyncio.to_thread(search_fotmob_logo, team)
            if logo:
                logo_cache[team] = logo
                print(f"   ✅ {team}")
            else:
                logo_cache[team] = ""
                print(f"   ⚠️ {team} (не найдено)")
            await asyncio.sleep(0.1)

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
            score1 = ev.get("score1", ev.get("liveScore1", 0))
            score2 = ev.get("score2", ev.get("liveScore2", 0))
            score = f"{score1} : {score2}"
            
            minute = ev.get("time", ev.get("liveTime", ""))
            if minute:
                status_str = f"LIVE {minute}'"
            else:
                status_str = "LIVE"

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
        print(f"🔥 Успешно сохранено {len(matches_dict)} матчей в Firebase!")
    else:
        print("⚠️ Матчей не найдено.")

if __name__ == "__main__":
    asyncio.run(main())