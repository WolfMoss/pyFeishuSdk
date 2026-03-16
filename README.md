# 飞书 Python SDK

为 AI Agent 设计的飞书开放平台 Python SDK，支持操作飞书文档、多维表格和知识空间。

## 特性

- 🔐 **自动认证管理** — 支持应用身份 (`tenant_access_token`) 和用户身份 (`user_access_token`)
- 🤖 **MCP 支持** — 内置 Claude Desktop MCP Server，让 AI 具备“全自动发现并读写”能力
- 📄 **云文档操作** — 创建/读取/编辑飞书新版文档 (docx)
- 📊 **多维表格操作** — 自动搜索表格、解析结构、完整的记录 CRUD
- 📚 **知识空间操作** — 空间和节点管理
- 🔄 **自动分页** — 内置分页处理，一次获取所有数据
- 🛡️ **智能重试** — 自动处理 token 过期和频率限制

## 快速开始

### 1. 安装依赖
```bash
pip install requests qrcode pillow mcp
```

### 2. 配置与授权
1. 将 `config_example.json` 复制为 `config.json` 并填写 `app_id` 和 `app_secret`。
2. 运行扫码授权脚本（获取用户权限，避免手动分享表格）：
   ```bash
   python feishu_auth.py
   ```
   *注意：需在飞书控制台设置重定向 URL 为 `http://localhost:9721/callback`*

## Claude Desktop (MCP) 部署

通过 MCP 协议，你可以让 Claude 直接成为你的飞书助手。

### 配置方式
修改 Claude 的配置文件（Windows: `%APPDATA%\Claude\claude_desktop_config.json`），添加以下内容：

```json
{
  "mcpServers": {
    "feishu": {
      "command": "python",
      "args": [
        "d:/codes/hxy/pyFeishuSdk/mcp_feishu_server.py"
      ],
      "env": {
        "PYTHONPATH": "d:/codes/hxy/pyFeishuSdk"
      }
    }
  }
}
```

### 常用指令示例
- "帮我列出我名下所有的多维表格。"
- "读取表格 `AyUL...in0S` 的结构，并统计里面有多少行记录。"
- "把今天的会议结论写进飞书文档‘今日纪要’里。"

## 项目结构

```
feishu/
├── __init__.py      # 包入口
├── client.py        # 核心客户端（认证/重试/身份切换）
├── documents.py     # 云文档 API
├── bitable.py       # 多维表格 API
├── wiki.py          # 知识空间 API
├── drive.py         # 云空间搜索 API
└── exceptions.py    # 异常定义
mcp_feishu_server.py # Claude MCP 服务端
feishu_auth.py       # 扫码授权工具 (OpenClaw 同款模式)
```

## License

MIT
