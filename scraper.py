import requests
import urllib.parse

def test_thesportsdb_key123(team_name):
    print(f"\n--- TheSportsDB (Key 123): {team_name} ---")
    url = f"https://www.thesportsdb.com/api/v1/json/123/searchteams.php?t={urllib.parse.quote(team_name)}"
    try:
        r = requests.get(url, timeout=10)
        print(f"  Статус: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            teams = data.get("teams") or []
            if teams:
                badge = teams[0].get("strTeamBadge")
                if badge:
                    print(f"    ✅ Найдено: {teams[0].get('strTeam')}")
                    print(f"    🔗 Логотип: {badge}")
                    return badge
            else:
                print("    ⚠️ Команда не найдена")
        else:
            print(f"    ❌ Ответ: {r.text[:150]}")
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    return None

def test_sportsapipro_v1_search(team_name):
    print(f"\n--- SportsAPI Pro (V1 Search): {team_name} ---")
    # Пробуем разные варианты путей поиска
    urls = [
        f"https://api.sportsapipro.com/v1/football/search?q={urllib.parse.quote(team_name)}",
        f"https://api.sportsapipro.com/v1/search?q={urllib.parse.quote(team_name)}"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            print(f"  URL: {url.split('?')[0]}")
            print(f"    Статус: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                # Пытаемся найти результаты
                results = data.get("results") or data.get("data") or []
                if results:
                    for item in results:
                        if item.get("participantType") == "team":
                            team_id = item.get("id")
                            print(f"    ✅ Найдено: {item.get('title')} (ID: {team_id})")
                            # Формируем ссылку на логотип по шаблону V1
                            logo_url = f"https://api.sportsapipro.com/v1/football/images/competitors/{team_id}"
                            print(f"    🔗 Логотип: {logo_url}")
                            return logo_url
                else:
                    print("    ⚠️ Результатов нет")
            else:
                print(f"    ❌ Ответ: {r.text[:100]}")
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
    return None

if __name__ == "__main__":
    team_ru = "Зенит"
    team_en = "Zenit"
    
    print(f"🚀 Тестируем логотипы для: {team_ru} ({team_en})")
    
    logo_tsdb = test_thesportsdb_key123(team_en)
    logo_sapi = test_sportsapipro_v1_search(team_en)
    
    print("\n=== ИТОГ ===")
    if logo_tsdb:
        print(f"✅ TheSportsDB (ключ 123) работает! Ссылка: {logo_tsdb}")
    elif logo_sapi:
        print(f"✅ SportsAPI Pro V1 работает! Ссылка: {logo_sapi}")
    else:
        print("❌ Ни один из источников не сработал. Нужно менять подход.")