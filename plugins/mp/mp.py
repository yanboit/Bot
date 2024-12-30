import time

import aiohttp
import asyncio
import re

import base64
import requests

from mirai import GroupMessage, MessageChain, Image
from mirai.models import Forward, ForwardMessageNode
from collections import defaultdict

# 用户状态管理字典

user_search_states = defaultdict(lambda: {
    'waiting_message_id': None,
    'timeout_task': None,
    'is_waiting_for_reply': False,
    'current_medias': [],
    'reply_step': 0,
    'wait_time': 60,
    'current_seasons:': [],
    "cancel_sub": False
})


async def send_timeout_message(bot, event, user_id):
    """发送超时消息并重置状态"""
    await asyncio.sleep(user_search_states[user_id]['wait_time'])
    if user_search_states[user_id]['is_waiting_for_reply']:
        await bot.send(event, "超时未收到回复，取消查询。", True)
        reset_search_state(user_id)


def reset_search_state(user_id):
    """重置指定用户的搜索状态"""
    user_search_states[user_id].update({
        'waiting_message_id': None,
        'timeout_task': None,
        'is_waiting_for_reply': False,
        'current_medias': [],
        'reply_step': 0,
        'current_seasons': [],
        "cancel_sub": False
    })


async def get_mp_base():
    """
    获取 mp 基本配置信息
    :return: 基本信息字典
    """
    # async with aiohttp.ClientSession() as session:
    #     async with session.get("https://wiremock.imold.wang/app/mock/16/mp/subscribe") as response:
    #         return await response.json()
    token = read_token_from_file()
    json_data = {
        "baseUrl": "https://mp.4348662.asia:16384",
        "token": token
    }
    return json_data


# 获取sub img url
async def get_sub_img(tmdb_url):
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token
    url = f"{mp_url}/api/v1/system/cache/image?url={tmdb_url}"
    return url


async def image_url_to_base64(image_url):
    response = requests.get(image_url)

    if response.status_code == 200:
        # 将图片内容转换为 base64
        img_data = response.content
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return img_base64
    else:
        raise Exception("无法获取图片，HTTP 状态码: " + str(response.status_code))


async def sub_search(name: str, page=1) -> list:
    """
    根据名称搜索媒体信息
    :param page:
    :param name: 搜索的媒体名称
    :return: 搜索结果列表
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL 和 Headers
    search_url = f"{mp_url}/api/v1/media/search?page={page}&title={name}&type=media"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }

    # 发起 GET 请求
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers) as response:
            if response.status == 200:
                return await response.json()  # 返回 JSON 数据
            else:
                # 处理非 200 状态码的情况
                print(f"Request failed with status {response.status}")
                return []


async def sub_search_copy(name: str, page=1) -> list:
    """
    根据名称搜索媒体信息
    :param page:
    :param name: 搜索的媒体名称
    :return: 搜索结果列表
    """
    # 获取基础配置
    mp_url = "https://mp.4348662.asia:16384"  # 获取 base_url
    token = read_token_from_file()
    mp_token = token  # 获取 token

    # 构造请求 URL 和 Headers
    search_url = f"{mp_url}/api/v1/media/search?page={page}&title={name}&type=media"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }

    # 发起 GET 请求
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers) as response:
            if response.status == 200:
                return True  # 返回 JSON 数据
            else:
                if response.status == 403:
                    return False  # 返回 JSON 数据
                # 处理非 200 状态码的情况
                print(f"Request failed with status {response.status}")
                return []


async def format_single_subscribed_movie(movie_data):
    """
    格式化单条已订阅电影数据
    """
    message_chain = []

    # 提取影片数据
    title = movie_data.get("name", "未知标题")
    year = movie_data.get("year", "未知年份")
    season = movie_data.get("season", 0)
    description = movie_data.get("description", "暂无简介")
    rating = movie_data.get("vote", 0)
    category = movie_data.get("type", "未知分类")
    poster_link = movie_data.get("poster", "")
    backdrop_link = movie_data.get("backdrop", "")
    tmdb_id = movie_data.get("tmdbid", "无 TMDB ID")
    username = movie_data.get("username", "未知用户")
    date = movie_data.get("date", "未知日期")

    # 格式化文本内容
    formatted_text = (
        f"🎬 影片名: 《{title}》\n"
        f"📆 上映年份: {year}\n"
        f"📂 分类: {category}\n"
        f"📺 第几季: {season}\n"
        f"⭐ 评分: {rating}/10\n"
        f"🏡 简介: {description}\n"
        f"🔑 TMDB ID: {tmdb_id}\n"
        f"👤 订阅用户: {username}\n"
        f"📅 订阅日期: {date}\n"
    )

    # 添加文本消息
    message_chain.append({"type": "Plain", "text": formatted_text})

    # 添加海报图片（如果存在）
    if poster_link:
        message_chain.append({"type": "Image", "url": poster_link})

    return message_chain


# 格式化单条订阅数据
async def format_single_tv_show_data(tv_show_data):
    message_chain = []

    # 提取数据
    title = tv_show_data.get("title", "未知标题")
    release_date = tv_show_data.get("release_date", "未知日期")

    overview = tv_show_data.get("overview", "暂无简介")
    rating = tv_show_data.get("vote_average", 0.0)
    actors = tv_show_data.get("actors", [])
    detail_link = tv_show_data.get("detail_link", "无链接")
    poster_link = tv_show_data.get("poster_path", "")
    genres = tv_show_data.get("genres", ["未知类型"])
    category = tv_show_data.get("type", ["未知分类"])
    is_sub = tv_show_data.get("is_sub", "未订阅")
    img_url = tv_show_data.get("backdrop_path", None)

    # 演员处理
    actor_list = "暂无演员信息" if not actors else "\n".join([f"- {actor}" for actor in actors])

    # 格式化文本内容
    res = (
        f"🎬 剧名: 《{title}》\n"
        f"📅 订阅状态: {is_sub}\n"  # 加入订阅状态
        f"📂 分类: {category}\n"  # 显示分类（Category）
        f"📆 上映日期: {release_date}\n"
        f"🏡 简介: {overview}\n"
        f"⭐ 评分: {rating}/10\n"
        f"🎥 类型: {', '.join(genres)}\n"
        f"🎭 演员:\n{actor_list}\n"
        f"🌐 详情链接: {detail_link}\n"
        # f"🌐 图片地址: {img_url}\n"
    )

    # 添加文本消息
    message_chain.append({"type": "Plain", "text": res})

    # 添加图片消息
    # if img_url:
    #     img = await image_url_to_base64(img_url)
    #     message_chain.append(Image(base64=img))
    if img_url:
        message_chain.append({"type": "Image", "url": img_url})

    # 添加结尾提示
    # message_chain.append({"type": "Plain", "text": "\n\n💡 想了解更多影片信息？请联系管理员！"})

    return message_chain


# 查询所有订阅
async def fetch_all_subscriptions():
    """
    查询所有已订阅数据，并支持过滤条件
    :return: 所有订阅
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL 和 Headers
    url = f"{mp_url}/api/v1/subscribe/"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"请求失败，状态码: {response.status}")
                data = await response.json()
                return data
    except Exception as e:
        print(f"获取已订阅数据失败: {e}")
        return []


# 查询所有订阅
async def fetch_subscriptions(season=None, tmdbid=None, sub_type=None, name=None):
    """
    查询所有已订阅数据，并支持过滤条件
    :param season: 过滤条件 - 季度
    :param tmdbid: 过滤条件 - TMDB ID
    :param sub_type: 过滤条件 - 类型（如 电影、剧集）
    :param name: 过滤条件 - 名称
    :return: 满足条件的已订阅数据列表
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL 和 Headers
    url = f"{mp_url}/api/v1/subscribe/"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"请求失败，状态码: {response.status}")
                data = await response.json()

        # 数据过滤
        filtered_data = []
        for item in data:
            if season is not None and item.get("season") != season:
                continue
            if tmdbid is not None and item.get("tmdbid") != tmdbid:
                continue
            if sub_type is not None and item.get("type") != sub_type:
                continue
            if name is not None and name.lower() not in item.get("name", "").lower():
                continue
            filtered_data.append(item)

        return filtered_data
    except Exception as e:
        print(f"获取已订阅数据失败: {e}")
        return []


async def fetch_subscription_info(tmdb_id, title, page=1):
    """
    根据 tmdb_id 和标题获取订阅信息
    :param tmdb_id: tmdb id
    :param title: 媒体标题
    :param page: 页码，默认为 1
    :return: 返回订阅信息
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL（将 token 加入请求参数）
    url = f"{mp_url}/api/v1/subscribe/media/tmdb:{tmdb_id}?title={title}&page={page}"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                # 获取返回的 JSON 数据
                data = await response.json()
                # 格式化并返回订阅信息
                return data
            else:
                return f"{tmdb_id},{title}订阅查询请求失败，状态码: {response.status}"


# 查询可订阅的季
async def fetch_seasons_info(tmdb_id):
    """
    根据 tmdb_id 获取当前影片的季节信息
    :param tmdb_id: tmdb id
    :return: 返回季节信息
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL（将 tmdb_id 用于构造季节查询的请求地址）
    url = f"{mp_url}/api/v1/tmdb/seasons/{tmdb_id}"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                # 获取返回的 JSON 数据，返回季节信息
                return await response.json()
            else:
                return f"查询季节信息失败，状态码: {response.status}"


# 新增订阅
async def add_subscription(media_info, selected_season):
    """
    根据传入的媒体信息添加订阅
    :param media_info: 媒体信息字典，包含媒体的详细信息
    :return: 返回订阅操作的结果
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL
    url = f"{mp_url}/api/v1/subscribe/"
    headers = {
        "Authorization": f"Bearer {mp_token}",
        "Content-Type": "application/json"
    }

    # 构造请求数据，注意处理可能为 None 的字段
    subscription_data = {
        "name": media_info.get("title", None),
        "type": media_info.get("type", None),
        "year": media_info.get("year", None),
        "tmdbid": media_info.get("tmdb_id", None),
        "doubanid": media_info.get("douban_id", None),
        "bangumiid": media_info.get("bangumi_id", None),
        "season": selected_season.get("season_number", None),
        "best_version": 0  # 默认为 0
    }

    # 发送请求
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=subscription_data, headers=headers) as response:
            if response.status == 200:
                # 返回成功的订阅数据
                return await response.json()
            else:
                return {"success": False}


# 电影订阅删除
async def delete_movie_subscription(tmdb_id):
    """
    根据传入的 tmdb_id 删除订阅
    :param tmdb_id: 需要删除的订阅的 tmdb_id
    :return: 返回删除操作的结果
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL（将 tmdb_id 插入到 URL 中）
    url = f"{mp_url}/api/v1/subscribe/media/tmdb:{tmdb_id}"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }

    # 发送请求
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                # 返回成功的删除信息
                return await response.json()
            else:
                return {"success": False}


# 删除电视剧订阅
async def delete_tv_show_subscription(subscription_id):
    """
    根据传入的订阅 ID 删除电视剧订阅
    :param subscription_id: 需要删除的订阅的 ID
    :return: 返回删除操作的结果
    """
    # 获取基础配置
    mp_base = await get_mp_base()
    mp_url = mp_base['baseUrl']  # 获取 base_url
    mp_token = mp_base['token']  # 获取 token

    # 构造请求 URL（将 subscription_id 插入到 URL 中）
    url = f"{mp_url}/api/v1/subscribe/{subscription_id}"
    headers = {
        "Authorization": f"Bearer {mp_token}"
    }

    # 发送 DELETE 请求
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                # 返回成功的删除信息
                return await response.json()
            else:
                # 返回失败的信息
                return {"success": False}


# 订阅请求开始
async def sub_start_search(bot, event, logger, user_id):
    message_text = str(event.message_chain)
    if not message_text.startswith("mp订阅新增"):
        return

    await check_token()
    query = message_text.replace("mp订阅新增", "").strip()
    if not query:
        await bot.send(event, "请提供有效的搜索内容！例如【mp订阅新增 乡村爱情】")
        return

    # 异步调用 fetch_emby_media_info 并使用 await 获取结果
    # try:
    #
    # except:
    #     print("请求出错sub_start_search-》medias = await sub_search(query)请求超时")
    #     reset_search_state(user_id)
    #     return
    #
    # if not medias:
    #     await bot.send(event, "抱歉，咩有搜到资源哦！！！")
    #     reset_search_state(user_id)
    #     return

    # 异步调用格式化函数并确保正确返回

    # 过滤出已订阅的数据
    async def handle_medias(medias1, all_subscriptions1):
        for item0 in all_subscriptions1:
            for item1 in medias1:
                if item0['tmdbid'] != item1['tmdb_id']:
                    continue
                else:
                    if item0['name'] != item1['title']:
                        continue
                item1['is_sub'] = "已订阅"
        return medias1

    count = 1
    try:
        await bot.send(event, "玩命搜索中......", True)
        # 数据准备
        medias = []
        forMeslist = []
        all_subscriptions = await fetch_all_subscriptions()
        while 1:
            page_medias = await sub_search(query, count)
            medias.extend(page_medias)
            count += 1
            if not page_medias:
                break
            # 所有已订阅
            page_medias = await handle_medias(page_medias, all_subscriptions)

            for index, item in enumerate(page_medias):
                index = index + 1
                index_info = f"📌 序号：{index+(count-2)*8}\n"
                format_media = await format_single_tv_show_data(item)
                format_media.insert(0, {"type": "Plain", "text": index_info + "\n"})
                message = ForwardMessageNode(sender_id=bot.qq, sender_name=f"咩序号：{index+(count-2)*8}",
                                             message_chain=MessageChain(format_media))
                forMeslist.append(message)
            await bot.send(event, Forward(node_list=forMeslist))
            forMeslist = []
        #  保存medias
        if not medias:
            await bot.send(event, "没有找到数据哦，请不要加上第几季或第几部重新搜索试试。", True)
            return
        await bot.send(event, "搜索完毕啦，请在60s内请选择对应的序号进行下一步。", True)
        user_search_states[user_id]['current_medias'] = medias
        user_search_states[user_id]['is_waiting_for_reply'] = True
        user_search_states[user_id]['reply_step'] = 1
        user_search_states[user_id]['timeout_task'] = asyncio.create_task(send_timeout_message(bot, event, user_id))

    except:
        await bot.send(event, "请求出错啦", True)
        print("请求出错sub_start_search出错啦")
        reset_search_state(user_id)
        return


# 订阅取消请求开始
async def sub_cancel_start_search(bot, event, logger, user_id):
    message_text = str(event.message_chain)
    if not message_text.startswith("mp订阅删除"):
        return

    await check_token()
    query = message_text.replace("mp订阅删除", "").strip()
    if not query:
        await bot.send(event, "请提供有效的内容！例如【mp订阅删除 乡村爱情】")
        return

    # 异步调用格式化函数并确保正确返回
    try:
        await bot.send(event, "玩命搜索中......", True)
        medias = await fetch_subscriptions(None, None, None, query)
        user_search_states[user_id]['current_medias'] = medias
        forMeslist = []

        # tips_message = [{"type": "Plain", "text": "下面是搜索结果，请在60s内请选择对应的序号进行下一步。支持多选，以逗号分隔，例如1，2则订阅第一第二季。"}]
        # note_text = ForwardMessageNode(sender_id=bot.qq, sender_name=f"tips：",
        #                                message_chain=MessageChain(tips_message))
        # forMeslist.append(note_text)
        for index, item in enumerate(medias):
            index = index + 1
            index_info = f"📌 序号：{index}\n"
            format_media = await format_single_subscribed_movie(item)
            format_media.insert(0, {"type": "Plain", "text": index_info + "\n"})
            message = ForwardMessageNode(sender_id=bot.qq, sender_name=f"咩序号：{index}",
                                         message_chain=MessageChain(format_media))
            forMeslist.append(message)
            if index % 7 == 0:
                await bot.send(event, Forward(node_list=forMeslist))
                forMeslist = []
        if len(medias) % 7 != 0:
            await bot.send(event, Forward(node_list=forMeslist))
        if not medias:
            await bot.send(event, "没有找到数据哦，请不要加上第几季或第几部重新搜索试试。", True)
            return
        await bot.send(event, "搜索完毕啦，请在60s内请选择对应的序号进行下一步。支持多选，以逗号分隔，例如1，2则取消订阅第一项和第二项。", True)
        user_search_states[user_id]['timeout_task'] = asyncio.create_task(send_timeout_message(bot, event, user_id))
        user_search_states[user_id]['cancel_sub'] = True
        user_search_states[user_id]['is_waiting_for_reply'] = True
        user_search_states[user_id]['reply_step'] = 1
    except:
        print("请求出错sub_cancel_start_search-》forMeslist = []")
        reset_search_state(user_id)
        return


# 订阅回复处理
async def sub_handle_reply(bot, event, logger, user_id):
    """处理用户回复"""
    is_cancel_sub = user_search_states[user_id]['cancel_sub']
    if not user_search_states[user_id]['is_waiting_for_reply'] or is_cancel_sub:
        return

    await check_token()
    reply_text = str(event.message_chain)
    try:
        user_search_states[user_id]['timeout_task'].cancel()  # 取消当前超时任务
    except:
        reset_search_state(user_id)
        return

    if user_search_states[user_id]['reply_step'] == 1:
        await handle_sub_media_selection(bot, event, reply_text, user_id)
    elif user_search_states[user_id]['reply_step'] == 2:
        await handle_sub_season_selection(bot, event, reply_text, user_id)


# 订阅取消回复处理
async def sub_cancel_handle_reply(bot, event, logger, user_id):
    """处理用户取消回复"""
    is_cancel_sub = user_search_states[user_id]['cancel_sub']
    if not user_search_states[user_id]['is_waiting_for_reply'] or (not is_cancel_sub):
        return

    await check_token()
    reply_text = str(event.message_chain)
    user_search_states[user_id]['timeout_task'].cancel()  # 取消当前超时任务
    selects = re.split(r"[，,]", reply_text)
    current_medias = user_search_states[user_id]['current_medias']
    selected_medias = []
    for select in selects:
        try:
            index = int(select.strip()) - 1  # 用户通常从 1 开始计数，需减 1 转为列表索引
            if 0 <= index < len(current_medias):  # 确保索引在范围内
                selected_medias.append(current_medias[index])
        except ValueError:
            # 忽略无法转换为整数的输入
            continue
    result_text = f"下面是取消订阅结果：\n"
    try:
        for item in selected_medias:
            temp = ""
            if item['type'] == "电影":
                res = await delete_movie_subscription(item['tmdbid'])
                del_status = res['success']
                if del_status:
                    temp = f"{item['name']}取消订阅成功\n"
                else:
                    temp = f"{item['name']}取消订阅失败\n"
                result_text += temp
            if item['type'] == "电视剧":
                res = await delete_tv_show_subscription(item['id'])
                del_status = res['success']
                if del_status:
                    temp = f"{item['name']}第{item['season']}季取消订阅成功\n"
                else:
                    temp = f"{item['name']}第{item['season']}季取消订阅失败\n"
                result_text += temp
    except:
        print("请求出错sub_cancel_handle_reply-》for = []")
        reset_search_state(user_id)
        return

    await bot.send(event, f"{result_text}", True)
    reset_search_state(user_id)


# 格式化订阅季度信息
# 格式化单条季度数据
async def format_sub_season_data(season_data: dict, user_id: int) -> list:
    """
    格式化单条季度数据为 MessageChain 格式
    :param user_id:
    :param season_data: 单条季度数据
    :param index: 当前数据的序号（从1开始）
    :return: 格式化后的 MessageChain
    """
    message_chain = []

    # 提取数据
    name = season_data.get("name", "未知季")
    air_date = season_data.get("air_date", "未知日期")
    episode_count = season_data.get("episode_count", "未知")
    vote_average = season_data.get("vote_average", 0.0)
    overview = season_data.get("overview", "暂无简介")
    poster_link = season_data.get("poster_path", "")
    is_sub = season_data.get("is_sub", "未订阅")

    # 格式化文本内容
    res = (
        f"📅 订阅状态: {is_sub}\n"  # 加入订阅状态
        f"📺 季度: {name}\n"
        f"📆 首播时间: {air_date}\n"
        f"🎬 集数: {episode_count} 集\n"
        f"⭐ 评分: {vote_average}/10\n"
        f"📖 简介: {overview}\n"
        # f"🌐 图片地址: https://image.tmdb.org/t/p/original{poster_link}\n"
    )

    # 添加文本消息
    message_chain.append({"type": "Plain", "text": res})

    # 添加图片消息（如果有海报路径）
    # if poster_link:
    #     full_poster_url = f"https://image.tmdb.org/t/p/original{poster_link}"
    #     img = await image_url_to_base64(full_poster_url)
    #     message_chain.append(Image(base64=img))
    if poster_link:
        full_poster_url = f"https://image.tmdb.org/t/p/original{poster_link}"
        message_chain.append({"type": "Image", "url": full_poster_url})

    # 添加分隔符
    # message_chain.append({"type": "Plain", "text": "\n-------------------------\n"})

    return message_chain


# 处理订阅搜索的回复结果
async def handle_sub_media_selection(bot, event, reply_text, user_id):
    """处理用户选择的媒体"""
    try:
        index = int(reply_text) - 1
        selected_media = user_search_states[user_id]['current_medias'][index]
    except (ValueError, IndexError):
        await bot.send(event, "您的输入有误，查询结束啦！！！")
        reset_search_state(user_id)
        return

    if selected_media['type'] == "电视剧":

        await bot.send(event, "玩命搜索中......", True)
        # 电视剧逻辑
        seasons = await fetch_seasons_info(selected_media['tmdb_id'])
        tmdb_id = selected_media['tmdb_id']

        forMeslist = []
        # 所有已订阅
        all_subscriptions = await fetch_all_subscriptions()

        # 过滤出已订阅的数据
        for item in all_subscriptions:
            for item1 in seasons:
                if item['tmdbid'] != tmdb_id:
                    continue
                else:
                    if item1['season_number'] != item['season']:
                        continue
                item1['is_sub'] = "已订阅"

        # tips_message = [{"type": "Plain", "text": "下面是搜索结果，请在60s内选择对应的序号进行下一步。支持多选，以逗号分隔，例如1，2则订阅第一第二季。"}]
        # note_text = ForwardMessageNode(sender_id=bot.qq, sender_name=f"tips：",
        #                                message_chain=MessageChain(tips_message))
        # forMeslist.append(note_text)
        for index, item in enumerate(seasons):
            index = index + 1
            index_info = f"📌 序号：{index}\n"
            format_media = await format_sub_season_data(item, user_id)
            format_media.insert(0, {"type": "Plain", "text": index_info + "\n"})
            message = ForwardMessageNode(sender_id=bot.qq, sender_name=f"咩序号：{index}",
                                         message_chain=MessageChain(format_media))
            forMeslist.append(message)
            if index % 8 == 0:
                await bot.send(event, Forward(node_list=forMeslist))
                forMeslist = []
        if len(seasons) % 8 != 0:
            await bot.send(event, Forward(node_list=forMeslist))
        await bot.send(event, "搜索完毕啦，请在60s内请选择对应的序号进行下一步。支持多选，以逗号分隔，例如1，2则订阅第一第二季。", True)
        user_search_states[user_id]['current_medias'] = selected_media
        user_search_states[user_id]['current_seasons'] = seasons
        user_search_states[user_id]['reply_step'] = 2
        user_search_states[user_id]['timeout_task'] = asyncio.create_task(send_timeout_message(bot, event, user_id))

    if selected_media['type'] == "电影":
        # 电影逻辑
        res = await add_subscription(selected_media, {})
        add_status = res.get('success', False)
        reset_search_state(user_id)
        if add_status:
            temp = f"{selected_media['title']}订阅成功\n"
        else:
            temp = f"{selected_media['title']}订阅失败\n"
        await bot.send(event, temp, True)
        reset_search_state(user_id)


# 处理订阅季度回复的结果
async def handle_sub_season_selection(bot, event, reply_text, user_id):
    """处理用户选择的电视剧季"""
    try:
        selects = re.split(r"[，,]", reply_text)
        result_text = f"下面是订阅结果：\n"
        current_media = user_search_states[user_id]['current_medias']
        try:
            for i in selects:
                temp = ""
                i = int(i)
                i = i - 1
                selected_season = user_search_states[user_id]['current_seasons'][i]
                res = await add_subscription(current_media, selected_season)
                add_status = res.get('success', False)
                if add_status:
                    temp = f"第{i + 1}季订阅成功\n"
                else:
                    temp = f"第{i + 1}季订阅失败\n"
                result_text += temp
        except:
            print("请求出错handle_sub_season_selection-》for = []")
            reset_search_state(user_id)
            return

        await bot.send(event, f"{result_text}", True)
        reset_search_state(user_id)

    except (ValueError, IndexError):
        await bot.send(event, "您的输入有误，查询结束啦！！！")
        reset_search_state(user_id)
        return


def main(bot, logger):
    logger.info("启用mp功能")

    @bot.on(GroupMessage)
    async def manager(event: GroupMessage):
        message_content = str(event.message_chain)
        user_id = event.sender.id  # 获取用户ID

        # 帮助功能
        if message_content.startswith("mp帮助"):
            help_message = (
                "🎉 **mp 帮助功能** 🎉\n\n"
                "嘿嘿~欢迎使用 **mp** 功能！下面是你可以用的命令哦～快来看看吧~ 😎👇\n\n"
                "1️⃣ **mp订阅新增 [关键词]** - 🎬 mp订阅影片或剧集！例如：**mp订阅新增 乡村爱情**\n"
                "2️⃣ **mp订阅删除 [关键词]** - 🎬 mp取消订阅影片或剧集！例如：**mp订阅删除 乡村爱情**\n"
                "3️⃣ **mp订阅查询 [关键词]** - 🎬 mp已订阅查询，不传参查询全部！例如：**mp订阅查询 乡村爱情**\n"
                # "4️⃣ **emby用户搜索@(直接艾特群友，账号为qq号)或#(自定义账号名)** - 🔍 搜索用户！格式是：@用户名\n\n"
                "💡 **小贴士**：\n"
                "- 每个命令后面跟上需要的参数（如：影片名）。\n"
                "- 如果遇到问题，随时可以输入 **mp帮助** 来获取更多帮助哦~ 😊\n\n"
                "💖 现在就试试看吧，快快输入命令来玩吧~ 😜"
            )

            await bot.send(event, help_message, True)
            return

        # mp订阅功能
        if user_search_states[user_id]['reply_step'] == 0:
            start_time = time.time()
            await sub_start_search(bot, event, logger, user_id)
            end_time = time.time()
            print(f"运行时间: {end_time - start_time} 秒")
        else:
            await sub_handle_reply(bot, event, logger, user_id)

        # mp取消订阅
        if user_search_states[user_id]['reply_step'] == 0:
            await sub_cancel_start_search(bot, event, logger, user_id)
        else:
            await sub_cancel_handle_reply(bot, event, logger, user_id)

        # mp订阅查询
        if message_content.startswith("mp订阅查询"):
            await check_token()
            message_text = str(event.message_chain)
            query = message_text.replace("mp订阅查询", "").strip()
            await bot.send(event, "玩命搜索中......", True)
            res = await fetch_subscriptions(None, None, None, query)
            if len(res) == 0:
                await bot.send(event, "抱歉没有找到相关订阅数据。", True)
                return
            forMeslist = []
            tips_message = [{"type": "Plain", "text": "下面是所有订阅哦！！！"}]
            note_text = ForwardMessageNode(sender_id=bot.qq, sender_name=f"tips：",
                                           message_chain=MessageChain(tips_message))
            forMeslist.append(note_text)
            for index, item in enumerate(res):
                index = index + 1
                index_info = f"📌 序号：{index}\n"
                format_media = await format_single_subscribed_movie(item)
                format_media.insert(0, {"type": "Plain", "text": index_info + "\n"})
                message = ForwardMessageNode(sender_id=bot.qq, sender_name=f"咩序号：{index}",
                                             message_chain=MessageChain(format_media))
                forMeslist.append(message)
                if index % 8 == 0:
                    await bot.send(event, Forward(node_list=forMeslist))
                    forMeslist = []
                    # time.sleep(1)

            if len(res) % 8 != 0:
                await bot.send(event, Forward(node_list=forMeslist))

        # 示例调用
        # search_name = "凡人修仙传"
        # medias = await sub_search(search_name)
        #
        # forMeslist = []
        #
        # if len(medias) == 0:
        #     await bot.send(event, "抱歉，咩有搜到资源哦！！！")
        #
        # for index, item in enumerate(medias):
        #     index = index + 1
        #     index_info = f"📌 序号：{index}\n"
        #     format_media = await format_single_tv_show_data(item)
        #     format_media.insert(0, {"type": "Plain", "text": index_info + "\n"})
        #     message = ForwardMessageNode(sender_id=bot.qq, sender_name=f"咩序号：{index}",
        #                                  message_chain=MessageChain(format_media))
        #     forMeslist.append(message)
        #
        # await bot.send(event, Forward(node_list=forMeslist))

        # client = MiraiHttpClient(base_url, verify_key, qq_number)
        #
        # # 发送群消\n息
        # # await bot.send(event, message_chain, True)
        # await client.send_group_message(group_id, message_chain)
        return


async def fetch_token():
    url = "https://mp.4348662.asia:16384/api/v1/login/access-token"
    payload = {
        "username": "zhugeyue",
        "password": "zzs123qq"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=payload, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    token = data.get("access_token")
                    if token:
                        # 将 token 写入到文件 token.txt 中
                        with open("plugins/mp/token.txt", "w") as file:
                            file.write(token)
                        print("Token fetched and saved successfully.")
                        return token
                    else:
                        print("Token not found in the response.")
                else:
                    print(f"Request failed with status code: {response.status}")
        except Exception as e:
            print(f"An error occurred: {e}")


async def check_token():
    res = await sub_search_copy("")
    if res:
        return
    if not res:
        token = await fetch_token()
        return token


def read_token_from_file() -> object:
    try:
        with open("plugins/mp/token.txt", "r") as file:
            token = str(file.read().strip())
            print(f"Token read from file: {token}")
            return token
    except FileNotFoundError:
        print("Token file not found. Please fetch the token first.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the token: {e}")
        return None


