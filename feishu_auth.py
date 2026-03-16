"""
飞书 OAuth 扫码授权脚本

功能：在终端生成可扫描的二维码，用手机飞书扫码后自动以用户身份授权，并将
user_access_token 保存到 config.json，之后 SDK 可以直接以用户身份访问所有
你有权限的文档和多维表格，无需手动设置任何分享权限。

用法：
    python feishu_auth.py
"""

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
import qrcode

# ─── 配置 ───────────────────────────────────────────
CONFIG_FILE = "config.json"
CALLBACK_PORT = 9721  # 本地回调端口，和飞书开放平台配置保持一致
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
BASE_URL = "https://open.feishu.cn/open-apis"
# ────────────────────────────────────────────────────

_auth_code: str | None = None
_server_done = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    """临时 HTTP Server，接收飞书 OAuth 回调中的 code 参数"""

    def do_GET(self):
        global _auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            # 返回成功页面，关闭浏览器标签
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;margin-top:100px">
                <h2>&#10003; \u6388\u6743\u6210\u529f\uff01</h2>
                <p>\u5df2\u83b7\u53d6\u548c\u4fdd\u5b58 user_access_token\uff0c\u6b64\u7a97\u53e3\u53ef\u5173\u95ed\u3002</p>
                </body></html>
            """)
            _server_done.set()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter")

    def log_message(self, format, *args):
        pass  # 静默日志


def _run_server():
    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 1
    while not _server_done.is_set():
        server.handle_request()
    server.server_close()


def _print_qrcode(url: str):
    """在终端用字符画打印二维码"""
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def _get_app_access_token(app_id: str, app_secret: str) -> str:
    """自建应用获取 app_access_token，用于调用 v1 接口。"""
    resp = requests.post(
        f"{BASE_URL}/auth/v3/app_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"获取 app_access_token 失败: {data}")
    return data.get("app_access_token") or data.get("tenant_access_token") or ""


def _exchange_code_v1(app_access_token: str, code: str) -> dict:
    """v1 用授权码换 token（请求头带 app_access_token），文档称会返回 refresh_token。"""
    resp = requests.post(
        f"{BASE_URL}/authen/v1/access_token",
        headers={"Authorization": f"Bearer {app_access_token}"},
        json={"grant_type": "authorization_code", "code": code},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _exchange_code_v2(app_id: str, app_secret: str, code: str) -> dict:
    """v2 用授权码换 token；授权 URL 的 scope 需包含 offline_access 才会返回 refresh_token。"""
    resp = requests.post(
        f"{BASE_URL}/authen/v2/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": app_secret,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"换取 token 失败: {data}")
    return data


def main():
    # 1. 读取配置
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)

    app_id = config["app_id"]
    app_secret = config["app_secret"]

    # 2. 检查飞书开放平台是否配置了回调地址
    print("=" * 60)
    print("  飞书 OAuth 扫码授权")
    print("=" * 60)
    print(f"\n[前置检查] 请确认飞书开放平台的应用安全设置中")
    print(f"已将以下地址添加为【重定向 URL (Redirect URI)】：")
    print(f"  >> {REDIRECT_URI}")
    print(f"\n路径：开放平台 -> 你的应用 -> 安全设置 -> 重定向 URL")
    print("-" * 60)
    input("确认已添加后，按回车继续...\n")

    # 3. 构造授权 URL（scope 必须包含 offline_access 才能拿到 refresh_token，见飞书长期授权文档）
    auth_params = urlencode({
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": (
            "bitable:app wiki:wiki docx:document "
            "drive:drive contact:user.base:readonly offline_access"
        ),
    })
    auth_url = f"https://open.feishu.cn/open-apis/authen/v1/authorize?{auth_params}"

    # 4. 启动本地回调服务器（后台线程）
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    # 5. 打印二维码到终端
    print("请用手机飞书 App 扫描以下二维码进行授权：\n")
    _print_qrcode(auth_url)
    print(f"\n或将此链接复制到浏览器打开：\n{auth_url}\n")
    print("等待授权中...")

    # 同时尝试在 PC 浏览器打开
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # 6. 等待用户完成授权（最多等 120 秒）
    success = _server_done.wait(timeout=120)
    if not success or not _auth_code:
        print("超时或未收到授权码，请重新运行脚本。")
        return

    print(f"\n已收到授权码，正在换取 user_access_token...")

    # 7. 用 code 换取 token（优先 v1，v1 会返回 refresh_token；失败则用 v2）
    raw = None
    try:
        app_token = _get_app_access_token(app_id, app_secret)
        if app_token:
            raw = _exchange_code_v1(app_token, _auth_code)
            if raw.get("code", 0) == 0 and (raw.get("data", {}).get("access_token") or raw.get("access_token")):
                print("  已通过 v1 接口获取 token（便于拿到 refresh_token）")
    except Exception as e:
        print(f"  v1 换 token 未用上: {e}")
    if raw is None or raw.get("code", 0) != 0:
        try:
            raw = _exchange_code_v2(app_id, app_secret, _auth_code)
        except Exception as e:
            print(f"换取 token 失败: {e}")
            return

    # 兼容 data 在 data 内或顶层混用（v1/v2 文档不一致）
    token_data = raw.get("data", raw) if isinstance(raw.get("data"), dict) else raw
    user_token = token_data.get("access_token") or token_data.get("user_access_token")
    refresh_token = (
        token_data.get("refresh_token")
        or (raw.get("refresh_token") if isinstance(raw, dict) else "")
        or ""
    )
    expires_in = token_data.get("expires_in") or raw.get("expires_in") or 7200
    expire_at = int(time.time()) + expires_in

    if not user_token:
        print(f"未能从响应中获取 token，完整响应：{raw}")
        return

    # 8. 保存到 config.json
    config["user_access_token"] = user_token
    config["user_token_refresh"] = refresh_token
    config["user_token_expire_at"] = expire_at

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

    print("\n" + "=" * 60)
    print("  授权成功！")
    print("=" * 60)
    print(f"  user_access_token: {user_token[:20]}...")
    print(f"  有效期: {expires_in // 3600} 小时")
    if refresh_token:
        print(f"  refresh_token: 已保存（可自动续期）")
    else:
        print(f"  refresh_token: 未返回，token 过期后需重新运行本脚本扫码授权。")
    print(f"  已保存到 config.json")
    print("\n现在可以直接运行 read_my_table.py 了，无需分享表格权限！")
    print("=" * 60)


if __name__ == "__main__":
    main()
