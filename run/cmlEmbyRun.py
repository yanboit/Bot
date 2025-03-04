import asyncio
import yaml
from mirai import GroupMessage, Image
from run.authentication import authentication
from collections import defaultdict

from plugins.cmlEmby import (
    fetch_emby_media_info,  # 原 getEmbyMediasInfo
    format_media_info_list,  # 原 formatterMediasInfo
    fetch_media_info_by_id,  # 原 getMediaInfoById
    format_detailed_media_info,  # 原 formatterMediaInfo
    fetch_emby_seasons,  # 原 getEmbySeasons
    format_series_info_list,  # 原 formatterSeriesInfo
    format_series_details,  # 原 formatterSerieDetail
    fetch_image_url,  # 原 getImgUrl
    emby_user_add,
    emby_user_del,
    fetch_emby_user_by_partial_name, image_url_to_base64,
)


# 用户状态管理字典
user_search_states = defaultdict(lambda: {
    'waiting_message_id': None,
    'timeout_task': None,
    'is_waiting_for_reply': False,
    'current_medias': [],
    'reply_step': 0,
    'wait_time': 60,
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
    })


async def start_search(bot, event, logger, user_id):
    """处理初始搜索请求"""
    message_text = str(event.message_chain)
    if not message_text.startswith("emby搜索"):
        return

    query = message_text.replace("emby搜索", "").strip()
    if not query:
        await bot.send(event, "请提供有效的搜索内容！例如【emby搜索 乡村爱情】")
        return

    # 异步调用 fetch_emby_media_info 并使用 await 获取结果
    search_results = await fetch_emby_media_info(query)
    if not search_results:
        await bot.send(event, "抱歉！！！未找到对应的影片。")
        reset_search_state(user_id)
        return

    user_search_states[user_id]['current_medias'] = search_results
    user_search_states[user_id]['is_waiting_for_reply'] = True
    user_search_states[user_id]['reply_step'] = 1

    # 异步调用格式化函数并确保正确返回
    formatted_results = await format_media_info_list(search_results)
    await bot.send(event, formatted_results)
    user_search_states[user_id]['timeout_task'] = asyncio.create_task(send_timeout_message(bot, event, user_id))


async def handle_reply(bot, event, logger, user_id):
    """处理用户回复"""
    if not user_search_states[user_id]['is_waiting_for_reply']:
        return

    reply_text = str(event.message_chain)
    user_search_states[user_id]['timeout_task'].cancel()  # 取消当前超时任务

    if user_search_states[user_id]['reply_step'] == 1:
        await handle_media_selection(bot, event, reply_text, user_id)
    elif user_search_states[user_id]['reply_step'] == 2:
        await handle_season_selection(bot, event, reply_text, user_id)


async def handle_media_selection(bot, event, reply_text, user_id):
    """处理用户选择的媒体"""
    try:
        index = int(reply_text) - 1
        selected_media = user_search_states[user_id]['current_medias'][index]
    except (ValueError, IndexError):
        await bot.send(event, "您的输入有误，查询结束啦！！！")
        reset_search_state(user_id)
        return

    if selected_media['IsFolder']:
        # 电视剧逻辑
        seasons = await fetch_emby_seasons(await fetch_media_info_by_id(selected_media['Id']))
        user_search_states[user_id]['current_medias'] = seasons
        user_search_states[user_id]['reply_step'] = 2

        formatted_seasons = await format_series_info_list(seasons)
        await bot.send(event, formatted_seasons, True)
        user_search_states[user_id]['timeout_task'] = asyncio.create_task(send_timeout_message(bot, event, user_id))
    else:
        # 电影逻辑
        media_info = await fetch_media_info_by_id(selected_media['Id'])
        movie_details = await format_detailed_media_info(media_info)
        image_url = await fetch_image_url(media_info['Id'], media_info['ImageTags']['Primary'])
        img = await image_url_to_base64(image_url)
        await bot.send(event, [f"啦啦啦下面是查询的电影详情哦\n\n{movie_details}", Image(base64=img)], True)
        reset_search_state(user_id)


async def handle_season_selection(bot, event, reply_text, user_id):
    """处理用户选择的电视剧季"""
    try:
        index = int(reply_text) - 1
        selected_season = user_search_states[user_id]['current_medias'][index]
    except (ValueError, IndexError):
        await bot.send(event, "您的输入有误，查询结束啦！！！")
        reset_search_state(user_id)
        return

    season_details = await format_series_details(await fetch_media_info_by_id(selected_season['Id']))
    image_url = await fetch_image_url(selected_season['SeriesId'], selected_season['SeriesPrimaryImageTag'])
    img = await image_url_to_base64(image_url)
    await bot.send(event, [f"啦啦啦下面是查询的电视剧详情哦\n\n{season_details}", Image(base64=img)], True)
    reset_search_state(user_id)


def extract_username(message_chain: str) -> str:
    """提取用户输入的用户名，支持@和#前缀"""
    if "@" in message_chain:
        return message_chain.split("@")[1].strip()
    elif "#" in message_chain:
        return message_chain.split("#")[1].strip()
    return None


async def manage_emby_users(bot, event):
    """管理 Emby 用户功能"""
    message_content = str(event.message_chain)

    if "emby用户新增" in message_content:
        username = extract_username(message_content)
        if not username:
            await bot.send(event, "输入有误，请按格式【emby用户新增@】或【emby用户新增#】输入！！！", True)
            return
        res = await emby_user_add(username)
        if res:
            await bot.send(event, f"恭喜你新增成功啦!!!\n新增的用户名：{username}\n默认密码为空，第一次登录记得修改密码哟。", True)
        else:
            await bot.send(event, f"新增失败，用户已存在或其他原因！！！", True)

    elif "emby用户删除" in message_content:
        del_username = extract_username(message_content)
        if not del_username:
            await bot.send(event, "输入有误，请按格式【emby用户删除@】或【emby用户删除#】输入！！！", True)
            return
        res = await emby_user_del(del_username)
        if res:
            await bot.send(event, f"删除成功啦!!!\n删除的用户名：{del_username}", True)
        else:
            await bot.send(event, f"删除失败，用户不存在或其他原因！！！", True)

    elif "emby用户搜索" in message_content:
        search_username = extract_username(message_content)
        if not search_username:
            await bot.send(event, "输入有误，请按格式【emby用户搜索@】或【emby用户搜索#】输入！！！", True)
            return
        res = await fetch_emby_user_by_partial_name(search_username)
        await bot.send(event, res, True)


def main(bot, logger):
    logger.info("启用emby功能")

    @bot.on(GroupMessage)
    async def manager(event: GroupMessage):
        message_content = str(event.message_chain)
        user_id = event.sender.id  # 获取用户ID

        # 帮助功能
        if message_content.startswith("emby帮助"):
            help_message = (
                "🎉 **Emby 帮助功能** 🎉\n\n"
                "嘿嘿~欢迎使用 **Emby** 功能！下面是你可以用的命令哦～快来看看吧~ 😎👇\n\n"
                "1️⃣ **emby搜索 [关键词]** - 🎬 搜索影片或剧集！例如：**emby搜索 乡村爱情**\n"
                "2️⃣ **emby用户新增@(直接艾特群友，账号为qq号)或#(自定义账号名)** - 👤 新增用户！格式是：@用户名\n"
                "3️⃣ **emby用户删除@(直接艾特群友，账号为qq号)或#(自定义账号名)** - 🗑️ 删除用户！格式是：@用户名\n"
                "4️⃣ **emby用户搜索@(直接艾特群友，账号为qq号)或#(自定义账号名)** - 🔍 搜索用户！格式是：@用户名\n\n"
                "💡 **小贴士**：\n"
                "- 每个命令后面跟上需要的参数（如：用户名或影片名）。\n"
                "- 如果遇到问题，随时可以输入 **emby帮助** 来获取更多帮助哦~ 😊\n\n"
                "💖 现在就试试看吧，快快输入命令来玩吧~ 😜"
            )

            await bot.send(event, help_message, True)
            return

        # 搜索功能
        if user_search_states[user_id]['reply_step'] == 0:
            try:
                await start_search(bot, event, logger, user_id)
            except:
                print("请求出错main-》await start_search(bot, event, logger, user_id)")
                reset_search_state(user_id)
                return
        else:
            try:
                await handle_reply(bot, event, logger, user_id)
            except:
                print("请求出错main-》await handle_reply(bot, event, logger, user_id)")
                reset_search_state(user_id)
                return

        # 管理用户
        if message_content.startswith("emby用户"):
            # 读取用户权限
            send_id = str(event.sender.id)

            # 判断用户权限
            if authentication(send_id):
                # 用户新增
                if str(event.message_chain).startswith("emby用户新增"):
                    username = None
                    if str(event.message_chain).startswith("emby用户新增@"):
                        username = str(event.message_chain).split("@")[1]
                    if str(event.message_chain).startswith("emby用户新增#"):
                        username = str(event.message_chain).split("#")[1]
                    if not username:
                        await bot.send(event, f"输入有误，请按格式【emby用户新增@】或【emby用户新增#】输入！！！", True)
                        return
                    res = await emby_user_add(username)
                    if res:
                        await bot.send(event, f"恭喜你新增成功啦!!!\n新增的用户名：{username}\n默认密码为空，第一次登录记得修改密码哟。", True)
                    else:
                        await bot.send(event, f"新增失败，用户已存在或其他原因！！！", True)

                # 用户删除
                if str(event.message_chain).startswith("emby用户删除"):
                    del_username = None
                    if str(event.message_chain).startswith("emby用户删除@"):
                        del_username = str(event.message_chain).split("@")[1]
                    if str(event.message_chain).startswith("emby用户删除#"):
                        del_username = str(event.message_chain).split("#")[1]
                    if not del_username:
                        await bot.send(event, f"输入有误，请按格式【emby用户删除@】或【emby用户删除#】输入！！！", True)
                        return
                    res = await emby_user_del(del_username)
                    if res:
                        await bot.send(event, f"删除成功啦!!!\n删除的用户名：{del_username}", True)
                    else:
                        await bot.send(event, f"删除失败，用户不存在或其他原因！！！", True)

                # 用户搜索
                if str(event.message_chain).startswith("emby用户搜索"):
                    search_username = None
                    if str(event.message_chain).startswith("emby用户搜索@"):
                        search_username = str(event.message_chain).split("@")[1]
                    if str(event.message_chain).startswith("emby用户搜索#"):
                        search_username = str(event.message_chain).split("#")[1]
                    if str(event.message_chain) == "emby用户搜索":
                        search_username = ''
                    if not search_username and search_username != '':
                        await bot.send(event, f"输入有误，请按格式【emby用户删除@】或【emby用户删除#】输入！！！", True)
                        return
                    res = await fetch_emby_user_by_partial_name(search_username)
                    await bot.send(event, res, True)
            else:
                await bot.send(event, "不好意思你的权限不够哟，请叫管理员使用命令【授权#qq号】授权", True)
                return
