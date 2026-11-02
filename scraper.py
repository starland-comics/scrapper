import requests
import json

def search_fotmob(team_name):
    print(f"\n--- Поиск в FotMob: {team_name} ---")
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
            print(f"  Тип данных: {type(data)}")
            
            # Показываем первые 600 символов ответа для отладки
            print("  Фрагмент ответа (для понимания структуры):")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:600])
            
            # Пытаемся найти команду в зависимости от структуры
            found = False
            
            # Вариант 1: Ответ — это список
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("type") == "team":
                        payload = item.get("payload", {})
                        team_id = payload.get("id")
                        name = item.get("title")
                        if team_id:
                            logo_url = f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
                            print(f"  ✅ Найдено: {name} (ID: {team_id})")
                            print(f"  🔗 Логотип: {logo_url}")
                            found = True
                            break
            
            # Вариант 2: Ответ — это словарь с ключом suggest
            elif isinstance(data, dict):
                suggests = data.get("suggest", [])
                for item in suggests:
                    if isinstance(item, dict) and item.get("type") == "team":
                        payload = item.get("payload", {})
                        team_id = payload.get("id")
                        name = item.get("title")
                        if team_id:
                            logo_url = f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
                            print(f"  ✅ Найдено: {name} (ID: {team_id})")
                            print(f"  🔗 Логотип: {logo_url}")
                            found = True
                            break
            
            if not found:
                print("  ⚠️ Команда не найдена в ответе")
                
        else:
            print(f"  ❌ Ошибка: {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Исключение: {e}")
    return None

if __name__ == "__main__":
    search_fotmob("Галатасарай")
    search_fotmob("Зенит")
    search_fotmob("Интер")