"""
飞书 SDK 核心客户端模块

负责认证管理（tenant_access_token 自动获取与刷新）和统一的 HTTP 请求封装。
所有子模块（documents, bitable, wiki）都依赖此客户端进行 API 调用。
"""

import time
import logging
import requests
from typing import Optional, Any

from .exceptions import (
    FeishuError,
    FeishuAuthError,
    FeishuPermissionError,
    FeishuNotFoundError,
    FeishuRateLimitError,
    FeishuNetworkError,
)

logger = logging.getLogger("feishu_sdk")

# 飞书 API 基础地址
BASE_URL = "https://open.feishu.cn/open-apis"

# token 相关常量
_TOKEN_ENDPOINT = "/auth/v3/tenant_access_token/internal"
_TOKEN_BUFFER_SECONDS = 300  # 提前 5 分钟刷新 token
# 飞书返回的 token 无效/过期错误码（触发自动刷新并重试）
_TOKEN_EXPIRED_CODES = (4001, 40016, 99991663, 99991664, 99991668)


class FeishuClient:
    """
    飞书 API 客户端

    使用自建应用的 app_id 和 app_secret 进行认证，自动管理 tenant_access_token。

    示例::

        from feishu import FeishuClient
        client = FeishuClient(app_id="cli_xxx", app_secret="xxx")
        # client 会在首次调用 API 时自动获取 token
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        初始化飞书客户端

        Args:
            app_id: 飞书自建应用的 App ID
            app_secret: 飞书自建应用的 App Secret
            base_url: API 基础地址，默认为飞书国内版
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # token 缓存
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0

        # 用户身份相关
        self._user_access_token: Optional[str] = None
        self._user_refresh_token: Optional[str] = None
        self._user_token_expire_time: float = 0
        self._use_user_mode: bool = False
        self._config_path: Optional[str] = None  # 用于回写刷新后的 token

        # HTTP Session（复用连接）
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json; charset=utf-8",
        })

    def switch_to_user_mode(
        self,
        user_token: str,
        refresh_token: str = "",
        expire_at: float = 0,
        config_path: str = "",
    ):
        """
        切换到用户身份模式

        Args:
            user_token: user_access_token
            refresh_token: 用于自动续期的 refresh_token（有效期 30 天）
            expire_at: user_access_token 的过期时间戳
            config_path: config.json 路径，刷新后自动回写
        """
        self._user_access_token = user_token
        self._user_refresh_token = refresh_token
        self._user_token_expire_time = expire_at
        self._use_user_mode = True
        self._config_path = config_path
        logger.info("已切换到用户身份模式")

    def switch_to_tenant_mode(self):
        """切换回应用身份模式"""
        self._use_user_mode = False
        logger.info("已切换到应用身份模式")

    # ──────────────────────────────────────────────
    #  认证管理
    # ──────────────────────────────────────────────

    def _is_token_valid(self) -> bool:
        """检查当前 token 是否还在有效期内"""
        if self._use_user_mode:
            if self._user_access_token is None:
                return False
            # 如果设置了过期时间，检查是否即将过期
            if self._user_token_expire_time > 0:
                return time.time() < self._user_token_expire_time - _TOKEN_BUFFER_SECONDS
            return True  # 未设置过期时间则假设有效
        return (
            self._tenant_access_token is not None
            and time.time() < self._token_expire_time - _TOKEN_BUFFER_SECONDS
        )

    def _refresh_user_token(self) -> None:
        """使用 refresh_token 静默刷新 user_access_token（无需重新扫码）。
        v1 token（u-/ur- 前缀）用 v1 端点刷新，v2 token（JWT）用 v2 端点刷新。
        """
        if not self._user_refresh_token:
            raise FeishuAuthError(
                code=-1,
                msg="user_access_token 已过期且无 refresh_token，请重新运行 feishu_auth.py 扫码授权",
            )

        logger.info("user_access_token 已过期，正在使用 refresh_token 自动续期...")
        is_v1 = (self._user_refresh_token or "").startswith("ur-") or (self._user_access_token or "").startswith("u-")
        if is_v1:
            self._refresh_user_token_v1()
        else:
            self._refresh_user_token_v2()
        logger.info("user_access_token 续期成功")
        self._save_user_token_to_config()

    def _refresh_user_token_v1(self) -> None:
        """v1 刷新：先获取 app_access_token，再调 /authen/v1/refresh_access_token"""
        try:
            app_resp = self._session.post(
                f"{self.base_url}/auth/v3/app_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=self.timeout,
            )
            app_resp.raise_for_status()
            app_token = app_resp.json().get("app_access_token", "")
        except requests.RequestException as e:
            raise FeishuNetworkError(code=-1, msg="获取 app_access_token 失败", detail=str(e))

        try:
            resp = self._session.post(
                f"{self.base_url}/authen/v1/refresh_access_token",
                headers={"Authorization": f"Bearer {app_token}"},
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._user_refresh_token,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise FeishuNetworkError(code=-1, msg="刷新 user token(v1) 网络请求失败", detail=str(e))
        self._handle_refresh_response(resp)

    def _refresh_user_token_v2(self) -> None:
        """v2 刷新：请求体带 client_id/client_secret"""
        try:
            resp = self._session.post(
                f"{self.base_url}/authen/v2/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._user_refresh_token,
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise FeishuNetworkError(code=-1, msg="刷新 user token(v2) 网络请求失败", detail=str(e))
        self._handle_refresh_response(resp)

    def _handle_refresh_response(self, resp: requests.Response) -> None:
        """处理刷新接口的响应（v1/v2 共用）"""
        if not resp.ok:
            try:
                err_body = resp.json()
                msg = err_body.get("msg") or err_body.get("error_description") or err_body.get("error") or resp.text or resp.reason
            except Exception:
                msg = resp.text or resp.reason
            if "invalid" in (msg or "").lower() and "refresh" in (msg or "").lower():
                raise FeishuAuthError(
                    code=resp.status_code,
                    msg="refresh_token 已失效。请重新运行 feishu_auth.py 扫码授权（授权后无需重启 MCP，下次调用会自动用新 token）。",
                )
            raise FeishuAuthError(
                code=resp.status_code,
                msg=f"刷新 user token 失败 ({resp.status_code}): {msg}",
            )

        data = resp.json()
        if data.get("code", 0) != 0:
            raise FeishuAuthError(
                code=data.get("code", -1),
                msg=f"刷新 user token 失败: {data.get('msg', '')}",
            )

        token_data = data.get("data", data)
        self._user_access_token = token_data.get("access_token") or token_data.get("user_access_token")
        new_refresh = token_data.get("refresh_token")
        if new_refresh:
            self._user_refresh_token = new_refresh
        expires_in = token_data.get("expires_in", 7200)
        self._user_token_expire_time = time.time() + expires_in

    def _save_user_token_to_config(self) -> None:
        """将刷新后的 token 回写到 config.json"""
        if not self._config_path:
            return
        try:
            import json as _json
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = _json.load(f)
            config["user_access_token"] = self._user_access_token
            if self._user_refresh_token:
                config["user_token_refresh"] = self._user_refresh_token
            config["user_token_expire_at"] = int(self._user_token_expire_time)
            with open(self._config_path, "w", encoding="utf-8") as f:
                _json.dump(config, f, ensure_ascii=False, indent=4)
            logger.info("已将刷新后的 token 回写到 %s", self._config_path)
        except Exception as e:
            logger.warning("回写 config.json 失败: %s", e)

    def _refresh_token(self) -> None:
        """获取或刷新 tenant_access_token"""
        url = f"{self.base_url}{_TOKEN_ENDPOINT}"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise FeishuNetworkError(
                code=-1,
                msg="获取 tenant_access_token 网络请求失败",
                detail=str(e),
            )

        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAuthError(
                code=data.get("code", -1),
                msg=data.get("msg", "获取 tenant_access_token 失败"),
            )

        self._tenant_access_token = data["tenant_access_token"]
        expire = data.get("expire", 7200)  # 默认 2 小时
        self._token_expire_time = time.time() + expire
        logger.info("tenant_access_token 刷新成功，有效期 %d 秒", expire)

    def get_token(self) -> str:
        """
        获取有效的 tenant_access_token，必要时自动刷新

        Returns:
            有效的 tenant_access_token
        """
        if not self._is_token_valid():
            self._refresh_token()
        return self._tenant_access_token  # type: ignore

    # ──────────────────────────────────────────────
    #  统一请求方法
    # ──────────────────────────────────────────────

    def _build_url(self, path: str) -> str:
        """拼接完整的 API URL"""
        if path.startswith("http"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _classify_error(code: int, msg: str) -> FeishuError:
        """根据错误码分类异常"""
        if code in (99991663, 99991664, 99991668):
            return FeishuAuthError(code=code, msg=msg)
        if code in (99991400, 99991403):
            return FeishuPermissionError(code=code, msg=msg)
        if code == 99991404:
            return FeishuNotFoundError(code=code, msg=msg)
        if code == 99991429:
            return FeishuRateLimitError(code=code, msg=msg)
        return FeishuError(code=code, msg=msg)

    def request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
        **kwargs: Any,
    ) -> dict:
        """
        发送 API 请求（自动携带认证 token，自动重试）

        Args:
            method: HTTP 方法（GET, POST, PUT, PATCH, DELETE）
            path: API 路径，如 "docx/v1/documents"
            params: URL 查询参数
            json_body: JSON 请求体
            headers: 额外的请求头
            **kwargs: 传递给 requests 的其他参数

        Returns:
            API 响应中的 data 字段（dict）

        Raises:
            FeishuError: API 返回错误
            FeishuNetworkError: 网络请求失败
        """
        url = self._build_url(path)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            # 获取有效的 Token
            if self._use_user_mode:
                # 检查用户 token 是否过期，过期则自动续期
                if not self._is_token_valid():
                    self._refresh_user_token()
                token = self._user_access_token
            else:
                token = self.get_token()

            req_headers = {"Authorization": f"Bearer {token}"}
            if headers:
                req_headers.update(headers)

            try:
                resp = self._session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body,
                    headers=req_headers,
                    timeout=self.timeout,
                    **kwargs,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                last_error = FeishuNetworkError(
                    code=-1, msg=f"HTTP 请求失败 (第 {attempt} 次)", detail=str(e)
                )
                logger.warning("请求失败 [%s %s] 第 %d 次: %s", method, path, attempt, e)
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 10))
                continue

            result = resp.json()
            code = result.get("code", 0)
            # 部分接口把业务 code 放在 data 里
            if code == 0 and isinstance(result.get("data"), dict):
                data_code = result["data"].get("code", 0)
                if data_code != 0:
                    code = data_code

            if code == 0:
                return result.get("data", {})

            # token 过期 → 强制刷新后重试
            if code in _TOKEN_EXPIRED_CODES:
                logger.warning("Token 过期 (code=%s)，尝试刷新并重试...", code)
                try:
                    if self._use_user_mode:
                        self._refresh_user_token()
                    else:
                        self._tenant_access_token = None
                        self._token_expire_time = 0
                except FeishuAuthError as e:
                    if self._use_user_mode and "refresh_token" in (e.msg or ""):
                        raise FeishuAuthError(
                            code=e.code,
                            msg="user_access_token 已过期且无法自动续期（无 refresh_token），请重新运行 feishu_auth.py 扫码授权后再试。",
                        )
                    raise
                if attempt < self.max_retries:
                    continue

            # 频率限制 → 等待后重试
            if code == 99991429:
                logger.warning("触发频率限制，等待后重试...")
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 10))
                    continue

            # 其他错误 → 抛出
            msg = result.get("msg", "未知错误")
            raise self._classify_error(code, msg)

        # 所有重试都失败
        if last_error:
            raise last_error
        raise FeishuError(code=-1, msg="请求失败，已耗尽所有重试次数")

    # ──────────────────────────────────────────────
    #  便捷方法
    # ──────────────────────────────────────────────

    def get(self, path: str, params: Optional[dict] = None, **kwargs: Any) -> dict:
        """发送 GET 请求"""
        return self.request("GET", path, params=params, **kwargs)

    def post(
        self, path: str, json_body: Optional[dict] = None, **kwargs: Any
    ) -> dict:
        """发送 POST 请求"""
        return self.request("POST", path, json_body=json_body, **kwargs)

    def put(
        self, path: str, json_body: Optional[dict] = None, **kwargs: Any
    ) -> dict:
        """发送 PUT 请求"""
        return self.request("PUT", path, json_body=json_body, **kwargs)

    def patch(
        self, path: str, json_body: Optional[dict] = None, **kwargs: Any
    ) -> dict:
        """发送 PATCH 请求"""
        return self.request("PATCH", path, json_body=json_body, **kwargs)

    def delete(
        self, path: str, json_body: Optional[dict] = None, **kwargs: Any
    ) -> dict:
        """发送 DELETE 请求"""
        return self.request("DELETE", path, json_body=json_body, **kwargs)

    # ──────────────────────────────────────────────
    #  分页辅助
    # ──────────────────────────────────────────────

    def get_all_pages(
        self,
        path: str,
        params: Optional[dict] = None,
        items_key: str = "items",
        page_size: int = 50,
    ) -> list:
        """
        自动处理分页，获取所有数据

        Args:
            path: API 路径
            params: 查询参数
            items_key: 返回数据中列表字段的 key
            page_size: 每页数量

        Returns:
            合并后的完整列表
        """
        all_items = []
        page_token = None
        _params = dict(params or {})
        _params["page_size"] = page_size

        while True:
            if page_token:
                _params["page_token"] = page_token
            data = self.get(path, params=_params)
            items = data.get(items_key, [])
            if items:
                all_items.extend(items)
            if not data.get("has_more", False):
                break
            page_token = data.get("page_token")
            if not page_token:
                break

        return all_items

    def close(self) -> None:
        """关闭 HTTP 连接"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
