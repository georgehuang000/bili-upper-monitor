"""
B站 WBI 签名算法
B站对部分API（如用户视频列表）要求WBI签名验证
"""
import hashlib
import time
from urllib.parse import urlencode, quote

# WBI 混淆表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 36, 25, 1, 4, 40, 44, 51, 6, 16, 21, 20, 30, 34, 22, 11,
    17, 52, 26, 0, 24, 57, 7, 48, 54, 55, 56, 61, 60, 59, 64, 62,
]


def get_mixin_key(orig: str) -> str:
    """对 img_key + sub_key 进行混淆"""
    mixed = []
    for idx in MIXIN_KEY_ENC_TAB:
        if idx < len(orig):
            mixed.append(orig[idx])
    return "".join(mixed)[:32]


def enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    """
    对请求参数添加 WBI 签名
    返回包含 wts 和 w_rid 的新参数字典
    """
    mixin_key = get_mixin_key(img_key + sub_key)
    wts = int(time.time())
    params["wts"] = wts
    # 参数按键名排序后拼接
    params_sorted = sorted(params.items())
    query = urlencode(params_sorted, quote_via=quote)
    # 计算 MD5
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = wbi_sign
    return params


class WBISigner:
    """WBI 签名器：缓存 img_key 和 sub_key"""

    def __init__(self):
        self._img_key = None
        self._sub_key = None
        self._last_update = 0
        self._cache_ttl = 3600  # 缓存1小时

    @property
    def sub_key(self):
        return self._sub_key

    @sub_key.setter
    def sub_key(self, value):
        self._sub_key = value

    async def update_keys(self, httpx_client):
        """从B站导航接口获取最新的 img_key 和 sub_key"""
        now = time.time()
        if self._img_key and now - self._last_update < self._cache_ttl:
            return

        try:
            resp = await httpx_client.get(
                "https://api.bilibili.com/x/web-interface/nav"
            )
            data = resp.json()
            if data.get("code") == 0:
                wbi_img = data["data"]["wbi_img"]
                self._img_key = wbi_img["img_url"].rsplit("/", 1)[-1].split(".")[0]
                self._sub_key = wbi_img["sub_url"].rsplit("/", 1)[-1].split(".")[0]
                self._last_update = now
        except Exception:
            pass  # 签名失败时降级为无签名请求

    def sign(self, params: dict) -> dict:
        """对参数进行 WBI 签名"""
        if not self._img_key or not self._sub_key:
            return params  # 无密钥时不签名
        return enc_wbi(params, self._img_key, self._sub_key)


# 全局签名器实例
wbi_signer = WBISigner()
