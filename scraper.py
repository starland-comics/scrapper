import asyncio
import time
import httpx
import json
import urllib.parse
import difflib
from curl_cffi import requests as cffi_requests

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"

# ФУТБОЛ = vids[]=1. Для лайва работает, для линии - нет (выдает 400)
OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events?vids%5B%5D=1"
# ДЛЯ ЛИНИИ УБИРАЕМ vids, чтобы не было 400
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events"

FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

BLACKLIST_WORDS = ["люб", "жен", "u21", "u19", "u20", "юнош", "молод", "угл", "жк", "кк", "статистика"]

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
            data = r.json()
            translated = data[0][0][0]
            # Очищаем от лишних приставок
            translated = translated.replace(" FC", "").replace("FC ", "").replace(" FK", "").replace("FK ", "").strip()
            return translated
    except Exception:
        pass
    return text

def clean_team_name(name):
    """Убирает лишние приставки для лучшего поиска"""
    bad_words = ["ФК", "ФК ", " 04", " 05", " Москва", " Санкт-Петербург", " (люб)", " (жен)"]
    for w in bad_words:
        name = name.replace(w, "")
    return name.strip()

def search_fotmob_logo(team_name):
    # Варианты запросов для поиска
    queries = []
    
    # 1. Оригинальное название (русское)
    queries.append(team_name)
    
    # 2. Очищенное русское название
    cleaned = clean_team_name(team_name)
    if cleaned != team_name: queries.append(cleaned)
    
    # 3. Перевод на английский
    trans = translate_ru_to_en(team_name)
    if trans != team_name: queries.append(trans)
    
    # 4. Очищенный перевод
    trans_clean = clean_team_name(trans)
    if trans_clean not in queries: queries.append(trans_clean)

    for q in queries:
        try:
            url = f"{FOTMOB_SEARCH_URL}?term={urllib.parse.quote(q)}&lang=ru"
            r = cffi_requests.get(url, headers=FOTMOB_HEADERS, impersonate="chrome120", timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Ищем среди всех групп и предложений
                for group in data:
                    for item in group.get("suggestions", []):
                        if item.get("type") == "team":
                            found_name = item.get("name", "")
                            team_id = item.get("id")
                            
                            # Проверка на нечеткое совпадение (если в запросе > 4 символов)
                            if team_id and len(q) > 4:
                                ratio = difflib.SequenceMatcher(None, q.lower(), found_name.lower()).ratio()
                                if ratio > 0.5: # Если похоже хотя бы на 50%
                                    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
                            
                            # Для коротких запросов (например, "Порт") берем первый результат
                            elif team_id and len(q) <= 4:
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
    
    print("📥 Загружаю ЛИНИЮ с Olimpbet...")
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

    # Умный поиск логотипов
    missing_teams = set()
    for ev, _, _ in all_matches:
        t1 = ev.get("team1Name")
        t2 = ev.get("team2Name")
        if t1 and t1 not in logo_cache: missing_teams.add(t1)
        if t2 and t2 not in logo_cache: missing_teams.add(t2)

    if missing_teams:
        print(f"🔎 Умный поиск логотипов для {len(missing_teams)} команд...")
        for team in missing_teams:
            # Если уже пытались и не нашли (""), не тратим время
            if logo_cache.get(team) == "": continue
            
            logo = await asyncio.to_thread(search_fotmob_logo, team)
            if logo:
                logo_cache[team] = logo
                print(f"   ✅ {team}")
            else:
                logo_cache[team] = ""
                print(f"   ❌ {team} (не найдено)")
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