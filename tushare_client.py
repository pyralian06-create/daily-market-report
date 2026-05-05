"""Tushare Pro API 单例工厂，从 settings 读取 TUSHARE_TOKEN / TUSHARE_URL。"""
import tushare as ts

import settings

_pro = None


def get_pro() -> ts.pro_api:
    global _pro
    if _pro is not None:
        return _pro

    token = settings.TUSHARE_TOKEN
    api_url = settings.TUSHARE_URL

    if not token:
        raise ValueError(
            "未配置 Tushare token，请在 .env 文件中设置 TUSHARE_TOKEN"
        )

    _pro = ts.pro_api(token)
    if api_url:
        _pro._DataApi__http_url = api_url

    return _pro
