import time
import json
from curl_cffi import requests as cffi_requests

FONBET_BASE = "https://line-lb51.bk6bba-resources.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
    "Origin": "https://www.fon.bet"
}

TARGET_TEAMS = ["Крылья Советов", "Оренбург"]

def find_event_id():
    """Ищет eventId в listBase?scopeMarket=1 и в ?scopeMarket=1600."""
    for sm in [1, 1600]:
        url = f"{FONBET_BASE}/events/listBase?scopeMarket={sm}&lang=ru"
        try:
            r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=30)
            if r.status_code != 200:
                print(f"❌ scopeMarket={sm}: HTTP {r.status_code}")
                continue
            data = r.json()
            events = data.get("events", [])
            factors = data.get("factors", [])
            custom_factors = data.get("customFactors", [])
            
            for ev in events:
                t1 = ev.get("team1", "")
                t2 = ev.get("team2", "")
                if TARGET_TEAMS[0] in t1 and TARGET_TEAMS[1] in t2:
                    eid = ev.get("id")
                    # Считаем факторы для этого события
                    cnt_basic = sum(1 for f in factors if f.get("e") == eid)
                    cnt_custom = 0
                    for cf in custom_factors:
                        if cf.get("e") == eid:
                            cnt_custom += len(cf.get("factors", []))
                    total = cnt_basic + cnt_custom
                    print(f"\n✅ Найдено в scopeMarket={sm}:")
                    print(f"   eventId={eid} | {t1} vs {t2}")
                    print(f"   startTime={ev.get('startTime')}")
                    print(f"   factors={cnt_basic} + customFactors={cnt_custom} = {total} шт")
                    return eid
            print(f"⚠️ scopeMarket={sm}: не найдено (events={len(events)})")
        except Exception as e:
            print(f"⚠️ scopeMarket={sm}: {e}")
    return None

def probe_endpoints(ev_id):
    """Пробует 12 эндпоинтов для получения полной линии."""
    print(f"\n🔍 Проверяю эндпоинты для eventId={ev_id}\n")
    
    endpoints = [
        # Стандартные
        f"/events/listBase?scopeMarket=1&eventIds={ev_id}&lang=ru",
        f"/events/listBase?scopeMarket=1600&eventIds={ev_id}&lang=ru",
        f"/events/list?scopeMarket=1&eventIds={ev_id}&lang=ru",
        f"/events/list?scopeMarket=1600&eventIds={ev_id}&lang=ru",
        # Альтернативные scopeMarket
        f"/events/listBase?scopeMarket=2&eventIds={ev_id}&lang=ru",
        f"/events/listBase?scopeMarket=3&eventIds={ev_id}&lang=ru",
        f"/events/listBase?scopeMarket=1600,1601&eventIds={ev_id}&lang=ru",
        f"/events/listBase?eventIds={ev_id}&lang=ru",
        # Прямые
        f"/events/{ev_id}?lang=ru",
        f"/event/{ev_id}?lang=ru",
        f"/api/v1/events/{ev_id}?lang=ru",
        f"/api/v2/events/{ev_id}?lang=ru",
        f"/api/v3/events/{ev_id}?lang=ru",
        f"/api/events/{ev_id}/markets?lang=ru",
        f"/line/events/{ev_id}?lang=ru",
    ]
    
    for ep in endpoints:
        url = FONBET_BASE + ep
        try:
            r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
            marker = "✅" if r.status_code == 200 else "❌"
            preview = ""
            factors_count = 0
            events_count = 0
            
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        factors_count = len(data.get("factors", []))
                        cf = data.get("customFactors", [])
                        factors_count += sum(len(x.get("factors", [])) for x in cf)
                        events_count = len(data.get("events", []))
                    elif isinstance(data, list):
                        events_count = len(data)
                except:
                    pass
                preview = f"| events={events_count}, factors={factors_count}"
            
            print(f"   {marker} [{r.status_code}] {ep} {preview}")
            
            # Если нашли эндпоинт с большим числом факторов — показываем
            if r.status_code == 200 and factors_count > 50 and events_count <= 5:
                print(f"\n   🎯 Найден полный эндпоинт с {factors_count} факторами!")
                try:
                    data = r.json()
                    factors = data.get("factors", [])
                    custom = data.get("customFactors", [])
                    for cf in custom:
                        factors.extend(cf.get("factors", []))
                    
                    # Печатаем все уникальные f-ID
                    fids = set()
                    for f in factors:
                        if f.get("e") == ev_id and f.get("f"):
                            fids.add(f.get("f"))
                    print(f"   Уникальные f-ID ({len(fids)}): {sorted(fids)}")
                except:
                    pass
        except Exception as e:
            print(f"   ❌ {ep} → {str(e)[:80]}")

def main():
    print("=" * 60)
    print("🔍 Debug: поиск полной линии для Крылья Советов – Оренбург")
    print("=" * 60)
    
    ev_id = find_event_id()
    if not ev_id:
        print("\n❌ Матч не найден ни в scopeMarket=1, ни в 1600")
        return
    
    probe_endpoints(ev_id)

if __name__ == "__main__":
    main()