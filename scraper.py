import requests

def search_fotmob(team_name):
    print(f"\n--- Поиск в FotMob: {team_name} ---")
    url = f"https://www.fotmob.com/api/data/search/suggest?term={team_name}&lang=ru"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.fotmob.com/"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            
            # Перебираем группы (All, Teams, Matches...)
            for group in data:
                suggestions = group.get("suggestions", [])
                
                # Ищем внутри группы команду
                for item in suggestions:
                    if item.get("type") == "team":
                        team_id = item.get("id")
                        name = item.get("name")
                        if team_id:
                            logo_url = f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
                            print(f"  ✅ Найдено: {name} (ID: {team_id})")
                            print(f"  🔗 Логотип: {logo_url}")
                            return logo_url # Возвращаем первый найденный логотип
    except Exception as e:
        print(f"  ❌ Исключение: {e}")
    return None

if __name__ == "__main__":
    search_fotmob("Галатасарай")
    search_fotmob("Зенит")
    search_fotmob("Интер")