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
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

FIREBASE_DB_URL = "https://winstars-435f1-default-rtdb.firebaseio.com"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

# --- Твои фильтры (без изменений) ---
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

# ... (остальные константы: FOTMOB_ID_OVERRIDES, DIRECT_LOGO_URLS, TEAM_OVERRIDES, LOGO_COUNTRY_HINTS и т.д. — оставь как в предыдущем коде) ...

# --- Новый парсер WebSocket через Playwright ---
async def fetch_live_odds_via_websocket():
    """
    Открывает страницу live-футбола на Olimpbet, перехватывает WebSocket-сообщения
    и возвращает словарь {event_id: {market_name: [{name, odds}]}}.
    """
    print("🌐 Запускаю Playwright для перехвата WebSocket...")
    odds_data = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)

        # Слушаем WebSocket-соединения
        page.on("websocket", lambda ws: asyncio.create_task(handle_ws(ws, odds_data)))

        # Открываем страницу live-футбола (ID спорта 1)
        await page.goto("https://www.olimp.bet/app/live/1", wait_until="networkidle", timeout=60000)

        # Даём время на подгрузку начальных данных и несколько обновлений
        await asyncio.sleep(15)

        await browser.close()

    print(f"✅ Получено рынков для {len(odds_data)} событий.")
    return odds_data

async def handle_ws(ws, odds_data):
    """Обработчик входящих WebSocket-сообщений."""
    print(f"🔌 WebSocket подключён: {ws.url}")
    ws.on("framereceived", lambda payload: asyncio.create_task(process_ws_message(payload, odds_data)))

async def process_ws_message(payload, odds_data):
    """Парсит JSON из WebSocket и извлекает рынки."""
    try:
        data = json.loads(payload)
        # Структура сообщений Olimpbet может быть разной. Ищем ключевые поля.
        # Пример: {"type": "update", "eventId": 123, "markets": [...]}
        # Или: {"action": "update_event", "event": {...}}
        # Точная структура зависит от протокола. Здесь — общий парсер.
        event_id = None
        markets = None

        if isinstance(data, dict):
            # Пробуем разные возможные ключи
            event_id = data.get("eventId") or data.get("event_id") or data.get("id")
            markets = data.get("markets") or data.get("odds") or data.get("outcomes")
            if not event_id and "event" in data and isinstance(data["event"], dict):
                event_id = data["event"].get("id")
                markets = data["event"].get("markets") or data["event"].get("outcomes")
        
        # Если нашли event_id и markets — парсим
        if event_id and markets:
            parsed = {}
            for market in markets:
                group_name = market.get("groupName") or market.get("name") or "Другое"
                outcomes = market.get("outcomes") or []
                outs = []
                for out in outcomes:
                    name = out.get("shortName") or out.get("name")
                    odds = out.get("probability") or out.get("odds") or out.get("price")
                    if name and odds:
                        outs.append({"name": name, "odds": odds})
                if outs:
                    parsed[group_name] = outs
            if parsed:
                odds_data[str(event_id)] = parsed
    except Exception:
        pass  # Игнорируем не-JSON или нерелевантные сообщения

# --- Остальные функции (fetch_olimp_matches, fetch_finished_matches, firebase_get, firebase_put, main) ---
# ... (оставь как в предыдущем scraper.py, но в main() используй fetch_live_odds_via_websocket() для получения полных рынков) ...

async def main():
    print("🔄 [Scraper] Запуск (WebSocket Playwright)...")

    # 1. Получаем полные рынки через WebSocket
    live_odds = await fetch_live_odds_via_websocket()

    # 2. Загружаем остальные данные (матчи, логотипы, результаты) как раньше
    old_matches_dict = await firebase_get("matches") or {}
    finished_known = await firebase_get("finished_matches") or {}
    raw_cache = await firebase_get("team_logos") or {}
    logo_cache = _cache_from_fb(raw_cache)

    # Получаем список матчей из REST API (как раньше)
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
                        if status_type == "Скоро" and st and st < now_ts:
                            actual_status = "LIVE"
                        all_matches.append((ev, actual_status, comp_name))
                        count += 1
        return count

    parse(live_data, "LIVE")
    parse(line_data, "Скоро")

    # ... (дальше — логика сборки matches_dict, но теперь используем live_odds для полей markets) ...

    matches_dict = {}
    for ev, status_type, league_name in all_matches:
        ev_id = ev.get("id")
        mid = f"olimp_{ev_id}"
        if mid in finished_known: continue

        # Базовые поля
        t1 = ev.get("team1Name"); t2 = ev.get("team2Name")
        hint = league_to_country(league_name) or ""
        hl = find_logo(logo_cache, t1, hint)
        al = find_logo(logo_cache, t2, hint)

        # Базовые кэфы из REST (П1/Х/П2)
        p1 = px = p2 = None
        for out in ev.get("outcomes", []):
            gn = out.get("groupName", "").strip()
            sn = out.get("shortName", "").strip()
            prob = out.get("probability")
            if prob is None or not sn: continue
            if "Исход" in gn or "Результат" in gn:
                if sn in ["П1", "1"]: p1 = prob
                elif sn in ["X", "Х"]: px = prob
                elif sn in ["П2", "2"]: p2 = prob

        # Полные рынки из WebSocket (если есть)
        ws_markets = live_odds.get(str(ev_id), {})
        # Если WebSocket не дал рынки, оставляем базовые
        if not ws_markets and p1 and px and p2:
            ws_markets = {"Исход": [
                {"name": "П1", "odds": p1},
                {"name": "Х", "odds": px},
                {"name": "П2", "odds": p2},
            ]}

        score = "VS"; status_str = status_type
        if status_type == "LIVE":
            sc, mn = extract_live_score_and_time(ev)
            if sc: score = sc
            status_str = build_status("LIVE", mn)

        time_display = status_str
        if status_type == "Скоро":
            st = ev.get("startDateTime")
            if st: time_display = time.strftime("%d.%m %H:%M", time.localtime(st))

        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": hl, "awayLogo": al, "league": league_name,
            "status": time_display, "score": score,
            "start_time": ev.get("startDateTime"),
            "odds": {"1": p1, "X": px, "2": p2},
            "markets": ws_markets
        }

    if matches_dict:
        await firebase_put("matches", matches_dict)
        print(f"🔥 Сохранено {len(matches_dict)} матчей (с полной росписью из WebSocket)")

if __name__ == "__main__":
    asyncio.run(main())