from datetime import datetime, timedelta

import aiohttp
import pytz
import asyncio
import base64
import requests


# 获取 Emby 基本信息
async def get_emby_base() -> dict:
    """
    获取 Emby 基本配置信息
    :return: 基本信息字典
    """
    async with aiohttp.ClientSession() as session:
        async with session.get("https://wiremock.imold.wang/app/mock/16/baseinfo") as response:
            return await response.json()


# 构建 Emby 请求 URL
async def build_emby_url(base_url: str, path: str, user: str, token: str, params: dict = None) -> str:
    """
    构建 Emby API 请求 URL
    :param base_url: 基本 URL
    :param path: 请求路径
    :param user: 用户名
    :param token: 用户 token
    :param params: 请求参数字典
    :return: 完整的请求 URL
    """
    params = params or {}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}{path}?UserId={user}&X-Emby-Token={token}&{query}"


# 获取搜索结果
async def fetch_emby_media_info(search_text: str) -> list:
    """
    根据搜索文本获取媒体信息
    :param search_text: 搜索关键词
    :return: 媒体信息列表
    """
    emby_base = await get_emby_base()
    url = await build_emby_url(
        emby_base["baseUrl"],
        "/emby/Users/{user}/Items".format(user=emby_base["user"]),
        emby_base["user"],
        emby_base["token"],
        {
            "Fields": "BasicSyncInfo,CanDelete,PrimaryImageAspectRatio,ProductionYear,Status,EndDate",
            "StartIndex": "0",
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "EnableImageTypes": "Primary,Backdrop,Thumb",
            "ImageTypeLimit": "1",
            "Recursive": "true",
            "SearchTerm": search_text,
        },
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data.get("Items", [])


# 根据 ID 获取媒体信息
async def fetch_media_info_by_id(media_id: str) -> dict:
    """
    根据媒体 ID 获取详细信息
    :param media_id: 媒体 ID
    :return: 媒体详情字典
    """
    emby_base = await get_emby_base()
    url = await build_emby_url(
        emby_base["baseUrl"],
        f"/emby/Users/{emby_base['user']}/Items/{media_id}",
        emby_base["user"],
        emby_base["token"],
        {"fields": "ShareLevel"},
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


# 获取剧集季信息
async def fetch_emby_seasons(media_info: dict) -> list:
    """
    获取剧集的季信息
    :param media_info: 媒体信息字典
    :return: 剧集季列表
    """
    emby_base = await get_emby_base()
    url = await build_emby_url(
        emby_base["baseUrl"],
        f"/emby/Shows/{media_info['Id']}/Seasons",
        emby_base["user"],
        emby_base["token"],
        {"Fields": "BasicSyncInfo,CanDelete,PrimaryImageAspectRatio,Overview"},
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data.get("Items", [])


# 获取图片 URL
async def fetch_image_url(series_id: str, tag: str) -> str:
    """
    获取指定剧集的图片 URL
    :param series_id: 剧集 ID
    :param tag: 图片标签
    :return: 图片 URL
    """
    emby_base = await get_emby_base()
    return await build_emby_url(
        emby_base["baseUrl"],
        f"/emby/Items/{series_id}/Images/Primary",
        emby_base["user"],
        emby_base["token"],
        {
            "tag": tag,
            "keepAnimation": "true",
            "quality": 90,
            "maxHeight": 492,
            "maxWidth": 328
        },
    )


# 格式化媒体信息
async def format_detailed_media_info(media_info: dict) -> str:
    """
    格式化媒体详情信息
    :param media_info: 媒体信息字典
    :return: 格式化后的媒体信息字符串
    """
    name = media_info.get("Name", "未知剧名")
    premiere_date = media_info.get("PremiereDate", "未知首播日期")[:10]
    overview = media_info.get("Overview", "暂无简介")
    rating = media_info.get("CommunityRating", "暂无评分")
    genres = ", ".join(media_info.get("Genres", []))
    item_url = f"https://emby.4348662.asia:16384/web/index.html#!/item?id={media_info.get('Id', '')}&serverId={media_info.get('ServerId', '')}"
    actors = "\n".join(
        f"- {person['Name']} (导演)" if person["Type"] == "Director" else f"- {person['Name']} 饰 {person.get('Role', '')}"
        for person in media_info.get("People", [])
    )
    links = " | ".join(f"[{url['Name']}]({url['Url']})" for url in media_info.get("ExternalUrls", []))

    return (
        f"🎬 剧名: 《{name}》\n"
        f"📆 首播日期: {premiere_date}\n"
        f"🏡 概述: {overview}\n"
        f"⭐ 评分: {rating}/10\n"
        f"🎥 类型: {genres}\n"
        f"🎭 演员:\n{actors}\n"
        f"🌐 更多信息: {links}\n"
        f"🌐 影片地址: {item_url}\n"
    )


# 异步函数 format_media_info_list
async def format_media_info_list(media_list: list) -> str:
    """
    格式化媒体信息列表，用于展示查询到的影片结果。
    :param media_list: 包含媒体信息的列表
    :return: 格式化的媒体信息字符串
    """
    if not media_list:
        return "未找到任何相关媒体信息。"

    formatted_list = ["🎥 查询到以下影片："]
    for index, media in enumerate(media_list, start=1):
        name = media.get("Name", "未知名称")
        year = media.get("ProductionYear", "未知年份")
        media_type = media.get("Type", "未知类型")
        type_cn = {"Series": "电视剧", "Movie": "电影"}.get(media_type, "未知类型")
        formatted_list.append(f"{index}. 【{name}】 ({year}) - 类型: {type_cn}")

    return "\n".join(formatted_list)


# 格式化电视剧详情
async def format_series_details(series_data: dict) -> str:
    """
    格式化电视剧详情信息
    :param series_data: 剧集数据字典
    :return: 格式化后的电视剧详情字符串
    """
    name = f"🎬 {series_data.get('SeriesName', '未知系列')} - {series_data.get('Name', '未知名称')}"
    premiere_date = f"📅 首播日期: {series_data.get('PremiereDate', '未知')[:10]}"
    overview = f"📖 简介:\n{series_data.get('Overview', '暂无简介')}"
    episode_count = f"📂 集数: {series_data.get('ChildCount', '未知')}"
    item_url = f"https://emby.4348662.asia:16384/web/index.html#!/item?id={series_data.get('Id', '')}&serverId={series_data.get('ServerId', '')}"
    item_formatted_info = f"🌐 影片地址: {item_url}\n"
    return f"{name}\n{premiere_date}\n{overview}\n{episode_count}\n{item_formatted_info}"


# 格式化系列信息列表
async def format_series_info_list(data: list) -> str:
    """
    格式化查询到的系列信息，供用户选择
    :param data: 剧集季数据列表
    :return: 格式化后的系列信息字符串
    """
    formatted_info = "查询到以下影片，输入数字查看对应影片详情，请在60秒内回复，过期取消。\n\n"
    for index, item in enumerate(data, start=1):
        name = item['SeriesName'] + item['Name']
        formatted_info += f"{index}. 🎬【{name}】\n"
        formatted_info += "-----------------------\n"
    return formatted_info


# 新增用户
async def emby_user_add(username: str) -> bool:
    """
    新增 Emby 用户
    :param username: 用户名
    :return: 是否成功
    """
    emby_base = await get_emby_base()
    url = f"{emby_base['baseUrl']}/emby/Users/New?&X-Emby-Token={emby_base['token']}"

    # 发送 POST 请求，使用 form-data 格式
    headers = {"Authorization": f"MediaBrowser Token={emby_base['token']}"}
    payload = {"Name": username}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=payload) as response:
            if response.status == 200:
                print(f"用户 {username} 新增成功！")
                return True
            else:
                print(f"用户 {username} 新增失败，状态码：{response.status}，响应内容：{await response.text()}")
                return False


# emby删除用户
async def emby_user_del(username: str) -> bool:
    """
    删除 Emby 用户
    :param username: 用户名
    :return: 是否成功
    """
    # 查询用户信息
    user = await fetch_emby_user_by_name(username)
    if not user:
        print(f"未找到用户 '{username}'，删除失败。")
        return False

    # 构造删除请求 URL
    user_id = user['Id']
    emby_base = await get_emby_base()
    url = (
        f"{emby_base['baseUrl']}/emby/Users/{user_id}/Delete"
        f"?UserId={emby_base['user']}&X-Emby-Token={emby_base['token']}"
    )

    # 发送 POST 请求删除用户
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url) as response:
                response.raise_for_status()  # 检查 HTTP 请求是否成功
                if response.status == 200 or response.status == 204:
                    print(f"用户 '{username}' 删除成功！")
                    return True
                else:
                    print(f"用户 '{username}' 删除失败，状态码: {response.status}，响应内容: {await response.text()}")
                    return False
    except aiohttp.ClientError as e:
        print(f"请求失败: {e}")
        return False


# 根据用户名全匹配搜索 Emby 用户
async def fetch_emby_user_by_name(username: str, limit: int = 100) -> dict:
    """
    根据用户名全匹配搜索 Emby 用户
    :param username: 用户名
    :param limit: 限制查询结果数量，默认 100
    :return: 匹配的用户信息字典，找不到返回 None
    """
    emby_base = await get_emby_base()
    url = await build_emby_url(
        emby_base["baseUrl"],
        "/emby/Users/Query",
        emby_base["user"],
        emby_base["token"],
        {
            "IncludeItemTypes": "User",
            "StartIndex": "0",
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "EnableImageTypes": "Primary,Backdrop,Thumb",
            "ImageTypeLimit": "1",
            "Limit": limit,
        },
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
    except aiohttp.ClientError as e:
        print(f"获取用户列表失败: {e}")
        return None

    # 从返回的用户列表中查找匹配的用户
    for user in data.get("Items", []):
        if user.get("Name") == username:
            return user

    print(f"未找到匹配的用户: {username}")
    return None


def format_user_info(users):
    formatted_info = "📋 Emby 用户信息\n\n"

    # 设置北京时间（UTC+8）
    beijing_tz = pytz.timezone("Asia/Shanghai")

    for index, user in enumerate(users, start=1):
        name = user.get('Name', '未知')
        prefix = user.get('Prefix', '无')
        date_created = user.get('DateCreated', '无记录')
        last_login = user.get('LastLoginDate', '无记录')
        last_activity = user.get('LastActivityDate', '无记录')
        user_id = user.get('Id', '未知')
        server_id = user.get('ServerId', '未知')
        is_admin = user['Policy'].get('IsAdministrator', False)
        is_disabled = user['Policy'].get('IsDisabled', False)
        has_password = user.get('HasPassword', False)

        # 转换日期格式
        def format_datetime(iso_date):
            if iso_date and iso_date != '无记录':
                try:
                    # 移除 Z 并截取到小数秒的前 6 位
                    iso_date = iso_date.rstrip("Z")
                    if "." in iso_date:
                        main, fraction = iso_date.split(".")
                        iso_date = f"{main}.{fraction[:6]}"
                    # 解析时间字符串
                    parsed_date = datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%S.%f")
                    # 将时间转换为 UTC 时间，并添加北京时间差值
                    parsed_date = pytz.utc.localize(parsed_date)
                    # 转为北京时间 (UTC+8)
                    beijing_time = parsed_date + timedelta(hours=8)
                    return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return "无效时间格式"
            return "无记录"

        date_created = format_datetime(date_created)
        last_login = format_datetime(last_login)
        last_activity = format_datetime(last_activity)

        # 格式化用户状态
        admin_status = "管理员" if is_admin else "普通用户"
        account_status = "✅ 正常" if not is_disabled else "❌ 已禁用"
        password_status = "已设置" if has_password else "未设置"

        formatted_info += (
            f"{index}. 🎭 用户名: {name} ({prefix})\n"
            f"   🗓️ 创建时间: {date_created}\n"
            f"   🗓️ 上次登录: {last_login}\n"
            f"   🗓️ 最后活动: {last_activity}\n"
            f"   🛡️ 用户类型: {admin_status}\n"
            f"   🛠️ 账号状态: {account_status}\n"
            f"   🔑 密码状态: {password_status}\n"
            # f"   🆔 用户ID: {user_id}\n"
            # f"   🌐 服务器ID: {server_id}\n"
            "-----------------------\n"
        )

    formatted_info += "\n💡 想了解更多用户信息？请联系管理员！"
    return formatted_info


# 模糊匹配搜索用户
async def fetch_emby_user_by_partial_name(partial_name: str, limit: int = 1000) -> list:
    """
    根据用户名模糊匹配搜索 Emby 用户
    :param partial_name: 用户名片段
    :param limit: 限制查询结果数量，默认 100
    :return: 匹配的用户信息列表，找不到返回空列表
    """
    emby_base = await get_emby_base()
    url = await build_emby_url(
        emby_base["baseUrl"],
        "/emby/Users/Query",
        emby_base["user"],
        emby_base["token"],
        {
            "IncludeItemTypes": "User",
            "StartIndex": "0",
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "EnableImageTypes": "Primary,Backdrop,Thumb",
            "ImageTypeLimit": "1",
            "Limit": limit,
        },
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
    except aiohttp.ClientError as e:
        print(f"获取用户列表失败: {e}")
        return []

    if partial_name == '':
        return format_user_info(data.get("Items", []))

    # 筛选包含部分名称的用户
    matched_users = [
        user for user in data.get("Items", [])
        if partial_name.lower() in user.get("Name", "").lower()
    ]

    if not matched_users or len(matched_users) == 0:
        print(f"未找到包含 '{partial_name}' 的用户")
        return f"未找到包含 '{partial_name}' 的用户"

    # 格式化返回的信息
    return format_user_info(matched_users)


def format_emby_in_info(data):
    # 设置北京时间（UTC+8）
    beijing_tz = pytz.timezone("Asia/Shanghai")

    def format_datetime(iso_date):
        if iso_date:
            try:
                # 移除 Z 并截取到小数秒的前 6 位
                iso_date = iso_date.rstrip("Z")
                if "." in iso_date:
                    main, fraction = iso_date.split(".")
                    iso_date = f"{main}.{fraction[:6]}"
                # 解析时间字符串
                parsed_date = datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%S.%f")
                # 将时间转换为 UTC 时间，并添加北京时间差值
                parsed_date = pytz.utc.localize(parsed_date)
                # 转为北京时间 (UTC+8)
                beijing_time = parsed_date + timedelta(hours=8)
                return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return "无效时间格式"
        return "无记录"

    formatted_info = "📋 Emby新影片入库啦 影片信息\n\n"

    title = data.get('Title', None)
    description = data.get('Description', None)
    event = data.get('Event', None)
    item = data.get('Item', {})

    name = item.get('Name', None)
    original_title = item.get('OriginalTitle', None)
    date_created = item.get('DateCreated', None)
    premiere_date = item.get('PremiereDate', None)
    genres = item.get('Genres', None)
    community_rating = item.get('CommunityRating', None)
    file_name = item.get('FileName', None)
    production_year = item.get('ProductionYear', None)
    studios = item.get('Studios', None)
    external_urls = item.get('ExternalUrls', None)

    # 提取 Path 中的分类（国产剧）
    path = item.get('Path', '')
    category = path.split('/')[3] if path else None

    # 格式化日期
    date_created = format_datetime(date_created) if date_created else None
    premiere_date = format_datetime(premiere_date) if premiere_date else None

    # 构建影片的 URL 地址
    item_url = f"https://emby.4348662.asia:16384/web/index.html#!/item?id={item.get('Id', '')}&serverId={item.get('ServerId', '')}"

    # 添加标题
    if title:
        formatted_info += f"🎬 影片标题: {str(title).split(' ')[2]}\n"
    # 添加上映日期
    if premiere_date:
        formatted_info += f"📅 上映日期: {premiere_date}\n"
    # 添加创建日期
    if date_created:
        formatted_info += f"🗓️ 创建日期: {date_created}\n"
    # 添加类型
    if genres:
        formatted_info += f"🎞️ 类型: {', '.join(genres)}\n"  # 显示类型（Genres）
    # 添加分类
    if category:
        formatted_info += f"📂 分类: {category}\n"  # 显示分类（Category）
    # 添加文件名
    if file_name:
        formatted_info += f"🎥 文件名: {file_name}\n"
    # 添加生产年份
    if production_year:
        formatted_info += f"📅 生产年份: {production_year}\n"
    # 添加制片公司
    if studios:
        formatted_info += f"🏢 制片公司: {', '.join([studio['Name'] for studio in studios])}\n"
    # 添加外部链接
    if external_urls:
        formatted_info += f"🔗 外部链接:\n"
        formatted_info += "\n".join([f"{url['Name']}: {url['Url']}" for url in external_urls]) + "\n"
    # 添加影片地址
    formatted_info += f"🌐 影片地址: {item_url}\n"

    return formatted_info


async def image_url_to_base64(image_url):
    # 发送请求获取图片
    response = requests.get(image_url)

    if response.status_code == 200:
        # 将图片内容转换为 base64
        img_data = response.content
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return img_base64
    else:
        raise Exception("无法获取图片，HTTP 状态码: " + str(response.status_code))
