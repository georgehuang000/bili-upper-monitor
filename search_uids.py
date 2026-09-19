import urllib.request
import json
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
    'Accept': 'application/json',
}

KEYWORDS = ['擒龙先生', '七加一不怕', '来去由心', '机构一手调研', '福总说实话']

for kw in KEYWORDS:
    print(f"\n=== 搜索: {kw} ===")
    url = f'https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword={urllib.parse.quote(kw)}&page=1'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        results = data.get('data', {}).get('result', [])
        for r in results[:5]:
            print(f"  {r.get('uname','')} - UID:{r.get('mid','')} - 粉丝:{r.get('fans',0)} - 视频:{r.get('videos',0)}")
    except Exception as e:
        print(f"  错误: {e}")
    time.sleep(1)
