import requests

team_id = 158

urls_to_test = [
    f"https://www.olimp.bet/api/v4/teams/{team_id}/image",
    f"https://www.olimp.bet/api/v4/0/teams/{team_id}/image",
    f"https://www.olimp.bet/api/v4/teams/{team_id}/icon",
    f"https://www.olimp.bet/api/v4/0/teams/{team_id}/logo",
    f"https://www.olimp.bet/api/v4/teams/{team_id}/logo",
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
        
        if 'image' in content_type:
            print(f"   ✅ УСПЕХ! Это логотип. Размер: {len(response.content)} байт")
        else:
            print(f"   ❌ Не картинка (ответ: {response.text[:100]}...)")
        print("-" * 30)
    except Exception as e:
        print(f"URL: {url}")
        print(f"   ❌ Ошибка: {e}")
        print("-" * 30)