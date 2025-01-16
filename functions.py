async def fetch_weather(session, city, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
    
    async with session.get(url) as response:
        if response.status == 200:
            result = await response.json()
            try:
                temp_kelvin = result["main"]["temp"]
                temp_celsius = temp_kelvin - 273.15
                return temp_celsius
            except KeyError:
                print(f"Не удалось получить температуру для {city}")
                return None
        elif response.status == 401:
            error_message = await response.json()
            raise ValueError(error_message["message"]) 
        else:
            print(f"Произошла ошибка при запросе погоды для {city}. Статус-код: {response.status}")
            return None
        


async def fetch_food_info(session, product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"

    async with session.get(url) as response:
        if response.status == 200:
            try:
                data = await response.json()
                products = data.get('products', [])
                if products:
                    first_product = products[0]
                    return {
                        'name': first_product.get('product_name', 'Неизвестно'),
                        'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
                    }
                return None
            except Exception as e:
                print(f"Произошла ошибка при парсинге JSON: {e}")
                return None
        else:
            print(f"Ошибка: статус-код {response.status}")
            return None

