import requests
import urllib.parse

def test_sportsapi_pro(team_name):
    print(f"\n--- SportsAPI Pro (V3 Search): {team_name} ---")
    # Пробуем с ключом и без (вдруг поиск тоже открыт)
    urls = [
        f"https://api.sportsapipro.com/v3/football/search?q={urllib.parse.quote(team_name)}",
        f"https://api.sportsapipro.com/v1/search?q={urllib.parse.quote(team_name)}"
    ]
    headers_variants = [
        {}, # без ключа
        {"x-api-key": "test"} # с фейковым ключом (на случай если проверяют наличие)
    ]
    
    for url in urls:
        for headers in headers_variants:
            try:
                r = requests.get(url, headers=headers, timeout=10)
                print(f"  URL: {url.split('?')[0]}, Headers: {list(headers.keys())}")
                print(f"    Статус: {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    if results:
                        # Ищем тип team
                        for item in results:
                            if item.get("participantType") == "team":
                                logo = item.get("logo")
                                print(f"    ✅ Найдено: {item.get('title')}")
                                print(f"    🔗 Логотип: {logo}")
                                return logo
                    else:
                        print("    ⚠️ Результатов нет")
                else:
                    print(f"    ❌ Ответ: {r.text[:100]}")
            except Exception as e:
                print(f"    ❌ Ошибка: {e}")
    return None

def test_thesportsdb(team_name):
    print(f"\n--- TheSportsDB (Free Key 3): {team_name} ---")
    # TheSportsDB ищет по английскому названию
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={urllib.parse.quote(team_name)}"
    try:
        r = requests.get(url, timeout=10)
        print(f"  URL: {url}")
        print(f"    Статус: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            teams = data.get("teams") or []
            if teams:
                for team in teams[:2]: # первые 2 результата
                    badge = team.get("strTeamBadge") or team.get("strTeamLogo")
                    if badge:
                        print(f"    ✅ Найдено: {team.get('strTeam')}")
                        print(f"    🔗 Логотип: {badge}")
                        return badge
            else:
                print("    ⚠️ Команда не найдена")
        else:
            print(f"    ❌ Ответ: {r.text[:100]}")
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    return None

if __name__ == "__main__":
    # Тестируем на примере Зенита (можно заменить на любой клуб)
    team_ru = "Зенит"
    team_en = "Zenit" 
    
    print(f"🚀 Тестируем получение логотипа для: {team_ru} ({team_en})")
    
    logo_sportsapi = test_sportsapi_pro(team_en)
    logo_tsdb = test_thesportsdb(team_en)
    
    print("\n=== ИТОГ ===")
    if logo_sportsapi:
        print(f"✅ SportsAPI Pro работает! Ссылка: {logo_sportsapi}")
    elif logo_tsdb:
        print(f"✅ TheSportsDB работает! Ссылка: {logo_tsdb}")
    else:
        print("❌ Ни один из источников не сработал. Нужно менять подход.")