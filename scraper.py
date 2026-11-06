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

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
PINNACLE_BASE_URL = "https://guest.api.arcadia.pinnacle.com/0.1"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

PINNACLE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.pinnacle.com",
    "Referer": "https://www.pinnacle.com/",
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
}

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

def american_to_decimal(american_odds):
    try:
        am = float(american_odds)
        if am >= 100:
            return round((am / 100) + 1, 2)
        elif am <= -100:
            return round((100 / abs(am)) + 1, 2)
        return None
    except Exception:
        return None

def parse_pinnacle_odds(markets, home_team, away_team):
    markets_data = {}
    if not markets or not isinstance(markets, list): return markets_data

    for market in markets:
        key = market.get("key", "")
        market_type = market.get("type", "")
        period = market.get("period", 0)
        
        if period != 0: continue # Берем только основной матч

        outcomes = market.get("prices", [])
        if not outcomes: continue

        if market_type == "moneyline":
            group_name = "Исход"
            for out in outcomes:
                designation = out.get("designation", "")
                price = american_to_decimal(out.get("price"))
                if price is None: continue
                
                name = "П1" if designation == "home" else ("Х" if designation == "draw" else "П2")
                if group_name not in markets_data: markets_data[group_name] = []
                markets_data[group_name].append({"name": name, "odds": price})

        elif market_type == "spread":
            group_name = "Фора"
            for out in outcomes:
                designation = out.get("designation", "")
                price = american_to_decimal(out.get("price"))
                points = out.get("points")
                if price is None or points is None: continue
                
                team = home_team if designation == "home" else away_team
                name = f"Ф1 {points:+g}" if designation == "home" else f"Ф2 {points:+g}"
                if group_name not in markets_data: markets_data[group_name] = []
                markets_data[group_name].append({"name": name, "odds": price})

        elif market_type == "total":
            group_name = "Тотал"
            for out in outcomes:
                designation = out.get("designation", "")
                price = american_to_decimal(out.get("price"))
                points = out.get("points")
                if price is None or points is None: continue
                
                name = f"ТБ {points}" if designation == "over" else f"ТМ {points}"
                if group_name not in markets_data: markets_data[group_name] = []
                markets_data[group_name].append({"name": name, "odds": price})

        elif market_type == "team_total":
            for out in outcomes:
                designation = out.get("designation", "")
                price = american_to_decimal(out.get("price"))
                points = out.get("points")
                if price is None or points is None: continue
                
                side = out.get("side", "") # home/away
                group_name = f"Тотал {'1' if side == 'home' else '2'}"
                name = f"ТБ {points}" if designation == "over" else f"ТМ {points}"
                
                if group_name not in markets_data: markets_data[group_name] = []
                markets_data[group_name].append({"name": name, "odds": price})

    return markets_data

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

async def fetch_pinnacle_data(endpoint):
    url = f"{PINNACLE_BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=PINNACLE_HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print("   ⚠️ Pinnacle rate limit (429). Ждем...")
                return None
            else:
                print(f"   ⚠️ Pinnacle error {r.status_code} for {endpoint}")
                return None
    except Exception as e:
        print(f"   ⚠️ Pinnacle request failed: {e}")
        return None

async def fetch_pinnacle_matchups():
    print("📥 Загружаю матчи из Pinnacle...")
    leagues = await fetch_pinnacle_data("/sports/1/leagues")
    if not leagues:
        print("   ❌ Не удалось загрузить лиги Pinnacle.")
        return []

    allowed_league_ids = []
    for lg in leagues:
        name = lg.get("name", "")
        if any(allowed in name.lower() for allowed in ALLOWED_LEAGUES):
            allowed_league_ids.append(lg.get("id"))

    if not allowed_league_ids:
        print("   ⚠️ Не найдено подходящих лиг по вайтлисту.")
        return []

    print(f"   🔍 Найдено {len(allowed_league_ids)} подходящих лиг. Загружаю матчи...")
    
    all_matchups = []
    for lg_id in allowed_league_ids:
        matchups = await fetch_pinnacle_data(f"/leagues/{lg_id}/matchups")
        if matchups:
            for m in matchups:
                m["_league_name"] = next((l["name"] for l in leagues if l["id"] == lg_id), "Футбол")
                all_matchups.append(m)

    return all_matchups

async def fetch_pinnacle_odds(matchup_ids):
    print(f"📥 Загружаю коэффициенты для {len(matchup_ids)} матчей...")
    odds_data = {}
    for mid in matchup_ids:
        markets = await fetch_pinnacle_data(f"/matchups/{mid}/markets/straight")
        if markets:
            odds_data[mid] = markets
    return odds_data

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
    print("🔄 [Scraper] Запуск (Pinnacle)...")

    old_matches_dict = await firebase_get("matches") or {}
    if not isinstance(old_matches_dict, dict): old_matches_dict = {}

    finished_known = await firebase_get("finished_matches") or {}
    if not isinstance(finished_known, dict): finished_known = {}

    raw_cache = await firebase_get("team_logos") or {}
    logo_cache = _cache_from_fb(raw_cache)
    print(f"📥 В кэше логотипов: {len(logo_cache)}")

    matchups = await fetch_pinnacle_matchups()
    if not matchups:
        print("❌ Матчи не получены. Завершаю.")
        return

    matchup_ids = [m["id"] for m in matchups]
    odds_map = await fetch_pinnacle_odds(matchup_ids)

    all_matches = []
    now_ts = time.time()

    for m in matchups:
        m_id = m.get("id")
        if not m_id: continue

        league_name = m.get("_league_name", "Футбол")
        home = m.get("home", "")
        away = m.get("away", "")
        
        if not is_valid_match(home, away, league_name): continue

        start_time_str = m.get("startTime")
        start_ts = 0
        if start_time_str:
            try:
                start_ts = int(time.mktime(time.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")))
            except:
                pass

        status = "Скоро"
        if m.get("isLive"): status = "LIVE"
        elif start_ts and start_ts < now_ts: status = "LIVE"

        all_matches.append({
            "id": m_id, "home": home, "away": away,
            "league": league_name, "start_ts": start_ts,
            "status_type": status, "matchup": m
        })

    print(f"⚽ Всего валидных матчей: {len(all_matches)}")

    missing = set()
    for m in all_matches:
        for t in (m["home"], m["away"]):
            if not t: continue
            hint = league_to_country(m["league"]) or ""
            ex = logo_cache.get(f"{t}|{hint}") or logo_cache.get(t)
            force = (t in FOTMOB_ID_OVERRIDES) or (t in DIRECT_LOGO_URLS) or (not ex) or _is_fallback(ex)
            if force: missing.add((t, m["league"], force))

    if missing:
        print(f"🔎 Поиск логотипов для {len(missing)} пар...")
        teams_to_search = list({t for t, _, _ in missing})
        name_en_map = batch_translate_ru_to_en(teams_to_search)
        t0 = time.time()
        await search_all_logos(list(missing), logo_cache, name_en_map)
        print(f"✅ Обработано за {time.time()-t0:.1f}s")
        print(f"📊 fotmob={LOGO_STATS['fotmob']}, thesportsdb={LOGO_STATS['thesportsdb']}, direct={LOGO_STATS['direct']}, fallback={LOGO_STATS['fallback']}, cache={LOGO_STATS['cache']}")

    ok = await firebase_put("team_logos", _cache_to_fb(logo_cache))
    print(f"💾 Кэш логотипов: {len(logo_cache)} записей, ok={ok}")
    if FALLBACK_TEAMS:
        print(f"🚨 БЕЗ ЛОГОТИПОВ: {list(set(FALLBACK_TEAMS))}")

    matches_dict = {}
    for m in all_matches:
        mid = f"pinnacle_{m['id']}"
        if mid in finished_known: continue

        t1 = m["home"]; t2 = m["away"]
        hint = league_to_country(m["league"]) or ""
        hl = find_logo(logo_cache, t1, hint)
        al = find_logo(logo_cache, t2, hint)

        odds = odds_map.get(m["id"], [])
        parsed_markets = parse_pinnacle_odds(odds, t1, t2)
        
        p1 = px = p2 = None
        if "Исход" in parsed_markets:
            for o in parsed_markets["Исход"]:
                if o["name"] == "П1": p1 = o["odds"]
                elif o["name"] == "Х": px = o["odds"]
                elif o["name"] == "П2": p2 = o["odds"]

        score = "VS"
        status_str = m["status_type"]
        if status_str == "LIVE":
            status_str = "LIVE" # Детали счета можно будет добавить позже

        time_display = status_str
        if status_str == "Скоро" and m["start_ts"]:
            time_display = time.strftime("%d.%m %H:%M", time.localtime(m["start_ts"]))

        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": hl, "awayLogo": al, "league": m["league"],
            "status": time_display, "score": score,
            "start_time": m["start_ts"],
            "odds": {"1": p1, "X": px, "2": p2},
            "markets": parsed_markets
        }

    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей")

if __name__ == "__main__":
    asyncio.run(main())