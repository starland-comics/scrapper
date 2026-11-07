import asyncio
import time
import httpx
import json
import urllib.parse
import os
import re
import hashlib
import base64
from collections import Counter
from curl_cffi import requests as cffi_requests
from rapidfuzz import fuzz

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FONBET_BASE = "https://line-lb51.bk6bba-resources.com"
FONBET_LINE_PATH = "/events/listBase?scopeMarket=1600&lang=ru"          # prematch — базовые данные
FONBET_LIVE_PATH = "/events/list?scopeMarket=1600&lang=ru&live=true"   # live — со счётом

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
    "Origin": "https://www.fon.bet"
}

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

FONBET_FACTORS = {
    921: ("Исход", "П1", False),
    922: ("Исход", "Х", False),
    923: ("Исход", "П2", False),
    924: ("Двойной шанс", "1Х", False),
    925: ("Двойной шанс", "12", False),
    926: ("Двойной шанс", "Х2", False),
    928: ("Обе забьют", "Да", False),
    929: ("Обе забьют", "Нет", False),
    930: ("Тотал", "ТБ", True),
    931: ("Тотал", "ТМ", True),
    932: ("Фора", "Ф1", True),
    933: ("Фора", "Ф2", True),
}

# === ТОЧНЫЙ WHITELIST ЛИГ (проверено по Fonbet) ===
ALLOWED_LEAGUES_EXPLICIT = [
    # ─── Россия (вышка + 2-й див + кубок) ───
    "Россия. Премьер", "Россия. РПЛ", "Россия. ФНЛ", "Россия. Первая лига",
    "Россия. Кубок",
    # ─── Англия (вышка + 2-й див + кубки) ───
    "Англия. Премьер", "Англия. Чемпионшип",
    "Англия. Кубок Англии", "Англия. Кубок лиги", "Англия. FA Cup",
    "Англия. EFL Cup", "Англия. Carabao",
    # ─── Испания (вышка + 2-й див + кубок) ───
    "Испания. Ла Лига", "Испания. Примера", "Испания. Сегунда",
    "Испания. Кубок", "Испания. Copa",
    # ─── Италия (вышка + 2-й див + кубок) ───
    "Италия. Серия А", "Италия. Серия Б", "Италия. Серия B",
    "Италия. Кубок",
    # ─── Германия (вышка + 2-й див + кубок) ───
    "Германия. Бундеслига", "Германия. 2-я Бундеслига", "Германия. 2. Бундеслига",
    "Германия. Вторая Бундеслига", "Германия. Кубок",
    # ─── Франция (вышка + 2-й див + кубок) ───
    "Франция. Лига 1", "Франция. Лига 2",
    "Франция. Кубок", "Франция. Coupe",
    # ─── Португалия (ТОЛЬКО вышка + кубок) ───
    "Португалия. Примейра", "Португалия. Primeira", "Португалия. Лига",
    "Португалия. Кубок", "Португалия. Taça",
    # ─── Нидерланды (ТОЛЬКО вышка + кубок) ───
    "Нидерланды. Эредивизи", "Нидерланды. Eredivisie",
    "Нидерланды. Кубок", "Нидерланды. KNVB",
    # ─── Бразилия (ТОЛЬКО вышка + кубок) ───
    "Бразилия. Серия A", "Бразилия. Серия А",
    "Бразилия. Кубок", "Бразилия. Copa do Brasil",
    # ─── Украина (ТОЛЬКО вышка + кубок) ───
    "Украина. Премьер", "Украина. УПЛ", "Украина. Кубок",
    # ─── Казахстан (ТОЛЬКО вышка + кубок) ───
    "Казахстан. Премьер", "Казахстан. Кубок",
    # ─── Саудовская Аравия (ТОЛЬКО вышка + кубок) ───
    "Саудовская Аравия. Про", "Саудовская Аравия. Премьер", "Саудовская Аравия. Кубок",
    # ─── Турция (ТОЛЬКО вышка + кубок) ───
    "Турция. Суперлига", "Турция. Süper Lig", "Турция. Кубок",
    # ─── США (ТОЛЬКО MLS + кубок) ───
    "США. MLS", "США. Major League Soccer", "США. Открытый кубок",
    # ─── Международные турниры ───
    "Лига чемпионов", "Лига Европы", "Лига конференций",
    "Чемпионат Европы", "Чемпионат мира", "Лига наций",
    "Отборочный", "Сборная", "Суперкубок УЕФА", "Товарищеск",
]

# === BLACKLIST ЛИГ (виды спорта + мусор, работает ДО whitelist) ===
FORBIDDEN_LEAGUE_WORDS = [
    "теннис", "tennis", "баскетбол", "basketball",
    "хоккей", "hockey", "волейбол", "volleyball",
    "регби", "rugby", "крикет", "cricket",
    "американский футбол", "american football", "бейсбол", "baseball",
    "гандбол", "handball", "флорбол", "floorball", "пляжный",
    "кибер", "esports", "e-sports", "csgo", "cs:go", "dota",
    "virtua", "виртуальн", "virtual",
    "лига про", "h2h", "fc 27", "fc27", "fc 26", "fc26", "fc 25", "fc25",
    "ncaa", "ncaab", "ncaaf",
    "жен", "women", "ladies", "fem", "vrouwen", "дамы", "девуш",
    "юнош", "юн ", "молодеж", "молодёж", "молодежн", "мол ",
    "дубл", "reserve", "academy", "академ",
    "до 15", "до 16", "до 17", "до 18", "до 19", "до 20", "до 21", "до 23",
    "u15", "u16", "u17", "u18", "u19", "u20", "u21", "u23",
    "u 15", "u 16", "u 17", "u 18", "u 19", "u 20", "u 21", "u 23",
    "пфл", "третий дивизион", "третья лига", "третий див",
    "amateur", "любител", "лига трофи",
]

BLACKLIST_WORDS = [
    "люб", "жен", "мол", "дубл", "резерв", "академ",
    "до 15", "до 16", "до 17", "до 18", "до 19", "до 20", "до 21", "до 23",
    "u15", "u16", "u17", "u18", "u19", "u20", "u21", "u23",
    " b team", " ii", " iii",
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

def _first_not_none(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def _normalize(s):
    s = (s or "").lower().strip()
    for w in (" fc", " cf", " sc", " ac", " fk", " afc", " club", " фк", " клуб"):
        s = s.replace(w, "").strip()
    return s

def is_allowed_league(league):
    """Точный whitelist по названиям лиг + blacklist по мусору."""
    if not league or league == "Футбол": return False
    low = league.lower()
    # Blacklist приоритетнее — виды спорта и мусор
    for f in FORBIDDEN_LEAGUE_WORDS:
        if f in low: return False
    # Whitelist — точное вхождение
    for allowed in ALLOWED_LEAGUES_EXPLICIT:
        if allowed.lower() in low:
            return True
    return False

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

def build_team_logo_index(cache):
    idx = {}
    for k, v in cache.items():
        if not v: continue
        team = k.split("|")[0] if "|" in k else k
        if team not in idx:
            idx[team] = v
    return idx

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
    sem = asyncio.Semaphore(40)
    async def one(team, league, force):
        async with sem:
            try: await resolve_logo(team, league, cache, name_en_map, force_refresh=force)
            except Exception:
                hint = league_to_country(league) or ""
                cache[f"{team}|{hint}"] = make_fallback_logo(team)
                LOGO_STATS["fallback"] += 1; FALLBACK_TEAMS.append(team)
    await asyncio.gather(*(one(t, l, f) for t, l, f in teams_with_league))

def find_logo_fast(team_logo_idx, team, cache, hint):
    if not team: return ""
    v = cache.get(f"{team}|{hint}")
    if v: return v
    return team_logo_idx.get(team, "")

# ============ FONBET ============

def fetch_fonbet_data(url):
    for _ in range(2):
        try:
            r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=45)
            if r.status_code == 200:
                try: return r.json()
                except json.JSONDecodeError:
                    print(f"   ⚠️ Не JSON: {r.text[:200]}")
                    return None
            else:
                print(f"   ⚠️ HTTP {r.status_code} для {url}")
        except Exception as e:
            print(f"   ⚠️ {e}")
            time.sleep(1)
    return None


def _parse_start_ts(ev):
    st = ev.get("startTime")
    if st is None: return 0
    try: return int(st)
    except: return 0


def _is_match_live(ev, now_ts):
    start_ts = _parse_start_ts(ev)
    if start_ts <= 0: return False
    elapsed = now_ts - start_ts
    if elapsed < 0: return False
    if elapsed >= int(3.5 * 3600): return False
    return True


def _parse_live_minute(ev):
    for k in ("timer", "time", "liveTimer", "currentMinute"):
        v = ev.get(k)
        if v is not None:
            try: return int(v)
            except: pass
    score = ev.get("score")
    if isinstance(score, dict):
        for k in ("timer", "time", "minute"):
            v = score.get(k)
            if v is not None:
                try: return int(v)
                except: pass
    return None


def extract_live_score(ev):
    """Гибкий парсинг счёта из разных форматов Fonbet."""
    score = ev.get("score")
    if isinstance(score, dict) and score:
        s1 = _first_not_none(score, ["c1", "team1", "s1", "home", "homeScore"])
        s2 = _first_not_none(score, ["c2", "team2", "s2", "away", "awayScore"])
        if s1 is not None and s2 is not None:
            try: return int(s1), int(s2)
            except: pass
    # Fallback: flat fields
    s1 = _first_not_none(ev, ["score1", "s1", "homeScore"])
    s2 = _first_not_none(ev, ["score2", "s2", "awayScore"])
    if s1 is not None and s2 is not None:
        try: return int(s1), int(s2)
        except: pass
    return None


def format_total_param(p):
    """Fonbet отдаёт p в разных форматах: 2.5, 25, 250 — надо нормализовать."""
    if p is None: return None
    try: p_val = float(p)
    except: return str(p)
    if p_val != int(p_val):
        return f"{p_val:g}"  # 2.5 → "2.5"
    p_int = int(p_val)
    if p_int >= 100:
        return f"{p_int / 100:g}"  # 250 → "2.5", 450 → "4.5"
    elif p_int >= 10:
        return f"{p_int / 10:g}"   # 25 → "2.5", 45 → "4.5"
    return str(p_int)               # 5 → "5"


def collect_fonbet_data(data):
    if not data: return [], {}, []
    events = data.get("events", [])
    factors_raw = data.get("factors", [])
    custom_factors_raw = data.get("customFactors", [])
    sports_list = data.get("sports", [])
    
    factors_by_event = {}
    for f in factors_raw:
        eid = f.get("e")
        if eid: factors_by_event.setdefault(eid, []).append(f)
    for cf in custom_factors_raw:
        eid = cf.get("e")
        if eid: factors_by_event.setdefault(eid, []).extend(cf.get("factors", []))
    
    return events, factors_by_event, sports_list


def parse_fonbet_odds(factors_list):
    markets = {}
    for factor in factors_list:
        fid = factor.get("f")
        if fid not in FONBET_FACTORS: continue
        group_name, base_name, has_param = FONBET_FACTORS[fid]
        odds = factor.get("v")
        if odds is None: continue
        try: odds = float(odds)
        except: continue
        if odds <= 1.0: continue
        name = base_name
        if has_param:
            p_str = format_total_param(factor.get("p"))
            if p_str is None: continue
            name = f"{base_name} {p_str}"
        if group_name not in markets: markets[group_name] = []
        markets[group_name].append({"name": name, "odds": odds})
    return markets


def filter_decided_markets(markets, s1, s2):
    """Убирает 100% сыгравшие рынки. s1/s2 — текущий счёт."""
    if s1 is None or s2 is None:
        return markets
    filtered = {}
    total = s1 + s2
    
    for group_name, outcomes in markets.items():
        if group_name == "Обе забьют":
            # Если обе команды забили — Да выиграл, Нет проиграл. Всё решено.
            if s1 > 0 and s2 > 0:
                continue
            filtered[group_name] = outcomes
        
        elif group_name == "Тотал":
            new_outs = []
            for o in outcomes:
                name = o["name"]
                limit_str = None
                if name.startswith("ТБ "): limit_str = name[3:]
                elif name.startswith("ТМ "): limit_str = name[3:]
                if limit_str:
                    try: limit = float(limit_str)
                    except:
                        new_outs.append(o); continue
                    # Решено если total > limit (неважно .5 или целый)
                    if total > limit:
                        continue
                new_outs.append(o)
            if new_outs:
                filtered[group_name] = new_outs
        
        else:
            filtered[group_name] = outcomes
    
    return filtered


# ============ FIREBASE ============

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


# ============ MAIN ============

async def main():
    t0 = time.time()
    print("🔄 [Scraper] Запуск (Fonbet)...")
    
    now_ts = int(time.time())
    seven_days = 7 * 86400
    
    raw_cache = await firebase_get("team_logos") or {}
    logo_cache = _cache_from_fb(raw_cache)
    team_logo_idx = build_team_logo_index(logo_cache)
    print(f"📥 В кэше логотипов: {len(logo_cache)} (уникальных: {len(team_logo_idx)})")
    
    print("📥 Загружаю линию Fonbet...")
    line_data = fetch_fonbet_data(FONBET_BASE + FONBET_LINE_PATH)
    live_data = fetch_fonbet_data(FONBET_BASE + FONBET_LIVE_PATH)
    
    if not line_data and not live_data:
        print("❌ Не удалось загрузить данные Fonbet.")
        return
    
    events_by_id = {}
    all_factors = {}
    all_sports = []
    
    for data in [line_data, live_data]:
        if not data: continue
        events, fb_e, sps = collect_fonbet_data(data)
        all_sports.extend(sps)
        for ev in events:
            eid = ev.get("id")
            if not eid: continue
            if eid in events_by_id:
                # Мержим score если в live есть
                old = events_by_id[eid]
                if ev.get("score") and not old.get("score"):
                    old["score"] = ev["score"]
                # Также timer
                if ev.get("timer") and not old.get("timer"):
                    old["timer"] = ev["timer"]
            else:
                events_by_id[eid] = dict(ev)
        for eid, flist in fb_e.items():
            all_factors.setdefault(eid, []).extend(flist)
    
    all_events = list(events_by_id.values())
    print(f"⚽ Всего событий (после дедупликации): {len(all_events)}")
    
    # Debug: показать структуру live-события
    for ev in all_events:
        if ev.get("rootKind") == 1 and ev.get("kind") == 1 and _is_match_live(ev, now_ts):
            print(f"   🔍 LIVE debug: {ev.get('team1')} vs {ev.get('team2')}")
            print(f"      keys: {list(ev.keys())}")
            print(f"      score field: {ev.get('score')}")
            print(f"      extracted: {extract_live_score(ev)}")
            print(f"      timer: {ev.get('timer')}")
            break
    
    tournament_by_id = {}
    for sp in all_sports:
        if sp.get('kind') == 'sport': continue
        sp_id = sp.get('id'); sp_name = sp.get('name', '')
        if sp_id and sp_name:
            tournament_by_id[sp_id] = sp_name
    
    # === ФИЛЬТРАЦИЯ ===
    valid_events = []
    skipped_sport = 0
    skipped_blacklist = 0
    skipped_whitelist = 0
    skipped_no_teams = 0
    skipped_time = 0
    rejected_leagues = Counter()
    live_count = 0
    prematch_count = 0
    
    for ev in all_events:
        if ev.get("rootKind") != 1 or ev.get("kind") != 1:
            skipped_sport += 1
            continue
        t1 = ev.get("team1", "")
        t2 = ev.get("team2", "")
        if not t1 or not t2:
            skipped_no_teams += 1
            continue
        
        start_ts = _parse_start_ts(ev)
        if start_ts <= 0:
            skipped_time += 1
            continue
        
        is_live = _is_match_live(ev, now_ts)
        
        if not is_live:
            if start_ts < now_ts - int(3.5 * 3600):
                skipped_time += 1
                continue
            if start_ts > now_ts + seven_days:
                skipped_time += 1
                continue
        
        sid = ev.get("sportId")
        league = tournament_by_id.get(sid, "")
        
        text = f"{t1} {t2}".lower()
        if any(word in text for word in BLACKLIST_WORDS):
            skipped_blacklist += 1
            continue
        
        if not is_allowed_league(league):
            skipped_whitelist += 1
            if league: rejected_leagues[league] += 1
            continue
        
        valid_events.append((ev, is_live, league, start_ts))
        if is_live: live_count += 1
        else: prematch_count += 1
    
    print(f"🔎 Отсев: sport/kind: {skipped_sport} | нет команд: {skipped_no_teams} | время: {skipped_time} | blacklist: {skipped_blacklist} | whitelist: {skipped_whitelist}")
    print(f"🎯 Валидных матчей: {len(valid_events)} (LIVE: {live_count} | Прематч: {prematch_count})")
    
    if rejected_leagues:
        print(f"   🔍 Топ-10 отсечённых лиг:")
        for lg, cnt in rejected_leagues.most_common(10):
            print(f"      {cnt:4d}  {lg}")
    
    valid_leagues = Counter(lg for _, _, lg, _ in valid_events)
    print(f"   ✅ Топ-10 разрешённых лиг:")
    for lg, cnt in valid_leagues.most_common(10):
        print(f"      {cnt:4d}  {lg}")
    
    if not valid_events:
        print("⚠️ Нет валидных матчей.")
        return
    
    # === ОПРЕДЕЛЕНИЕ КОМАНД ===
    teams_ru = set()
    for ev, _, _, _ in valid_events:
        if ev.get("team1"): teams_ru.add(ev.get("team1"))
        if ev.get("team2"): teams_ru.add(ev.get("team2"))
    
    teams_to_translate = set()
    for t in teams_ru:
        if t in FOTMOB_ID_OVERRIDES or t in DIRECT_LOGO_URLS: continue
        existing = team_logo_idx.get(t)
        if existing:  # лого или fallback уже в кэше — пропускаем
            continue
        teams_to_translate.add(t)
    
    print(f"🔤 Новых команд для поиска: {len(teams_to_translate)}/{len(teams_ru)}")
    
    if teams_to_translate:
        name_en_map = batch_translate_ru_to_en(list(teams_to_translate))
    else:
        name_en_map = {}
    
    missing = set()
    for ev, _, league, _ in valid_events:
        for t in (ev.get("team1"), ev.get("team2")):
            if not t: continue
            if t in FOTMOB_ID_OVERRIDES or t in DIRECT_LOGO_URLS: continue
            if team_logo_idx.get(t): continue
            hint = league_to_country(league) or ""
            missing.add((t, league, True))
    
    print(f"🔎 Поиск логотипов для {len(missing)} новых пар...")
    if missing:
        await search_all_logos(list(missing), logo_cache, name_en_map)
        await firebase_put("team_logos", _cache_to_fb(logo_cache))
        team_logo_idx = build_team_logo_index(logo_cache)
        if FALLBACK_TEAMS: print(f"🚨 БЕЗ ЛОГОТИПОВ в этом прогоне: {len(set(FALLBACK_TEAMS))}")
    
    # === СБОРКА ===
    matches_dict = {}
    with_full = 0
    
    for ev, is_live, league, start_ts in valid_events:
        ev_id = ev.get("id")
        if not ev_id: continue
        mid = f"fonbet_{ev_id}"
        t1 = ev.get("team1", "")
        t2 = ev.get("team2", "")
        hint = league_to_country(league) or ""
        hl = find_logo_fast(team_logo_idx, t1, logo_cache, hint)
        al = find_logo_fast(team_logo_idx, t2, logo_cache, hint)
        
        factors_list = all_factors.get(ev_id, [])
        markets_data = parse_fonbet_odds(factors_list)
        
        # Определяем счёт
        score_tuple = extract_live_score(ev) if is_live else None
        s1 = score_tuple[0] if score_tuple else None
        s2 = score_tuple[1] if score_tuple else None
        
        # Для live — фильтруем уже решённые рынки
        if is_live and s1 is not None and s2 is not None:
            markets_data = filter_decided_markets(markets_data, s1, s2)
        
        p1 = px = p2 = None
        if "Исход" in markets_data:
            for o in markets_data["Исход"]:
                if o["name"] == "П1": p1 = o["odds"]
                elif o["name"] == "Х": px = o["odds"]
                elif o["name"] == "П2": p2 = o["odds"]
        
        if markets_data: with_full += 1
        
        score = "VS"
        if is_live:
            if s1 is not None and s2 is not None:
                score = f"{s1} : {s2}"
            minute = _parse_live_minute(ev)
            status_str = f"LIVE {minute}'" if minute is not None else "LIVE"
        else:
            status_str = time.strftime("%d.%m %H:%M", time.localtime(start_ts))
        
        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": hl, "awayLogo": al, "league": league,
            "status": status_str, "score": score,
            "start_time": start_ts,
            "odds": {"1": p1, "X": px, "2": p2},
            "markets": markets_data
        }
    
    print(f"✅ С полной росписью: {with_full}/{len(matches_dict)}")
    print(f"⏱ Время: {time.time()-t0:.1f}s")
    
    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей")

if __name__ == "__main__":
    asyncio.run(main())