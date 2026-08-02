"""调试脚本 - 检查视频数据字段"""
from src.login import BilibiliLogin
from src.bilibili import BilibiliClient
import yaml

# 加载配置
with open('config/settings.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 加载Cookie
login = BilibiliLogin()
cookies = login.load_cookies()

# 初始化客户端
client = BilibiliClient(cookies)

# 获取视频列表
ups = client.get_followed_ups(max_count=1)
if ups:
    videos = client.get_up_videos(ups[0]['mid'], page=1, page_size=1)
    if videos:
        print('视频数据字段:')
        for key, value in videos[0].items():
            print(f'  {key}: {value} (type: {type(value).__name__})')