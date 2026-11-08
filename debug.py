import json
from curl_cffi import requests as cffi_requests

FONBET_BASE = "https://line-lb51.bk6bba-resources.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fon.bet/",
    "Origin": "https://www.fon.bet"
}

# Твои текущие маппинги (скопированы из main.py)
FONBET_FACTORS = {
    921: ("Исход", "П1", False), 922: ("Исход", "Х", False), 923: ("Исход", "П2", False),
    924: ("Двойной шанс", "1Х", False), 925: ("Двойной шанс", "12", False), 926: ("Двойной шанс", "Х2", False),
    927: ("Обе забьют", "Нет", False), 928: ("Обе забьют", "Да", False),
    930: ("Тотал", "ТБ", True), 931: ("Тотал", "ТМ", True),
    910: ("Фора", "Ф1", True), 912: ("Фора", "Ф2", True),
    989: ("Фора", "Ф1", True), 991: ("Фора", "Ф2", True),
    1672: ("Фора", "Ф1", True), 1675: ("Фора", "Ф2", True),
    1677: ("Фора", "Ф1", True), 1678: ("Фора", "Ф2", True),
    1680: ("Фора", "Ф1", True), 1681: ("Фора", "Ф2", True),
    1683: ("Фора", "Ф1", True), 1684: ("Фора", "Ф2", True),
    1686: ("Фора", "Ф1", True), 1687: ("Фора", "Ф2", True),
    1809: ("Фора", "Ф1", True), 1810: ("Фора", "Ф2", True),
    1812: ("Фора", "Ф1", True), 1813: ("Фора", "Ф2", True),
    1815: ("Фора", "Ф1", True), 1816: ("Фора", "Ф2", True),
    1818: ("Фора", "Ф1", True), 1819: ("Фора", "Ф2", True),
    1821: ("Фора", "Ф1", True), 1822: ("Фора", "Ф2", True),
    1824: ("Фора", "Ф1", True), 1825: ("Фора", "Ф2", True),
    1827: ("Фора", "Ф1", True), 1828: ("Фора", "Ф2", True),
    1830: ("Фора", "Ф1", True), 1831: ("Фора", "Ф2", True),
    1696: ("Инд. тотал 1", "ТБ", True), 1697: ("Инд. тотал 2", "ТБ", True),
    1727: ("Инд. тотал 1", "ТБ", True), 1728: ("Инд. тотал 2", "ТБ", True),
    1730: ("Инд. тотал 1", "ТБ", True), 1731: ("Инд. тотал 2", "ТБ", True),
    1733: ("Инд. тотал 1", "ТБ", True), 1734: ("Инд. тотал 2", "ТБ", True),
    1736: ("Инд. тотал 1", "ТБ", True), 1737: ("Инд. тотал 2", "ТБ", True),
    1739: ("Инд. тотал 1", "ТБ", True), 1791: ("Инд. тотал 2", "ТБ", True),
    1793: ("Инд. тотал 1", "ТБ", True), 1794: ("Инд. тотал 2", "ТБ", True),
    1796: ("Инд. тотал 1", "ТБ", True), 1797: ("Инд. тотал 2", "ТБ", True),
    1799: ("Инд. тотал 1", "ТБ", True), 1800: ("Инд. тотал 2", "ТБ", True),
    1802: ("Инд. тотал 1", "ТБ", True), 1803: ("Инд. тотал 2", "ТБ", True),
    1805: ("Инд. тотал 1", "ТБ", True), 1806: ("Инд. тотал 2", "ТБ", True),
    1569: ("Тотал", "ТМ", True), 1571: ("Тотал", "ТМ", True), 1572: ("Тотал", "ТБ", True),
    1854: ("Тотал", "ТБ", True), 1871: ("Тотал", "ТМ", True),
    1873: ("Тотал", "ТБ", True), 1874: ("Тотал", "ТМ", True),
    1880: ("Тотал", "ТБ", True), 1881: ("Тотал", "ТМ", True),
    1883: ("Тотал", "ТБ", True), 1884: ("Тотал", "ТМ", True),
    1886: ("Тотал", "ТБ", True), 1887: ("Тотал", "ТМ", True),
    2203: ("Тотал", "ТБ", True), 2204: ("Тотал", "ТМ", True),
    4241: ("Обе забьют 1-й тайм", "Нет", False), 4242: ("Обе забьют 1-й тайм", "Да", False),
}

TARGET_TEAMS = ["Крылья Советов", "Оренбург"]

def _format_param(p):
    if p is None: return None
    try: p_val = float(p)
    except: return str(p)
    if p_val != int(p_val): return f"{p_val:g}"
    p_int = int(p_val)
    if abs(p_int) >= 100: return f"{p_int / 100:g}"
    elif abs(p_int) >= 10: return f"{p_int / 10:g}"
    return str(p_int)

def find_target_event():
    url = f"{FONBET_BASE}/events/listBase?scopeMarket=1600&lang=ru"
    r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=30)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}")
        return None, None, None
    
    data = r.json()
    events = data.get("events", [])
    custom_factors = data.get("customFactors", [])
    factors = data.get("factors", [])
    
    target_ev = None
    for ev in events:
        t1 = ev.get("team1", "")
        t2 = ev.get("team2", "")
        if TARGET_TEAMS[0] in t1 and TARGET_TEAMS[1] in t2:
            target_ev = ev
            break
    
    if not target_ev:
        print("❌ Матч не найден")
        return None, None, None
    
    eid = target_ev.get("id")
    print(f"✅ Найдено: {target_ev.get('team1')} vs {target_ev.get('team2')} | id={eid}\n")
    
    return target_ev, factors, custom_factors

def dump_full(ev, factors, custom_factors):
    eid = ev.get("id")
    
    # Собираем ВСЕ факторы для этого eid (basic + custom)
    all_for_event = []
    
    # Basic factors
    basic_for_ev = [f for f in factors if f.get("e") == eid]
    print(f"📊 basic factors для eid={eid}: {len(basic_for_ev)}")
    
    # Custom factors
    print(f"📊 customFactors СТРУКТУРА:")
    for i, cf in enumerate(custom_factors[:3]):
        print(f"   [{i}] keys: {list(cf.keys())}")
        print(f"       e={cf.get('e')}, f={cf.get('f')}, v={cf.get('v')}, p={cf.get('p')}, gs={cf.get('gs')}")
        if "factors" in cf:
            fs = cf.get("factors", [])
            print(f"       → вложенных factors: {len(fs)}, первый: {fs[0] if fs else '—'}")
    
    print()
    custom_for_ev = [cf for cf in custom_factors if cf.get("e") == eid]
    print(f"📊 customFactors для eid={eid}: {len(custom_for_ev)} объектов\n")
    
    # Собираем flat список факторов из custom
    for cf in custom_for_ev:
        if "factors" in cf:
            for f in cf.get("factors", []):
                all_for_event.append(f)
        else:
            all_for_event.append(cf)
    
    print(f"📊 ВСЕГО факторов для eid={eid}: {len(all_for_event)}\n")
    print("="*70)
    print("📋 ВСЕ факторы (f | p | v | gs | ✅/❓ в FONBET_FACTORS | маппинг)")
    print("="*70)
    
    # Сортируем по f
    all_for_event.sort(key=lambda f: (f.get("f") or 0, str(f.get("p") or "")))
    
    matched = 0
    unknown_fids = set()
    
    for f in all_for_event:
        fid = f.get("f")
        p = f.get("p")
        v = f.get("v")
        gs = f.get("gs")
        p_str = _format_param(p) if p is not None else "—"
        
        if fid in FONBET_FACTORS:
            group, base, has_param = FONBET_FACTORS[fid]
            mapping = f"{group} / {base}"
            if has_param:
                mapping += f" {p_str}"
            marker = "✅"
            matched += 1
        else:
            mapping = "❌ НЕ ЗАМАПЛЕН"
            marker = "❓"
            unknown_fids.add(fid)
        
        print(f"  {marker} f={fid:>5} | p={p_str:>8} | v={str(v):>6} | gs={gs} | {mapping}")
    
    print("\n" + "="*70)
    print(f"📊 ИТОГ: {matched}/{len(all_for_event)} замаплено")
    print(f"❓ Неизвестные f-ID: {sorted(unknown_fids)}")
    
    # Показываем что получится в groups после парсинга
    groups = {}
    for f in all_for_event:
        fid = f.get("f")
        if fid not in FONBET_FACTORS: continue
        group, base, has_param = FONBET_FACTORS[fid]
        v = f.get("v")
        if v is None: continue
        try: v = float(v)
        except: continue
        if v <= 1.0: continue
        name = base
        if has_param:
            p_str = _format_param(f.get("p"))
            if p_str is None: continue
            try:
                pf = float(p_str)
                if pf > 0: name = f"{base} +{p_str}"
                else: name = f"{base} {p_str}"
            except: name = f"{base} {p_str}"
        
        if group not in groups: groups[group] = []
        groups[group].append({"name": name, "odds": v})
    
    print(f"\n📋 ИТОГОВЫЕ ГРУППЫ РЫНКОВ ({len(groups)} групп):")
    for g, outs in groups.items():
        print(f"   [{g}]: {len(outs)} рынков")
        for o in outs[:20]:
            print(f"      {o['name']} = {o['odds']}")

if __name__ == "__main__":
    ev, factors, custom = find_target_event()
    if ev:
        dump_full(ev, factors, custom)