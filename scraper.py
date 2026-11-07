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
FONBET_LINE_URL = "https://line52.bkfon-resources.com/events/list?lang=ru&version=7175598316&scopeMarket=1600"
FONBET_LIVE_URL = "https://line-lb.bkfon-resources.com/events/list?lang=ru&version=7175598316&scopeMarket=1600"
FOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fotmob.com/"
}

# ... (BLACKLIST_WORDS, ALLOWED_LEAGUES, FOTMOB_ID_OVERRIDES, TEAM_OVERRIDES, LEAGUE_COUNTRY_HINTS и функции логотипов — оставь без изменений, как в предыдущем scraper.py) ...

# ============ FONBET ПАРСЕР ============

def fetch_fonbet_matches(url):
    """Загружает JSON с событиями Fonbet."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
    for _ in range(2):
        try:
            r = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception: time.sleep(1)
    return None

def parse_fonbet_odds(ev_data):
    """Парсит полную роспись из структуры Fonbet."""
    markets = {}
    # Fonbet хранит рынки в ev_data['markets'] или в ev_data['customFactors']
    # В реальном JSON структура может быть сложной, здесь — общий парсер
    for market in ev_data.get("markets", []):
        group_name = None
        mt = market.get("marketType", "").lower()
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
    line_data = fetch_fonbet_matches(FONBET_LINE_URL)
    live_data = fetch_fonbet_matches(FONBET_LIVE_URL)
    
    if not line_data or not live_data:
        print("❌ Не удалось загрузить данные Fonbet.")
        return
    
    # 2. Собираем все события
    all_events = []
    # В JSON Fonbet события лежат в packets -> events
    for packet in line_data.get("packets", []):
        all_events.extend(packet.get("events", []))
    for packet in live_data.get("packets", []):
        all_events.extend(packet.get("events", []))
    
    print(f"⚽ Всего событий: {len(all_events)}")
    
    # 3. Фильтруем и матчим с логотипами (упрощённо)
    # ... (здесь нужно применить is_valid_match и find_logo, как в предыдущем коде) ...
    
    # 4. Собираем matches_dict
    matches_dict = {}
    for ev in all_events:
        # Пример структуры: ev['id'], ev['team1'], ev['team2'], ev['startTime']
        ev_id = ev.get("id")
        if not ev_id: continue
        
        mid = f"fonbet_{ev_id}"
        t1 = ev.get("team1", "Команда 1")
        t2 = ev.get("team2", "Команда 2")
        
        # Парсим полную роспись
        markets_data = parse_fonbet_odds(ev)
        
        # Базовые П1/Х/П2
        p1 = px = p2 = None
        if "Исход" in markets_data:
            for o in markets_data["Исход"]:
                if o["name"] == "1": p1 = o["odds"]
                elif o["name"] == "X": px = o["odds"]
                elif o["name"] == "2": p2 = o["odds"]
        
        # Определяем статус (live или prematch)
        status = "LIVE" if ev.get("isLive") else "Скоро"
        
        matches_dict[mid] = {
            "title": f"{t1} - {t2}", "home": t1, "away": t2,
            "homeLogo": "", "awayLogo": "",  # Заполняется через find_logo
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