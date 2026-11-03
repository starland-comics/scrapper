import asyncio
import time
import httpx
import json
import urllib.parse
import os
import hashlib
import base64
from curl_cffi import requests as cffi_requests
from rapidfuzz import fuzz

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events?vids%5B%5D=1"
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events"
# Эндпоинт результатов (может потребовать доработки, если Olimpbet его поменяет)
OLIMP_RESULTS_URL = "https://www.olimp.bet/api/v4/0/results/sports-with-competitions-with-events"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

BLACKLIST_WORDS = [
    "люб", "жен", "u21", "u19", "u20", "юнош", "молод", "мол", "до 19", "до 21", "до 23", "дубл", "резерв", "академ",
    "угл", "жк", "кк", "статистика", "победитель группы", "лига a", "лига b", "лига c",
    "видеопросмотр", "удары от ворот", "удары в створ", "удары по воротам", "штанги", "перекладины",
    "ауты", "офсайды", "фолы", "голы", "мед. бригад", "хозяева", "гости", "тотал", "фора",
    "обе забьют", "пенальти", "карточк"
]

INTL_LEAGUE_WORDS = [
    "world cup", "euro ", "european championship", "nations",
    "copa america", "africa cup", "asian cup", "gold cup",
    "olympic", "friendly international", "confederations"
]

COUNTRY_NAMES = {
    "russia", "germany", "france", "italy", "spain", "england", "portugal",
    "brazil", "argentina", "tunisia", "thailand", "switzerland", "austria",
    "belgium", "netherlands", "croatia", "serbia", "greece", "turkey",
    "japan", "korea", "china", "india", "australia", "mexico", "usa",
    "canada", "morocco", "egypt", "saudi arabia", "uae", "qatar", "iran",
    "iraq", "uzbekistan", "kazakhstan", "ukraine", "poland", "czech",
    "slovakia", "hungary", "romania", "bulgaria", "denmark", "norway",
    "sweden", "finland", "iceland", "ireland", "scotland", "wales",
    "россия", "германия", "франция", "италия", "испания",
    "англия", "португалия", "бразилия", "аргентина", "тунис", "таиланд",
    "швейцария", "австрия", "бельгия", "нидерланды", "хорватия", "сербия",
    "греция", "турция", "япония", "корея", "китай", "индия", "австралия",
    "мексика", "сша", "канада", "марокко", "египет", "саудовская аравия",
    "оаэ", "катар", "иран", "ирак", "узбекистан", "казахстан", "украина",
    "польша", "чехия", "словакия", "венгрия", "румыния", "болгария",
    "дания", "норвегия", "швеция", "финляндия", "исландия", "ирландия",
    "шотландия", "уэльс",
}

FOTMOB_ID_OVERRIDES = {
    "Порт": 165255, "Порт ФК": 165255, "Порту": 9775,
    "Тун": 10191, "Акрон": 1068364, "Акрон Тольятти": 1068364,
    "Родина": 1066681, "Родина Москва": 1066681,
    "Истанбул Башакшехир": 10068,
    "Атлетик Бильбао": 9807,
    "Синт-Трёйден": 10232,
    "Эштрела Амадора": 14303,
    "Витория Гимарайнш": 9778,
    "Витория БА": 9779,
    "Нью-Йорк Ред Буллс": 9805,
}

DIRECT_LOGO_URLS = {
    "Харборо Таун": "https://www.footylogos.com/dls/logo/rgba-v1/harborough-town.png",
    "Солсбери": "https://www.footylogos.com/dls/logo/rgba-v1/salisbury.png",
    "Алвчерч": "https://www.footylogos.com/dls/logo/rgba-v1/alvechurch.png",
    "Стаффорд Рейнджерс": "https://www.footylogos.com/dls/logo/rgba-v1/stafford-rangers.png",
    "Вустер Сити": "https://www.footylogos.com/dls/logo/rgba-v1/worcester-city.png",
    "Йовил Таун": "https://www.footylogos.com/dls/logo/rgba-v1/yeovil-town.png",
    "Олтринчэм": "https://www.footylogos.com/dls/logo/rgba-v1/altrincham.png",
    "Хорнчерч": "https://www.footylogos.com/dls/logo/rgba-v1/hornchurch.png",
    "Рашден & Даймондс": "https://www.footylogos.com/dls/logo/rgba-v1/afc-rushden-diamonds.png",
    "Галифакс Таун": "https://www.footylogos.com/dls/logo/rgba-v1/fc-halifax-town.png",
    "Анайтасуна": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8a/CD_Anaitasuna_logo.png/180px-CD_Anaitasuna_logo.png",
}

TEAM_OVERRIDES = {
    "Байер 04": "Bayer Leverkusen", "Майнц 05": "Mainz", "Интер Милан": "Inter",
    "Комо": "Como", "Атлетик Бильбао": "Athletic Bilbao", "Спортинг Лиссабон": "Sporting CP",
    "Крылья Советов": "Krylia Sovetov", "Брюгге": "Club Brugge", "Кёльн": "Koln",
    "Факел": "Fakel Voronezh", "Рубин": "Rubin Kazan", "Енисей": "Yenisey",
    "Акрон": "Akron Tolyatti", "Родина": "Rodina Moscow", "Алавес": "Alaves",
    "Венеция": "Venezia", "Витория Гимарайнш": "Vitoria Guimaraes", "Витория БА": "Vitoria Setubal",
    "Виктория Пльзень": "Viktoria Plzen", "Юнион Сен-Жиллуаз": "Union St. Gilloise",
    "Дармштадт 98": "Darmstadt", "Торренсе": "Torrent", "Синт-Трёйден": "Sint-Truiden",
    "Аль-Кадисия Хубар": "Al-Qadsiah", "Аль-Шабаб Рияд": "Al-Shabab", "Аль-Наср Рияд": "Al-Nassr",
    "Аль-Хиляль Рияд": "Al-Hilal", "Аль-Ахли Джидда": "Al-Ahli", "Аль-Иттихад Джидда": "Al-Ittihad",
    "Аль-Иттифак": "Al-Ettifaq", "Аль-Таавун": "Al-Taawoun", "Аль-Фатех": "Al-Fateh",
    "Аль-Фейха": "Al-Fayha", "Аль-Фейсали Харма": "Al-Faisaly", "Аль-Хазм": "Al-Hazem",
    "Эстеглаль Тегеран": "Esteghlal", "Тэджон Ситизен": "Daejeon Citizen", "Чонбук": "Jeonbuk",
    "Штурм": "Sturm Graz", "Камбур": "Cambuur", "ВПР Астана": "Astana", "Хромтау": "Khromtau",
    "Кайсар": "Kaisar", "Нью-Йорк Ред Буллс": "New York Red Bulls", "Лос-Анджелес Гэлакси": "LA Galaxy",
    "Текстильщик Иваново": "Tekstilshchik", "Памплона": "Osasuna", "Анайтасуна": "Anaitasuna",
    "Саламанка УДС": "Salamanca UDS", "Реус Реддис": "Reus", "Волна Ковернино": "Volna",
    "Конган": "Khon Kaen", "Сабах Баку": "Sabah", "Истанбул Башакшехир": "Istanbul Basaksehir",
    "Унив. Крайова": "Universitatea Craiova", "Интер Эскальдес": "Inter Club d'Escaldes",
    "Эштрела Амадора": "Estrela Amadora",
    "Солсбери": "Salisbury FC", "Алвчерч": "Alvechurch FC", "Йовил Таун": "Yeovil Town",
    "Галифакс Таун": "FC Halifax Town", "Таранкон": "Tarazona", "Стаффорд Рейнджерс": "Stafford Rangers",
    "Вустер Сити": "Worcester City", "Рашден & Даймондс": "AFC Rushden & Diamonds",
    "Хорнчерч": "Hornchurch", "Олтринчэм": "Altrincham", "Харборо Таун": "Harborough Town",
}

LEAGUE_COUNTRY_HINTS = {
    "португал": "portugal", "таиланд": "thailand", "тай": "thailand", "англ": "england",
    "испан": "spain", "итал": "italy", "герман": "germany", "франц": "france",
    "бразил": "brazil", "аргентин": "argentina", "турц": "turkey", "росси": "russia",
    "украин": "ukraine", "казах": "kazakhstan", "нидерланд": "netherlands", "голланд": "netherlands",
    "бельги": "belgium", "швейцар": "switzerland", "австри": "austria", "польш": "poland",
    "чехи": "czech", "хорват": "croatia", "серби": "serbia", "грец": "greece",
    "израил": "israel", "египет": "egypt", "саудов": "saudi", "эмират": "uae",
    "япон": "japan", "корея": "korea", "китай": "china", "инди": "india",
    "австрал": "australia", "мексик": "mexico", "сша": "usa", "америк": "usa",
    "шотланд": "scotland", "ирланд": "ireland", "дания": "denmark", "норвег": "norway",
    "швец": "sweden", "финлянд": "finland", "румын": "romania", "болгар": "bulgaria",
    "венгр": "hungary", "словен": "slovenia", "словак": "slovakia", "азерб": "azerbaijan",
    "армен": "armenia", "грузи": "georgia", "узбек": "uzbekistan", "киргиз": "kyrgyzstan",
    "таджик": "tajikistan"
}

LOGO_STATS = {"fotmob": 0, "thesportsdb": 0, "direct": 0, "fallback": 0, "cache": 0}
FALLBACK_TEAMS = []

def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    for w in (" fc", " cf", " sc", " ac", " fk", " afc", " club", " фк", " клуб"):
        s = s.replace(w, "").strip()
    return s

def is_valid_match(team1, team2, league):
    text = f"{team1} {team2} {league}".lower()
    for word in BLACKLIST_WORDS:
        if word in text:
            return False
    return True

def league_to_country(comp_name: str) -> str | None:
    if not comp_name: return None
    low = comp_name.lower()
    for marker, country in LEAGUE_COUNTRY_HINTS.items():
        if marker in low: return country
    return None

def is_national_team(name: str, league: str = "") -> bool:
    n = _normalize(name)
    l = (league or "").lower()
    if n in COUNTRY_NAMES: return True
    if any(w in l for w in ("national", "international", "world cup", "euro ", "nations")): return True
    if "сборная" in n or "national" in n: return True
    return False

def make_fallback_logo(name: str) -> str:
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    color = "#" + hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
           f'<rect width="80" height="80" rx="16" fill="{color}"/>'
           f'<text x="40" y="52" font-size="26" text-anchor="middle" fill="white" '
           f'font-family="Arial,sans-serif" font-weight="700">{initials}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

def _is_fallback(logo: str) -> bool:
    return isinstance(logo, str) and logo.startswith("data:image/svg")

def _encode_key(k: str) -> str:
    if not k: return "_"
    return "b64_" + base64.urlsafe_b64encode(k.encode("utf-8")).decode("ascii").rstrip("=")

def _decode_key(k: str) -> str:
    if k and isinstance(k, str) and k.startswith("b64_"):
        try:
            padding = "=" * (-len(k[4:]) % 4)
            return base64.urlsafe_b64decode(k[4:] + padding).decode("utf-8")
        except Exception:
            return k
    return k

def _cache_to_fb(cache: dict) -> dict:
    return {_encode_key(k): v for k, v in cache.items() if k and v}

def _cache_from_fb(raw) -> dict:
    if not raw or not isinstance(raw, dict): return {}
    return {_decode_key(k): v for k, v in raw.items()}

def batch_translate_ru_to_en(texts: list[str]) -> dict[str, str]:
    if not texts: return {}
    result = {}
    for i in range(0, len(texts), 40):
        chunk = texts[i:i+40]
        SEP = " | "
        joined = SEP.join(chunk)
        try:
            params = {"client": "gtx", "sl": "ru", "tl": "en", "dt": "t", "q": joined}
            r = cffi_requests.get(TRANSLATE_URL, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                segments = data[0] if data and data[0] else []
                translated_full = "".join(seg[0] for seg in segments if seg and seg[0])
                parts = [p.strip() for p in translated_full.split("|")]
                if len(parts) == len(chunk):
                    for orig, trans in zip(chunk, parts):
                        for w in [" FC", "FC ", " FK", "FK ", " CF", "CF "]:
                            trans = trans.replace(w, "")
                        result[orig] = trans.strip() or orig
                else:
                    for t in chunk: result[t] = t
            else:
                for t in chunk: result[t] = t
        except Exception:
            for t in chunk: result[t] = t
    return result

def pick_best_candidate(cands, target_name, country_hint):
    if not cands: return None
    cands = [c for c in cands if not is_national_team(c.get("name", ""), c.get("league", ""))]
    if not cands: return None

    target = _normalize(target_name)
    country_hint = (country_hint or "").lower()

    def base_score(c):
        return fuzz.token_set_ratio(target, _normalize(c.get("name", ""))) * 10 + min(c.get("score", 0), 200)

    if country_hint:
        matching = [c for c in cands if country_hint in (c.get("league") or "").lower() or country_hint in (c.get("country") or "").lower()]
        if matching:
            return max(matching, key=base_score)

    return max(cands, key=base_score)

def search_fotmob_candidates(team_name: str, name_en: str) -> list[dict]:
    queries = [name_en, team_name]
    seen, out = set(), []
    for q in queries:
        if not q or q in seen: continue
        seen.add(q)
        try:
            url = f"{FOTMOB_SEARCH_URL}?term={urllib.parse.quote(q)}&lang=ru"
            r = cffi_requests.get(url, headers=FOTMOB_HEADERS, impersonate="chrome120", timeout=10)
            if r.status_code != 200: continue
            for group in r.json():
                for item in group.get("suggestions", []):
                    if item.get("type") != "team": continue
                    league_name = (item.get("leagueName") or "").lower()
                    if any(w in league_name for w in INTL_LEAGUE_WORDS): continue
                    if not item.get("id"): continue
                    out.append({
                        "id": item["id"], "name": item.get("name", ""),
                        "league": league_name, "score": item.get("score", 0),
                        "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{item['id']}.png",
                        "source": "fotmob",
                    })
        except Exception:
            pass
    return out

async def search_thesportsdb(name_en: str) -> list[dict]:
    variants = [name_en, f"{name_en} FC", f"FC {name_en}", f"{name_en} AFC", f"AFC {name_en}"]
    seen, out = set(), []
    for q in variants:
        if q in seen: continue
        seen.add(q)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://www.thesportsdb.com/api/v1/json/3/searchteams.php", params={"t": q})
                if r.status_code != 200: continue
                for t in (r.json() or {}).get("teams") or []:
                    if not t.get("strBadge"): continue
                    sport = (t.get("strSport") or "").lower()
                    if sport and sport != "soccer": continue
                    if "national" in (t.get("strTeam") or "").lower(): continue
                    out.append({"name": t.get("strTeam", ""), "league": (t.get("strLeague") or "").lower(),
                                "country": (t.get("strCountry") or "").lower(), "logo": t.get("strBadge"), "source": "thesportsdb"})
        except Exception:
            continue
    return out

async def resolve_logo(team_ru: str, comp_name: str, cache: dict, name_en_map: dict, force_refresh: bool = False) -> str:
    country = league_to_country(comp_name) or ""
    key = f"{team_ru}|{country}"

    if not force_refresh:
        for existing_key in (key, team_ru):
            existing = cache.get(existing_key)
            if existing and not _is_fallback(existing):
                LOGO_STATS["cache"] += 1
                return existing

    direct = DIRECT_LOGO_URLS.get(team_ru)
    if direct:
        cache[key] = direct; LOGO_STATS["direct"] += 1
        return direct

    fid = FOTMOB_ID_OVERRIDES.get(team_ru)
    if fid:
        logo = f"https://images.fotmob.com/image_resources/logo/teamlogo/{fid}.png"
        cache[key] = logo; LOGO_STATS["fotmob"] += 1
        return logo

    name_en = TEAM_OVERRIDES.get(team_ru) or name_en_map.get(team_ru) or team_ru
    best = pick_best_candidate(search_fotmob_candidates(team_ru, name_en), name_en, country)
    if best and best.get("logo"):
        cache[key] = best["logo"]; LOGO_STATS["fotmob"] += 1
        return best["logo"]

    best = pick_best_candidate(await search_thesportsdb(name_en), name_en, country)
    if best and best.get("logo"):
        cache[key] = best["logo"]; LOGO_STATS["thesportsdb"] += 1
        return best["logo"]

    fb = make_fallback_logo(team_ru)
    cache[key] = fb
    LOGO_STATS["fallback"] += 1
    FALLBACK_TEAMS.append(team_ru)
    return fb

async def search_all_logos(teams_with_league: list, cache: dict, name_en_map: dict):
    sem = asyncio.Semaphore(10)
    async def one(team, league, force):
        async with sem:
            try:
                await resolve_logo(team, league, cache, name_en_map, force_refresh=force)
            except Exception:
                hint = league_to_country(league) or ""
                cache[f"{team}|{hint}"] = make_fallback_logo(team)
                LOGO_STATS["fallback"] += 1
                FALLBACK_TEAMS.append(team)
    await asyncio.gather(*(one(t, l, f) for t, l, f in teams_with_league))

def fetch_olimp_matches(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
    for attempt in range(2):
        try:
            r = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=120)
            if r.status_code == 200: return r.json()
        except Exception:
            time.sleep(1)
    return []

def extract_live_score_and_time(ev: dict):
    score = None; minute = None
    sc = ev.get("score")
    if isinstance(sc, dict):
        s1 = sc.get("team1") or sc.get("home") or sc.get("score1")
        s2 = sc.get("team2") or sc.get("away") or sc.get("score2")
        if s1 is not None and s2 is not None: score = f"{s1} : {s2}"
    elif isinstance(sc, str) and ":" in sc: score = sc

    if not score:
        s1 = ev.get("score1") or ev.get("homeScore") or ev.get("team1Score")
        s2 = ev.get("score2") or ev.get("awayScore") or ev.get("team2Score")
        if s1 is not None and s2 is not None: score = f"{s1} : {s2}"

    t = ev.get("time")
    if isinstance(t, dict): minute = t.get("minute") or t.get("current") or t.get("elapsed")
    elif isinstance(t, (int, str)): minute = t
    if not minute: minute = ev.get("minute") or ev.get("currentMinute") or ev.get("liveTime")
    return score, str(minute) if minute is not None else None

async def fetch_finished_matches():
    print("📥 Загружаю РЕЗУЛЬТАТЫ матчей...")
    results_data = fetch_olimp_matches(OLIMP_RESULTS_URL)
    
    finished_dict = {}
    if results_data:
        for sport_group in results_data:
            sport = sport_group.get("payload", {}).get("sport", {})
            if str(sport.get("id")) == "1": # Футбол
                comps = sport_group.get("payload", {}).get("competitionsWithEvents", [])
                for comp in comps:
                    for ev in comp.get("events", []):
                        ev_id = ev.get("id")
                        s1 = ev.get("score1") or ev.get("homeScore") or 0
                        s2 = ev.get("score2") or ev.get("awayScore") or 0
                        if ev_id:
                            finished_dict[f"olimp_{ev_id}"] = {"score1": s1, "score2": s2}
                            
    if finished_dict:
        print(f"✅ Найдено {len(finished_dict)} результатов.")
        try:
            async with httpx.AsyncClient() as client:
                await client.patch(f"{FIREBASE_DB_URL}/finished_matches.json", json=finished_dict, timeout=30.0)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения результатов: {e}")
    else:
        print("⚠️ Результаты не найдены. Возможно, эндпоинт Olimpbet изменился.")

async def firebase_get(path):
    try:
        async with httpx.AsyncClient() as client:
            return (await client.get(f"{FIREBASE_DB_URL}/{path}.json", timeout=15.0)).json()
    except Exception: return None

async def firebase_put(path, data):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=60.0)
            return r.status_code == 200
    except Exception: return False

async def main():
    print("🔄 [Scraper] Запуск...")
    raw_cache = await firebase_get("team_logos") or {}
    logo_cache = _cache_from_fb(raw_cache)
    print(f"📥 В кэше логотипов: {len(logo_cache)} (в Firebase: {len(raw_cache)})")

    print("📥 Загружаю LIVE...")
    live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
    
    if not live_data:
        print("   ⚠️ Olimpbet вернул пустой ответ для LIVE. Возможно, блокировка или смена API.")
    else:
        sports_found = []
        for item in live_data:
            sport = item.get("payload", {}).get("sport", {})
            comps = item.get("payload", {}).get("competitionsWithEvents", [])
            events_count = sum(len(c.get("events", [])) for c in comps)
            sports_found.append(f"ID={sport.get('id')} ({sport.get('name')}) - {events_count} событий")
        print(f"   🔍 LIVE API вернул виды спорта: {', '.join(sports_found)}")

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
                        if t1 and t2 and is_valid_match(t1, t2, comp_name):
                            all_matches.append((ev, status_type, comp_name))
                            count += 1
        return count

    live_count = parse_olimp_data(live_data, "LIVE")
    line_count = parse_olimp_data(line_data, "Скоро")
    print(f"⚽ LIVE: {live_count} | Скоро: {line_count}")

    missing = set()
    for ev, _, league_name in all_matches:
        for t in (ev.get("team1Name"), ev.get("team2Name")):
            if not t: continue
            hint = league_to_country(league_name) or ""
            existing = logo_cache.get(f"{t}|{hint}") or logo_cache.get(t)
            force = (t in FOTMOB_ID_OVERRIDES) or (t in DIRECT_LOGO_URLS) or (not existing) or _is_fallback(existing)
            if force: missing.add((t, league_name, force))

    if missing:
        print(f"🔎 Поиск логотипов для {len(missing)} пар (team, league)...")
        all_teams = list({t for t, _, _ in missing})
        name_en_map = batch_translate_ru_to_en(all_teams)

        t0 = time.time()
        await search_all_logos(list(missing), logo_cache, name_en_map)
        print(f"✅ Обработано {len(missing)} за {time.time()-t0:.1f}s")
        print(f"📊 Источники: fotmob={LOGO_STATS['fotmob']}, thesportsdb={LOGO_STATS['thesportsdb']}, direct={LOGO_STATS['direct']}, fallback={LOGO_STATS['fallback']}, cache={LOGO_STATS['cache']}")

    payload = _cache_to_fb(logo_cache)
    ok = await firebase_put("team_logos", payload)
    print(f"💾 Кэш логотипов: {len(logo_cache)} записей, ok={ok}")

    if FALLBACK_TEAMS:
        print(f"🚨 БЕЗ ЛОГОТИПОВ: {list(set(FALLBACK_TEAMS))}")

    matches_dict = {}
    for ev, status_type, league_name in all_matches:
        ev_id = ev.get("id")
        t1 = ev.get("team1Name"); t2 = ev.get("team2Name")
        hint = league_to_country(league_name) or ""
        home_logo = logo_cache.get(f"{t1}|{hint}") or logo_cache.get(t1, "")
        away_logo = logo_cache.get(f"{t2}|{hint}") or logo_cache.get(t2, "")

        p1 = px = p2 = None
        for out in ev.get("outcomes", []):
            group_name = out.get("groupName", ""); short_name = out.get("shortName", "")
            if "Исход" in group_name or "Результат" in group_name:
                if short_name in ["П1", "1"]: p1 = out.get("probability")
                elif short_name in ["X", "Х", "Ничья"]: px = out.get("probability")
                elif short_name in ["П2", "2"]: p2 = out.get("probability")

        score = "VS"
        status_str = status_type
        if status_type == "LIVE":
            extracted_score, extracted_minute = extract_live_score_and_time(ev)
            if extracted_score: score = extracted_score
            if extracted_minute: status_str = f"LIVE {extracted_minute}'"

        time_display = status_str
        if status_type == "Скоро":
            start_ts = ev.get("startDateTime")
            if start_ts:
                dt = time.localtime(start_ts)
                time_display = time.strftime("%d.%m %H:%M", dt)

        matches_dict[f"olimp_{ev_id}"] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": home_logo, "awayLogo": away_logo,
            "league": league_name, "status": time_display, "score": score,
            "start_time": ev.get("startDateTime"),
            "odds": {"1": p1, "X": px, "2": p2}
        }

    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей")

    await fetch_finished_matches()

if __name__ == "__main__":
    asyncio.run(main())