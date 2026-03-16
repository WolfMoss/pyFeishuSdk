"""
飞书 SDK 自定义异常模块
"""


class FeishuError(Exception):
    """飞书 API 基础异常"""

    def __init__(self, code: int = 0, msg: str = "", detail: str = ""):
        self.code = code
        self.msg = msg
        self.detail = detail
        super().__init__(f"[{code}] {msg}" + (f" - {detail}" if detail else ""))


class FeishuAuthError(FeishuError):
    """认证相关异常（token 获取失败、过期等）"""
    pass


class FeishuPermissionError(FeishuError):
    """权限不足异常"""
    pass


class FeishuNotFoundError(FeishuError):
    """资源不存在异常"""
    pass


class FeishuRateLimitError(FeishuError):
    """请求频率超限异常"""
    pass


class FeishuNetworkError(FeishuError):
    """网络请求异常"""
    pass
