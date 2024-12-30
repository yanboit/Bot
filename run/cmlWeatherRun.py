from mirai import GroupMessage, Image
from plugins.cmlWeather import fetch_weather, format_weather


def main(bot, logger):
    logger.info("启用天气查询功能")

    @bot.on(GroupMessage)
    async def tell_weather(event: GroupMessage):
        """处理天气查询请求"""
        if str(event.message_chain).startswith("天气"):  # 判断是否为天气查询消息
            try:
                city = str(event.message_chain).replace("天气", "").strip()  # 提取城市名
                weather_data = await fetch_weather(city)  # 异步获取天气数据
                logger.info(weather_data)  # 打印获取的天气数据
                formatted_weather = format_weather(weather_data)  # 格式化天气数据
                await bot.send(event, formatted_weather, True)  # 向群内发送格式化的天气信息
            except Exception as e:
                logger.error(f"查询失败: {e}")  # 记录错误日志
                await bot.send(event, "查询失败，请检查网络连接或城市名称。")
