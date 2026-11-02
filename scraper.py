import requests
import json

def search_fotmob(team_name):
    print(f"\n--- Поиск в FotMob: {team_name} ---")
    # Актуальный эндпоинт поиска
    url = f"https://www.fotmob.com/api/data/search/suggest?term={team_name}&lang=ru"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.fotmob.com/"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  Статус: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            suggests = data.get("suggest", [])
            
            if not suggests:
                print("  ⚠️ Ничего не найдено")
                return None
                
            for s in suggests:
                # Ищем тип "team"
                if s.get("type") == "team":
                    payload = s.get("payload", {})
                    team_id = payload.get("id")
                    name = s.get("title")
                    if team_id:
                        logo_url = f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
                        print(f"  ✅ Найдено: {name} (ID: {team_id})")
                        print(f"  🔗 Логотип: {logo_url}")
                        return logo_url
        else:
            print(f"  ❌ Ошибка: {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Исключение: {e}")
    return None

if __name__ == "__main__":
    # Проверяем на русских названиях
    search_fotmob("Галатасарай")
    search_fotmob("Зенит")
    search_fotmob("Интер")