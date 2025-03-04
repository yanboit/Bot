import asyncio
import httpx


# 异步获取天气信息
async def fetch_weather(city: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.lolimi.cn/API/weather/?city={city}")
        return response.json()


# 格式化天气数据
def format_weather(data) -> str:
    """
    格式化天气信息
    :param data: 天气数据字典
    :return: 格式化后的天气信息字符串
    """
    city = data["data"]["city"]
    current_weather = data["data"]["current"]
    warning = data["data"].get("warning", {})
    air_quality = current_weather["air_pm25"]
    visibility = current_weather["visibility"]

    # 天气主要信息
    weather_text = (
        f"嘿嘿，小可爱们注意啦！这里是最新鲜出炉的{city}天气播报哦～🎉\n\n"
        f"今天{city}{current_weather['weather']}，气温最高{current_weather['temp']}°C，"
        f"最低{data['data']['tempn']}°C，{current_weather['wind']}在风速{current_weather['windSpeed']}的舞台上交替登场～"
        f"空气质量超棒，PM2.5只有{air_quality}，能见度高达{visibility}！"
    )

    # 添加预警信息
    if warning:
        weather_text += (
            f"不过呀，市气象台还友情提醒：“{warning['color']}预警来啦！"
            f"{warning['warning']}”👗🧣\n\n"
        )

    # 添加建议
    living_indices = {item["name"]: item for item in data["data"]["living"]}
    morning_tips = living_indices.get("晨练指数", {}).get("tips", "适宜晨练哦！")
    shopping_tips = living_indices.get("逛街指数", {}).get("tips", "适合逛街呢！")
    fishing_tips = living_indices.get("钓鱼指数", {}).get("tips", "不太适合钓鱼哦！")
    mood_tips = living_indices.get("心情指数", {}).get("tips", "你的心情会很棒哦！")

    weather_text += (
        f"出门怎么安排？{morning_tips} {shopping_tips} "
        f"钓鱼和放风筝小憩一下吧，咱们下次再玩～"
        f"洗车党抓紧时间，赶紧让你的爱车闪亮登场！还有哦，这种晴朗好天气会让你的心情变得萌萌哒，"
        f"约会妥妥不受天气捣乱！🌞💕\n\n"
    )

    # 添加保养建议
    dryness_tips = living_indices.get("干燥指数", {}).get("tips", "别忘了做好保湿哦！")
    sunscreen_tips = living_indices.get("防晒指数", {}).get("tips", "注意涂抹防晒霜～")
    sunglasses_tips = living_indices.get("太阳镜指数", {}).get("tips", "带上太阳镜吧～")

    weather_text += (
        f"不过嘛，小手手有点干的宝宝别忘了抹润肤霜哦，{dryness_tips} "
        f"{sunscreen_tips} {sunglasses_tips} "
        f"让这个冬天也能活力满满～总之，{city}的今天是一个活泼又温暖的日子呢！✨"
    )

    return weather_text
