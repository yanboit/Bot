import aiohttp
import json
import os
from urllib.parse import urlencode
import requests

class MiraiHttpClient:
    def __init__(self, base_url, verify_key, qq, session_file="session.json"):
        self.base_url = base_url
        self.verify_key = verify_key
        self.qq = qq  # 初始化时直接传入 QQ 号
        self.session_file = session_file
        self.session_key = self.load_session()  # 加载已有的 sessionKey

    def load_session(self):
        """加载本地存储的 session key"""
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r') as f:
                data = json.load(f)
                print(f"加载的 sessionKey: {data.get('sessionKey')}")
                return data.get("sessionKey")
        else:
            print("sessionFile 不存在，未加载到 sessionKey。")
        return None

    def save_session(self):
        """保存 session key 到本地文件"""
        with open(self.session_file, 'w') as f:
            json.dump({"sessionKey": self.session_key}, f)
        print(f"保存 sessionKey: {self.session_key}")

    async def authenticate(self) -> bool:
        """认证并获取会话"""
        url = f"{self.base_url}/verify"
        data = {"verifyKey": self.verify_key}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        self.session_key = result.get("session")
                        self.save_session()  # 保存 session
                        print(f"认证成功。Session Key: {self.session_key}")
                        return True
                    else:
                        print(f"认证失败: {result.get('msg')}")
                        return False
                else:
                    print(f"认证请求失败，状态码: {response.status}")
                    return False

    async def bind(self):
        """绑定 session 和 QQ 号"""
        if not self.session_key:
            print("无有效的 Session Key，无法绑定 QQ。")
            return False

        url = f"{self.base_url}/bind"
        data = {
            "sessionKey": self.session_key,
            "qq": self.qq
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        print(f"成功将 session 绑定到 QQ: {self.qq}")
                        return True
                    else:
                        print(f"绑定失败: {result.get('msg')}")
                else:
                    print(f"绑定请求失败，状态码: {response.status}")
        return False

    async def check_session(self):
        """检查 session 是否有效并处理相应逻辑"""
        if not self.session_key:
            print("SessionKey 不存在，请先认证。")
            await self.authenticate()
            return False

        url = f"{self.base_url}/sessionInfo"
        params = {"sessionKey": self.session_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    code = result.get("code")
                    if code == 0:
                        print("Session有效")
                        return True
                    elif code == 4:
                        print("Session未绑定，正在绑定 QQ...")
                        await self.bind()
                        return False  # 绑定后还需要重新检查
                    elif code == 3:
                        print("Session失效，重新认证...")
                        for count in range(3):  # 循环最多 3 次
                            print(f"重新认证尝试第 {count + 1} 次...")
                            # 进行认证
                            session_key = await self.authenticate()
                            if session_key:  # 如果认证成功，session_key 会被赋值
                                print("认证成功")
                                # 绑定 QQ
                                await self.bind()
                                return True  # 认证和绑定成功，返回 True

                            # 如果尝试了 3 次都失败，返回 False
                        print("认证失败，重试次数超过限制。")
                        return False
                    else:
                        print(f"未知返回码: {code}, 信息: {result.get('msg')}")
                else:
                    print(f"检查 Session 请求失败，状态码: {response.status}")
        return False

    async def send_group_message(self, group_id, message_chain):
        """发送群消息"""
        if not await self.check_session():
            print("无法发送消息，Session 检查失败。")
            return

        url = f"{self.base_url}/sendGroupMessage"
        data = {
            "sessionKey": self.session_key,
            "group": group_id,
            "messageChain": message_chain
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        print(f"成功发送消息到群 {group_id}")
                    else:
                        print(f"发送消息失败: {result.get('msg')}")
                else:
                    print(f"发送消息请求失败，状态码: {response.status}")
