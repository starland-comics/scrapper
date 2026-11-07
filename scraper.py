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

# ✅ АКТУАЛЬНЫЕ ЭНДПОИНТЫ (на ноябрь 2026)
# Домен line-lb51 используется для лайва и линии, старый line52 может не работать.
FONBET_BASE_URL = "https://line-lb51.bk6bba-resources.com"
FONBET_LINE_PATH = "/events/listBase?scopeMarket=1600&lang=ru"
FONBET_LIVE_PATH = "/events/listBase?scopeMarket=1600&lang=ru&live=true" # Параметр live=true для лайва

FONBET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json", # ⚠️ Критически важно для получения JSON, а не HTML
    "Referer": "https://www.fon.bet/",
    "Origin": "https://www.fon.bet"
}

# ... (BLACKLIST_WORDS, ALLOWED_LEAGUES, FOTMOB_ID_OVERRIDES, TEAM_OVERRIDES, LEAGUE_COUNTRY_HINTS и функции логотипов — оставь без изменений, как в предыдущем scraper.py) ...

# ============ FONBET ПАРСЕР ============

def fetch_fonbet_data(url):
    """Загружает JSON с событиями Fonbet."""
    for _ in range(2):
        try:
            # Используем curl_cffi с impersonate="chrome120" для обхода защиты
            r = cffi_requests.get(url, headers=FONBET_HEADERS, impersonate="chrome120", timeout=30)
            if r.status_code == 200:
                try:
                    return r.json()
                except json.JSONDecodeError:
                    print(f"   ⚠️ Ответ не JSON (возможно, HTML). Первые 200 символов: {r.text[:200]}")
                    return None
            else:
                print(f"   ⚠️ HTTP {r.status_code} для {url}")
        except Exception as e:
            print(f"   ⚠️ Ошибка запроса: {e}")
            time.sleep(1)
    return None

def parse_fonbet_odds(ev_data):
    """Парсит полную роспись из customFactors."""
    markets = {}
    
    # Fonbet хранит коэффициенты в customFactors
    for custom_factor in ev_data.get("customFactors", []):
        factor_group = custom_factor.get("factors", [])
        if not factor_group:
            continue
        
        # Идентификатор группы факторов (например, 1X2, Тоталы, Форы)
        # В Fonbet `f` — это ID фактора, `v` — коэффициент
        # Для простоты группируем по типу, который можно определить по ID
        # Ниже — универсальный парсер, который сохраняет все факторы как есть
        
        group_name = None
        # Примерные ID групп (могут меняться, но обычно стабильны)
        # 921 - 1X2, 922 - Тотал, 923 - Фора, 924 - Обе забьют
        # Точные ID лучше смотреть в документации Fonbet MCP, но можно парсить все подряд
        
        # Если не знаем точный ID, сохраняем все факторы в общую группу
        if "factors" not in markets:
            markets["factors"] = []
        
        for factor in factor_group:
            fid = factor.get("f")  # ID фактора
            odds = factor.get("v") # Коэффициент
            
            if odds is None or float(odds) <= 1.0:
                continue
            
            markets["factors"].append({"name": str(fid), "odds": float(odds)})
    
    # Если customFactors пуст, пробуем старую структуру markets
    if not markets.get("factors"):
        for market in ev_data.get("markets", []):
            mt = market.get("marketType", "").lower()
            group_name = None
            if "1x2" in mt or "result" in mt:
                group_name = "Исход"
            elif "total" in mt:
                group_name = "Тотал"
            elif "handicap" in mt:
                group_name = "Фора"
            elif "both" in mt or "btts" in mt:
                group_name = "Обе забьют"
            
            if not group_name: continue
            if group_name not in markets: markets[group_name] = []
            
            for factor in market.get("factors", []):
                name = factor.get("name", "").strip()
                odds = factor.get("odds")
                if odds and float(odds) > 1.0:
                    markets[group_name].append({"name": name, "odds": float(odds)})
    
    return markets

async def main():
    print("🔄 [Scraper] Запуск (Fonbet)...")
    
    # 1. Загружаем JSON с Fonbet
    print("📥 Загружаю линию Fonbet...")
    line_url = FONBET_BASE_URL + FONBET_LINE_PATH
    live_url = FONBET_BASE_URL + FONBET_LIVE_PATH
    
    line_data = fetch_fonbet_data(line_url)
    live_data = fetch_fonbet_data(live_url)
    
    if not line_data and not live_data:
        print("❌ Не удалось загрузить данные Fonbet. Проверьте эндпоинты и заголовки.")
        return
    
    # 2. Собираем все события
    all_events = []
    # В JSON Fonbet события лежат в packets -> events
    for data in [line_data, live_data]:
        if not data: continue
        for packet in data.get("packets", []):
            all_events.extend(packet.get("events", []))
    
    print(f"⚽ Всего событий: {len(all_events)}")
    
    # 3. Фильтруем и матчим с логотипами (упрощённо)
    # ... (здесь нужно применить is_valid_match и find_logo, как в предыдущем коде) ...
    
    # 4. Собираем matches_dict
    matches_dict = {}
    for ev in all_events:
        ev_id = ev.get("id")
        if not ev_id: continue
        
        mid = f"fonbet_{ev_id}"
        t1 = ev.get("team1", "Команда 1")
        t2 = ev.get("team2", "Команда 2")
        
        # Парсим полную роспись
        markets_data = parse_fonbet_odds(ev)
        
        # Базовые П1/Х/П2 (если есть в markets_data)
        p1 = px = p2 = None
        if "Исход" in markets_data:
            for o in markets_data["Исход"]:
                if o["name"] == "1": p1 = o["odds"]
                elif o["name"] == "X": px = o["odds"]
                elif o["name"] == "2": p2 = o["odds"]
        
        status = "LIVE" if ev.get("isLive") else "Скоро"
        
        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": "", "awayLogo": "",
            "league": ev.get("sport", "Футбол"),
            "status": status, "score": "VS",
            "start_time": ev.get("startTime"),
            "odds": {"1": p1, "X": px, "2": p2},
            "markets": markets_data
        }
    
    # 5. Сохраняем в Firebase
    if matches_dict:
        async with httpx.AsyncClient() as client:
            r = await client.put(f"{FIREBASE_DB_URL}/matches.json", json=matches_dict, timeout=60.0)
            print(f"🔥 Сохранено {len(matches_dict)} матчей (status: {r.status_code})")

if __name__ == "__main__":
    asyncio.run(main())