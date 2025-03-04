import uvicorn
from fastapi import FastAPI, Request

from api.gerMiraiApiKey import MiraiHttpClient
from plugins.cmlEmby import format_emby_in_info, fetch_image_url

app = FastAPI()


@app.post("/movie_in")
async def movie_in_notice(request: Request):
    body = await request.json()
    print(body)
    data = body
    res = format_emby_in_info(data)

    # 初始化客户端
    base_url = "http://132.145.95.110:23457"
    verify_key = "1234567890"
    qq_number = 2511344185

    client = MiraiHttpClient(base_url, verify_key, qq_number)

    # 发送群消\n息
    group_id = 634722217
    img_id = data['Item'].get('Id', 1)
    img_tag = data['Item']['ImageTags'].get('Primary', True)
    if img_tag == 1:
        img_id = data['Item'].get('ParentLogoItemId', True)
        img_tag = data['Item'].get('SeriesPrimaryImageTag', '')

        if img_tag:
            img_id = data['Item'].get('SeriesId', '')

    if img_tag != '':
        img_url = await fetch_image_url(img_id, img_tag)
    else:
        img_url = ''

    message_chain = [{"type": "Plain", "text": res}, {"type": "Image",
                                                      "url": img_url},
                     {"type": "Plain", "text": "\n\n💡 想了解更多影片信息？请联系管理员！"}]
    await client.send_group_message(group_id, message_chain)

    return res


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=54339)
