import asyncio
import time
import httpx
import json
import urllib.parse
from curl_cffi import requests as cffi_requests

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"

# ПРАВИЛЬНЫЕ ЭНДПОИНТЫ ОЛИМПА
OLIMP_LIVE_URL = "https://www.olimp.bet/api/v4/0/live/broadcast/sports-with-competitions-with-events"
OLIMP_LINE_URL = "https://www.olimp.bet/api/v4/0/line/top/sports-with-competitions-with-events?vids%5B%5D="

FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

# Фильтр мусора
BLACKLIST_WORDS = ["люб", "жен", "u21", "u19", "u20", "юнош", "молод"]

def is_valid_match(team1, team2, league):
    text = f"{team1} {team2} {league}".lower()
    for word in BLACKLIST_WORDS:
        if word in text:
            return False
    return True

def search_fotmob_logo(team_name):
    try:
        url = f"{FOTMOB_SEARCH_URL}?term={urllib.parse.quote(team_name)}&lang=ru"
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
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️ Ошибка Olimpbet: {e}")
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
            await client.put(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=30.0)
    except Exception:
        pass

async def main():
    print("🔄 [Scraper] Запуск гибридного парсера...")
    
    # 1. Загружаем кэш логотипов
    logo_cache = await firebase_get("team_logos") or {}
    print(f"📥 В кэше логотипов: {len(logo_cache)}")

    # 2. Загружаем данные с Olimpbet
    print("📥 Загружаю матчи с Olimpbet...")
    live_data = fetch_olimp_matches(OLIMP_LIVE_URL)
    line_data = fetch_olimp_matches(OLIMP_LINE_URL)
    
    all_matches = []
    
    # Функция для парсинга групп (Лайв и Линия)
    def parse_olimp_data(data, status_type):
        for sport_group in data:
            sport = sport_group.get("payload", {}).get("sport", {})
            if str(sport.get("id")) == "1":  # Футбол
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

    # 3. Ищем недостающие логотипы в FotMob
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
            await asyncio.sleep(0.1) # Защита от бана

    # 4. Сохраняем обновленный кэш
    await firebase_put("team_logos", logo_cache)

    # 5. Формируем итоговый JSON для Firebase
    matches_dict = {}
    for ev, status_type, league_name in all_matches:
        ev_id = ev.get("id")
        t1 = ev.get("team1Name")
        t2 = ev.get("team2Name")
        
        # Ищем коэффициенты 1X2
        p1, px, p2 = None, None, None
        for out in ev.get("outcomes", []):
            group_name = out.get("groupName", "")
            short_name = out.get("shortName", "")
            if "Исход" in group_name:
                if short_name == "П1": p1 = out.get("probability")
                elif short_name == "X": px = out.get("probability")
                elif short_name == "П2": p2 = out.get("probability")

        # Счет и время для лайва
        score = "VS"
        status_str = status_type
        if status_type == "LIVE":
            score1 = ev.get("score1", 0)
            score2 = ev.get("score2", 0)
            score = f"{score1} : {score2}"
            
            # Ищем время
            for out in ev.get("outcomes", []):
                if "минута" in out.get("groupName", "").lower() or "time" in out.get("shortName", "").lower():
                    status_str = f"LIVE {out.get('unprocessedName', '')}"
                    break
            if status_str == "LIVE":
                status_str = "LIVE" # Если время не нашли

        # Дата для прематча
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

    # 6. Сохраняем матчи в Firebase
    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Успешно сохранено {len(matches_dict)} матчей в Firebase!")
    else:
        print("⚠️ Матчей не найдено.")

if __name__ == "__main__":
    asyncio.run(main())