import asyncio
import time
import httpx
import json
import urllib.parse
import os
import re
import hashlib
import base64
from curl_cffi import requests as cffi_requests
from rapidfuzz import fuzz

DO_RECON = os.environ.get("DO_RECON", "0") == "1"

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/sports-with-competitions-with-events"
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events"
OLIMP_RESULTS_URL = "https://www.olimp.bet/api/v4/0/results/sports-with-competitions-with-events"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

BLACKLIST_WORDS = [
    "люб", "жен", "мол", "дубл", "резерв", "академ",
    "до 15", "до 16", "до 17", "до 18", "до 19", "до 20", "до 21", "до 23",
    "u15", "u16", "u17", "u18", "u19", "u20", "u21", "u23",
    "угл", "жк", "кк", "статистика", "победитель группы", "лига a", "лига b", "лига c",
    "видеопросмотр", "удары от ворот", "удары в створ", "удары по воротам", "штанги", "перекладины",
    "ауты", "офсайды", "фолы", "голы", "мед. бригад", "хозяева", "гости", "тотал", "фора",
    "обе забьют", "пенальти", "карточк"
]

ALLOWED_LEAGUES = [
    "испан", "франц", "англ", "итал", "герман", 
    "португал", "нидерланд", "голланд", "бразил", 
    "росси", "украин", "казах", "саудов", "турц", 
    "сша", "mls",
    "чемпионов", "европы", "конференций", "суперкубок",
    "сборная", "сборных", "мира", "евро", "наций", 
    "отбор", "товарищеск", "копа", "кубок азии", "кубок африки"
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
    "Истанбул Башакшехир": 10068, "Атлетик Бильбао": 9807,
    "Синт-Трёйден": 10232, "Эштрела Амадора": 14303,
    "Витория Гимарайнш": 9778, "Витория БА": 9779,
    "Нью-Йорк Ред Буллс": 9805, "Саламанка УДС": 82679,
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
    "Хромтау": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/FC_Khromtau_logo.png/180px-FC_Khromtau_logo.png",
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
    "Аль-Нахда Бурайми": "Al-Nahda Buraimi", "Аль-Вахда Абу-Даби": "Al Wahda Abu Dhabi",
    "Аль-Файсали Амман": "Al Faisaly Amman", "Аль-Джазира Абу-Даби": "Al Jazira Abu Dhabi",
    "Аль-Мухаррак": "Al-Muharraq",
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

def _normalize(s):
    s = (s or "").lower().strip()
    for w in (" fc", " cf", " sc", " ac", " fk", " afc", " club", " фк", " клуб"):
        s = s.replace(w, "").strip()
    return s

def is_valid_match(team1, team2, league):
    text = f"{team1} {team2} {league}".lower()
    if any(word in text for word in BLACKLIST_WORDS): return False
    if not any(allowed in league.lower() for allowed in ALLOWED_LEAGUES): return False
    return True

def league_to_country(comp_name):
    if not comp_name: return None
    low = comp_name.lower()
    for marker, country in LEAGUE_COUNTRY_HINTS.items():
        if marker in low: return country
    return None

def is_national_team(name, league=""):
    n = _normalize(name); l = (league or "").lower()
    if n in COUNTRY_NAMES: return True
    if any(w in l for w in ("national", "international", "world cup", "euro ", "nations")): return True
    if "сборная" in n or "national" in n: return True
    return False

def make_fallback_logo(name):
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    color = "#" + hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
           f'<rect width="80" height="80" rx="16" fill="{color}"/>'
           f'<text x="40" y="52" font-size="26" text-anchor="middle" fill="white" '
           f'font-family="Arial,sans-serif" font-weight="700">{initials}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

def _is_fallback(logo):
    return isinstance(logo, str) and logo.startswith("data:image/svg")

def _encode_key(k):
    if not k: return "_"
    return "b64_" + base64.urlsafe_b64encode(k.encode("utf-8")).decode("ascii").rstrip("=")

def _decode_key(k):
    if k and isinstance(k, str) and k.startswith("b64_"):
        try:
            padding = "=" * (-len(k[4:]) % 4)
            return base64.urlsafe_b64decode(k[4:] + padding).decode("utf-8")
        except Exception: return k
    return k

def _cache_to_fb(cache): return {_encode_key(k): v for k, v in cache.items() if k and v}
def _cache_from_fb(raw):
    if not raw or not isinstance(raw, dict): return {}
    return {_decode_key(k): v for k, v in raw.items()}

def batch_translate_ru_to_en(texts):
    if not texts: return {}
    result = {}
    for i in range(0, len(texts), 40):
        chunk = texts[i:i+40]
        try:
            r = cffi_requests.get(TRANSLATE_URL, params={"client": "gtx", "sl": "ru", "tl": "en", "dt": "t", "q": " | ".join(chunk)}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                segs = data[0] if data and data[0] else []
                full = "".join(s[0] for s in segs if s and s[0])
                parts = [p.strip() for p in full.split("|")]
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
        if matching: return max(matching, key=base_score)
    return max(cands, key=base_score)

def search_fotmob_candidates(team_name, name_en):
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
        except Exception: pass
    return out

async def search_thesportsdb(name_en):
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
        except Exception: continue
    return out

async def resolve_logo(team_ru, comp_name, cache, name_en_map, force_refresh=False):
    country = league_to_country(comp_name) or ""
    key = f"{team_ru}|{country}"
    if not force_refresh:
        for ek in (key, team_ru):
            ex = cache.get(ek)
            if ex and not _is_fallback(ex):
                LOGO_STATS["cache"] += 1
                return ex
    direct = DIRECT_LOGO_URLS.get(team_ru)
    if direct:
        cache[key] = direct; LOGO_STATS["direct"] += 1; return direct
    fid = FOTMOB_ID_OVERRIDES.get(team_ru)
    if fid:
        logo = f"https://images.fotmob.com/image_resources/logo/teamlogo/{fid}.png"
        cache[key] = logo; LOGO_STATS["fotmob"] += 1; return logo
    name_en = TEAM_OVERRIDES.get(team_ru) or name_en_map.get(team_ru) or team_ru
    best = pick_best_candidate(search_fotmob_candidates(team_ru, name_en), name_en, country)
    if best and best.get("logo"):
        cache[key] = best["logo"]; LOGO_STATS["fotmob"] += 1; return best["logo"]
    best = pick_best_candidate(await search_thesportsdb(name_en), name_en, country)
    if best and best.get("logo"):
        cache[key] = best["logo"]; LOGO_STATS["thesportsdb"] += 1; return best["logo"]
    fb = make_fallback_logo(team_ru)
    cache[key] = fb; LOGO_STATS["fallback"] += 1; FALLBACK_TEAMS.append(team_ru); return fb

async def search_all_logos(teams_with_league, cache, name_en_map):
    sem = asyncio.Semaphore(10)
    async def one(team, league, force):
        async with sem:
            try: await resolve_logo(team, league, cache, name_en_map, force_refresh=force)
            except Exception:
                hint = league_to_country(league) or ""
                cache[f"{team}|{hint}"] = make_fallback_logo(team)
                LOGO_STATS["fallback"] += 1; FALLBACK_TEAMS.append(team)
    await asyncio.gather(*(one(t, l, f) for t, l, f in teams_with_league))

def _safe_get_first(d, keys):
    if not isinstance(d, dict): return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def _try_extract_minute(val):
    if val is None or isinstance(val, bool): return None
    if isinstance(val, (int, float)):
        return int(val) if 0 <= val <= 130 else None
    if isinstance(val, str):
        s = val.strip(); sl = s.lower()
        if any(x in sl for x in ["перерыв", "halftime", "half time", "ht"]): return "HT"
        if any(x in sl for x in ["завершен", "finished", "ended", "full time", "ft"]): return "FT"
        if any(x in sl for x in ["1st half", "1h", "первый тайм"]): return "1H"
        if any(x in sl for x in ["2nd half", "2h", "второй тайм"]): return "2H"
        m = re.search(r"(\d{1,3})", s)
        if m:
            n = int(m.group(1))
            if 0 <= n <= 130: return n
        return None
    if isinstance(val, dict):
        for sub in ["minute", "current", "elapsed", "value", "display", "text", "seconds", "currentMinute"]:
            if sub in val:
                r = _try_extract_minute(val[sub])
                if r is not None: return r
        return None
    return None

def extract_live_score_and_time(ev):
    score = None; minute = None
    sc = ev.get("score")
    if isinstance(sc, dict):
        s1 = _safe_get_first(sc, ["team1", "home", "score1", "homeScore", "team1Score"])
        s2 = _safe_get_first(sc, ["team2", "away", "score2", "awayScore", "team2Score"])
        if s1 is not None and s2 is not None: score = f"{s1} : {s2}"
    elif isinstance(sc, (list, tuple)) and len(sc) >= 2:
        if sc[0] is not None and sc[1] is not None: score = f"{sc[0]} : {sc[1]}"
    elif isinstance(sc, str) and ":" in sc: 
        score = sc
    if not score:
        s1 = _safe_get_first(ev, ["score1", "homeScore", "team1Score"])
        s2 = _safe_get_first(ev, ["score2", "awayScore", "team2Score"])
        if s1 is not None and s2 is not None: score = f"{s1} : {s2}"

    for field in ["minute", "currentMinute", "liveTime", "liveTimer", "elapsed",
                  "time", "timer", "matchTime", "gameTime", "periodTime",
                  "currentTime", "timeLive", "liveMinute", "scoreTime", "statusTime",
                  "gameMinute", "elapsedTime", "timePlayed", "minutes", "minutePlayed"]:
        if field in ev:
            r = _try_extract_minute(ev[field])
            if r is not None: minute = r; break

    if minute is None:
        for nk in ["score", "status", "live", "progress", "timer", "time"]:
            nested = ev.get(nk)
            if isinstance(nested, dict):
                r = _try_extract_minute(nested)
                if r is not None: minute = r; break

    if minute is None:
        for pf in ["period", "timeStatus", "status", "liveStatus", "matchStatus", "half", "timePeriod"]:
            v = ev.get(pf)
            if isinstance(v, str):
                vl = v.lower()
                if any(x in vl for x in ["ht", "halftime", "перерыв", "half"]): minute = "HT"; break
                if any(x in vl for x in ["1h", "1st", "первый тайм"]): minute = "1H"; break
                if any(x in vl for x in ["2h", "2nd", "второй тайм"]): minute = "2H"; break

    if minute is None:
        start_ts = ev.get("startDateTime")
        if start_ts and isinstance(start_ts, (int, float)):
            now = time.time()
            elapsed_mins = (now - start_ts) / 60.0
            if elapsed_mins < 0: minute = 0
            elif elapsed_mins < 47: minute = int(elapsed_mins)
            elif elapsed_mins < 62: minute = "HT"
            elif elapsed_mins < 107: minute = int(elapsed_mins) - 15
            else: minute = "FT"

    return score, minute

def build_status(status_type, minute):
    if status_type != "LIVE": return status_type
    if minute is None: return "LIVE"
    if minute in ("HT", "FT", "1H", "2H"): return f"LIVE · {minute}"
    return f"LIVE {minute}'"

def fetch_olimp_matches(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
    for _ in range(2):
        try:
            r = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=120)
            if r.status_code == 200: return r.json()
        except Exception: time.sleep(1)
    return []

def find_logo(cache, team, hint):
    if not team: return ""
    v = cache.get(f"{team}|{hint}")
    if v: return v
    v = cache.get(team)
    if v: return v
    for k, val in cache.items():
        if "|" in k and k.split("|")[0] == team and val:
            return val
    return ""

async def fetch_olimp_results():
    print("📥 Загружаю результаты из Olimpbet...")
    results_dict = {}
    try:
        data = fetch_olimp_matches(OLIMP_RESULTS_URL)
        for sg in data:
            sport = sg.get("payload", {}).get("sport", {})
            if str(sport.get("id")) != "1": continue
            comps = sg.get("payload", {}).get("competitionsWithEvents", [])
            for comp in comps:
                for ev in comp.get("events", []):
                    ev_id = ev.get("id")
                    if not ev_id: continue
                    sc = ev.get("score")
                    if isinstance(sc, dict):
                        s1 = _safe_get_first(sc, ["team1", "home"])
                        s2 = _safe_get_first(sc, ["team2", "away"])
                        if s1 is not None and s2 is not None:
                            results_dict[f"olimp_{ev_id}"] = {"score1": int(s1), "score2": int(s2)}
    except Exception as e:
        print(f"   ⚠️ Ошибка Olimpbet results: {e}")
    return results_dict

async def fetch_finished_matches(old_matches, new_match_ids):
    print("📥 Ищу результаты завершенных матчей...")
    finished_known = await firebase_get("finished_matches") or {}
    if not isinstance(finished_known, dict): finished_known = {}

    finished_dict = {}
    now = time.time()
    missing_ids = set()
    for mid, match in old_matches.items():
        if not isinstance(match, dict): continue
        if mid in finished_known: continue
        st = match.get("start_time")
        is_old = st and (now > st + 7800)
        if (mid not in new_match_ids and is_old) or (mid in new_match_ids and is_old):
            missing_ids.add(mid)

    if not missing_ids:
        print("✅ Нет матчей, требующих результата.")
        return

    print(f"🔍 Проверяю {len(missing_ids)} матчей на результат:")
    for mid in missing_ids:
        m = old_matches[mid]
        st = m.get("start_time", 0)
        age_h = round((now - st) / 3600, 1) if st else "?"
        print(f"   • {m.get('title')} ({mid}) — прошло {age_h}ч")

    olimp_results = await fetch_olimp_results()
    for mid in missing_ids:
        if mid in olimp_results:
            finished_dict[mid] = olimp_results[mid]
            print(f"   ✅ [Olimpbet] {mid}: {olimp_results[mid]['score1']}:{olimp_results[mid]['score2']}")

    missing_after_olimp = missing_ids - set(finished_dict.keys())
    if missing_after_olimp:
        dates = {
            time.strftime("%Y-%m-%d", time.localtime(now)),
            time.strftime("%Y-%m-%d", time.localtime(now - 86400)),
        }
        tsdb_results = {}
        async with httpx.AsyncClient() as client:
            for d in dates:
                try:
                    r = await client.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={d}&s=Soccer", timeout=15)
                    if r.status_code == 200:
                        for ev in (r.json() or {}).get("events") or []:
                            h = _normalize(ev.get("strHomeTeam", ""))
                            a = _normalize(ev.get("strAwayTeam", ""))
                            s1 = ev.get("intHomeScore"); s2 = ev.get("intAwayScore")
                            if s1 is not None and s2 is not None:
                                tsdb_results[f"{h}_{a}"] = {"score1": int(s1), "score2": int(s2)}
                except Exception: pass

        for mid in missing_after_olimp:
            match = old_matches[mid]
            h = _normalize(match.get("home", ""))
            a = _normalize(match.get("away", ""))
            if f"{h}_{a}" in tsdb_results:
                finished_dict[mid] = tsdb_results[f"{h}_{a}"]
                print(f"   ✅ [TSDB] {match.get('title')}: {finished_dict[mid]['score1']}:{finished_dict[mid]['score2']}")
                continue
            elif f"{a}_{h}" in tsdb_results:
                res = tsdb_results[f"{a}_{h}"]
                finished_dict[mid] = {"score1": res["score2"], "score2": res["score1"]}
                print(f"   ✅ [TSDB rev] {match.get('title')}: {finished_dict[mid]['score1']}:{finished_dict[mid]['score2']}")
                continue

            match_score = match.get("score", "")
            if ":" in match_score:
                try:
                    s1, s2 = [int(x.strip()) for x in match_score.split(":")]
                    finished_dict[mid] = {"score1": s1, "score2": s2, "source": "match_score"}
                    print(f"   🎯 [LAST_SCORE] {match.get('title')}: {s1}:{s2} (из БД)")
                    continue
                except: pass

            st = match.get("start_time")
            if st and now > st + 9000:
                finished_dict[mid] = {"void": True}
                print(f"   💀 [VOID] {match.get('title')} — прошло >2.5ч, счёта нет")

    if finished_dict:
        print(f"✅ Записываю {len(finished_dict)} результатов в finished_matches")
        async with httpx.AsyncClient() as client:
            await client.patch(f"{FIREBASE_DB_URL}/finished_matches.json", json=finished_dict, timeout=30.0)

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

# ====== РАЗВЕДКА (DO_RECON=1) ======
async def run_recon(ev_id):
    """
    Пробует напрямую дёрнуть кучу URL с eventId + слушает WS на странице матча.
    """
    from rebrowser_playwright.async_api import async_playwright
    
    print(f"\n🧪 [RECON] Прямой перебор URL для события {ev_id}:\n")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": f"https://www.olimp.bet/live/futbol-1/{ev_id}",
        "Origin": "https://www.olimp.bet",
    }
    
    test_urls = [
        f"https://www.olimp.bet/api/v4/0/live/sports-with-competitions-with-events?vids%5B%5D=1%3A{ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/sports-with-competitions-with-events?eventIds%5B%5D={ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/sports-with-competitions-with-events?eventId={ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/events/{ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/events/{ev_id}/markets",
        f"https://www.olimp.bet/api/v4/0/live/event/{ev_id}/markets",
        f"https://www.olimp.bet/api/v4/0/live/events-with-markets/{ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/event-with-markets/{ev_id}",
        f"https://www.olimp.bet/api/v4/0/events/{ev_id}",
        f"https://www.olimp.bet/api/v4/0/events/{ev_id}/markets",
        f"https://www.olimp.bet/api/v4/0/markets/event/{ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/markets?eventId={ev_id}",
        f"https://www.olimp.bet/api/v4/0/live/events-with-markets?vids%5B%5D=1%3A{ev_id}",
        f"https://www.olimp.bet/api/v4/0/line/sports-with-competitions-with-events?vids%5B%5D=1%3A{ev_id}",
    ]
    
    for u in test_urls:
        try:
            r = cffi_requests.get(u, headers=headers, impersonate="chrome120", timeout=10)
            preview = r.text[:500] if r.text else ""
            has_markets = any(x in preview.lower() for x in ['"outcomes"', '"markets"', '"total"', '"handicap"', '"spread"'])
            status_mark = "✅" if r.status_code == 200 else "❌"
            markets_mark = "📊" if has_markets else "—"
            print(f"   {status_mark}{markets_mark} [{r.status_code}] {u}")
            if r.status_code == 200:
                print(f"      → {preview[:200]}")
        except Exception as e:
            print(f"   ❌ ERR {u} → {str(e)[:100]}")
    
    # Теперь Playwright — слушаем WS на странице матча
    print(f"\n🔌 [RECON] Playwright: слушаем WS на странице матча {ev_id}...\n")
    
    ws_messages = []
    xhr_urls = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        async def on_response(response):
            url = response.url
            if response.status == 200 and "api" in url and "json" in response.headers.get("content-type", ""):
                xhr_urls.add(url)
        
        page.on("response", on_response)
        
        def on_ws(ws):
            print(f"   🔌 [WS] Подключён: {ws.url}")
            def on_frame(payload):
                try:
                    s = payload if isinstance(payload, str) else payload.decode("utf-8", errors="ignore")
                    if len(s) > 50:
                        ws_messages.append(s[:500])
                except: pass
            ws.on("framereceived", on_frame)
        
        page.on("websocket", on_ws)
        
        try:
            await page.goto(f"https://www.olimp.bet/live/futbol-1/{ev_id}", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(20)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        await browser.close()
    
    print(f"\n📡 [RECON] XHR URL после открытия страницы матча:")
    for u in sorted(xhr_urls):
        print(f"👉 {u}")
    
    print(f"\n📨 [RECON] Получено WS-сообщений: {len(ws_messages)}")
    for i, m in enumerate(ws_messages[:10]):
        print(f"   [{i}] {m}")
    print()

async def main():
    if DO_RECON:
        print("🕵️ Запуск в режиме РАЗВЕДКИ...")
        live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
        ev_id = None
        for sg in live_data:
            sport = sg.get("payload", {}).get("sport", {})
            if str(sport.get("id")) != "1": continue
            for comp in sg.get("payload", {}).get("competitionsWithEvents", []):
                for ev in comp.get("events", []):
                    t1 = ev.get("team1Name", ""); t2 = ev.get("team2Name", "")
                    if t1 and t2:
                        ev_id = ev.get("id")
                        break
                if ev_id: break
            if ev_id: break
        if not ev_id:
            print("❌ Нет live-матчей для разведки.")
            return
        await run_recon(ev_id)
        return

    print("🔄 [Scraper] Запуск (обычный режим)...")

    old_matches_dict = await firebase_get("matches") or {}
    if not isinstance(old_matches_dict, dict): old_matches_dict = {}
    finished_known = await firebase_get("finished_matches") or {}
    if not isinstance(finished_known, dict): finished_known = {}
    raw_cache = await firebase_get("team_logos") or {}
    logo_cache = _cache_from_fb(raw_cache)
    print(f"📥 В кэше логотипов: {len(logo_cache)}")

    live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
    line_data = fetch_olimp_matches(OLIMP_LINE_URL)

    all_matches = []
    now_ts = time.time()

    def parse(data, status_type):
        count = 0
        for sg in data:
            sport = sg.get("payload", {}).get("sport", {})
            if str(sport.get("id")) != "1": continue
            comps = sg.get("payload", {}).get("competitionsWithEvents", [])
            for comp in comps:
                comp_name = comp.get("competition", {}).get("name", "Футбол")
                for ev in comp.get("events", []):
                    t1 = ev.get("team1Name", ""); t2 = ev.get("team2Name", "")
                    if t1 and t2 and is_valid_match(t1, t2, comp_name):
                        st = ev.get("startDateTime")
                        actual_status = status_type
                        if status_type == "Скоро" and isinstance(st, (int, float)) and st < now_ts:
                            actual_status = "LIVE"
                        all_matches.append((ev, actual_status, comp_name))
                        count += 1
        return count

    live_count = parse(live_data, "LIVE")
    line_count = parse(line_data, "Скоро")
    print(f"⚽ LIVE: {live_count} | Скоро: {line_count}")

    unique_matches = {}
    for ev, status_type, league_name in all_matches:
        ev_id = ev.get("id")
        if not ev_id: continue
        if ev_id in unique_matches:
            if unique_matches[ev_id][1] == "Скоро" and status_type == "LIVE":
                unique_matches[ev_id] = (ev, status_type, league_name)
        else:
            unique_matches[ev_id] = (ev, status_type, league_name)
    
    print(f"🎯 Уникальных матчей: {len(unique_matches)}")

    missing = set()
    for ev, _, league_name in unique_matches.values():
        for t in (ev.get("team1Name"), ev.get("team2Name")):
            if not t: continue
            hint = league_to_country(league_name) or ""
            ex = logo_cache.get(f"{t}|{hint}") or logo_cache.get(t)
            force = (t in FOTMOB_ID_OVERRIDES) or (t in DIRECT_LOGO_URLS) or (not ex) or _is_fallback(ex)
            if force: missing.add((t, league_name, force))

    if missing:
        print(f"🔎 Поиск логотипов для {len(missing)} пар...")
        teams_to_search = list({t for t, _, _ in missing})
        name_en_map = batch_translate_ru_to_en(teams_to_search)
        t0 = time.time()
        await search_all_logos(list(missing), logo_cache, name_en_map)
        print(f"✅ Логотипы обработаны за {time.time()-t0:.1f}s")
        await firebase_put("team_logos", _cache_to_fb(logo_cache))
        if FALLBACK_TEAMS: print(f"🚨 БЕЗ ЛОГОТИПОВ: {list(set(FALLBACK_TEAMS))}")

    matches_dict = {}
    live_with_score = 0
    for ev, status_type, league_name in unique_matches.values():
        ev_id = ev.get("id")
        mid = f"olimp_{ev_id}"
        if mid in finished_known: continue

        t1 = ev.get("team1Name"); t2 = ev.get("team2Name")
        hint = league_to_country(league_name) or ""
        hl = find_logo(logo_cache, t1, hint)
        al = find_logo(logo_cache, t2, hint)

        p1 = px = p2 = None
        markets_data = {}

        for out in ev.get("outcomes", []):
            gn = out.get("groupName", "Другое").strip()
            sn = out.get("shortName", "").strip()
            prob = out.get("probability")
            if prob is None or not sn: continue
            if gn not in markets_data: markets_data[gn] = []
            markets_data[gn].append({"name": sn, "odds": prob})
            if "Исход" in gn or "Результат" in gn:
                if sn in ["П1", "1"]: p1 = prob
                elif sn in ["X", "Х"]: px = prob
                elif sn in ["П2", "2"]: p2 = prob

        score = "VS"; status_str = status_type
        if status_type == "LIVE":
            sc, mn = extract_live_score_and_time(ev)
            if sc: 
                score = sc
                live_with_score += 1
            status_str = build_status("LIVE", mn)

        time_display = status_str
        if status_type == "Скоро":
            st = ev.get("startDateTime")
            if isinstance(st, (int, float)): 
                time_display = time.strftime("%d.%m %H:%M", time.localtime(st))

        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": hl, "awayLogo": al, "league": league_name,
            "status": time_display, "score": score,
            "start_time": ev.get("startDateTime"),
            "odds": {"1": p1, "X": px, "2": p2},
            "markets": markets_data
        }

    print(f"🎯 LIVE-матчей со счётом: {live_with_score}")

    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей")

    await fetch_finished_matches(old_matches_dict, set(matches_dict.keys()))

if __name__ == "__main__":
    asyncio.run(main())