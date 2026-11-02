import requests

# ID Галатасарая из твоего лога
team_sb_id = 158
team_br_id = 3061

# Варианты URL, которые использует Олимп
urls_to_test = [
    f"https://www.olimp.bet/api/v4/0/team/{team_sb_id}/image",
    f"https://www.olimp.bet/api/v4/0/team/{team_br_id}/image",
    f"https://static.olimp.bet/team/{team_sb_id}.png",
    f"https://www.olimp.bet/img/team/{team_sb_id}.png"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for url in urls_to_test:
    try:
        response = requests.get(url, headers=headers, timeout=5)
        content_type = response.headers.get('Content-Type', '')
        
        print(f"URL: {url}")
        print(f"   Статус: {response.status_code}")
        print(f"   Тип контента: {content_type}")
        
        # Если это картинка (PNG или JPEG) - мы победили!
        if 'image' in content_type:
            print(f"   ✅ УСПЕХ! Это логотип. Размер: {len(response.content)} байт")
        else:
            print(f"   ❌ Это не картинка (наверное, JSON или HTML)")
        print("-" * 30)
    except Exception as e:
        print(f"URL: {url}")
        print(f"   ❌ Ошибка: {e}")
        print("-" * 30)