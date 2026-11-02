import asyncio
import json
from curl_cffi import requests as cffi_requests

BASE_URL = "https://line-lb51.bk6bba-resources.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fon.bet/",
}

def get_data(url):
    r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
    if r.status_code == 200:
        return r.json()
    return None

def find_id(data, target_id, path=""):
    if isinstance(data, dict):
        if data.get("id") == target_id or data.get("sportId") == target_id:
            print(f"📍 Найдено по пути: {path}")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:800])
        for k, v in data.items():
            find_id(v, target_id, f"{path}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            find_id(v, target_id, f"{path}[{i}]")

async def main():
    print("🔍 Ищем ID 11935 (РПЛ) во всем JSON...")
    data = await asyncio.to_thread(get_data, f"{BASE_URL}/events/list?scopeMarket=1600&lang=ru")
    
    find_id(data, 11935)
    
    print("\n🔍 Ищем sportId 11935 в событиях...")
    events = data.get("events", [])
    for ev in events:
        if ev.get("sportId") == 11935:
            print("Пример события с sportId=11935:")
            print(json.dumps(ev, ensure_ascii=False, indent=2))
            break

if __name__ == "__main__":
    asyncio.run(main())