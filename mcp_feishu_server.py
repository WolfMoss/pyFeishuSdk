import json
import os
from mcp.server.fastmcp import FastMCP
from feishu import FeishuClient, DocumentAPI, BitableAPI, WikiAPI, DriveAPI

# 1. 初始化 MCP
mcp = FastMCP("Feishu-Agent-Skill")

# 2. 每次调用都从 config 实时读取并创建客户端
def get_feishu_clients():
    """从 config.json 实时读取配置并返回 API 实例（每次工具调用都会读到最新 token）。"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    client = FeishuClient(config["app_id"], config["app_secret"])

    user_token = config.get("user_access_token")
    if user_token:
        client.switch_to_user_mode(
            user_token=user_token,
            refresh_token=config.get("user_token_refresh", ""),
            expire_at=config.get("user_token_expire_at", 0),
            config_path=config_path,
        )

    return DocumentAPI(client), BitableAPI(client), WikiAPI(client), DriveAPI(client)


def _repair_mojibake(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    candidates = [text]
    for src, dst in (("latin1", "utf-8"), ("gbk", "utf-8")):
        try:
            repaired = text.encode(src).decode(dst)
        except Exception:
            continue
        if repaired and repaired not in candidates:
            candidates.append(repaired)
    return candidates[-1]


def _normalize_bitable_fields(
    bitable_api: BitableAPI, app_token: str, table_id: str, fields: dict
) -> dict:
    schema = bitable_api.list_fields(app_token, table_id)
    alias_to_actual = {}
    expected_labels = [
        "时间",
        "标题",
        "一级分类",
        "二级分类",
        "三级分类",
        "链接",
        "内容摘要",
    ]

    for idx, field in enumerate(schema):
        actual = field.get("field_name")
        if not actual:
            continue
        for alias in {actual, _repair_mojibake(actual)}:
            if alias:
                alias_to_actual[alias] = actual
        if idx < len(expected_labels):
            alias_to_actual[expected_labels[idx]] = actual

    normalized = {}
    for key, value in fields.items():
        normalized[alias_to_actual.get(key, key)] = value
    return normalized


# ---------------------------------------------------------
# 工具定义：搜索与发现
# ---------------------------------------------------------

@mcp.tool()
def list_my_bitables(keyword: str = "") -> str:
    """搜索并列出用户所有的多维表格（Bitable）。可以提供关键词缩小范围。"""
    _, _, _, drive_api = get_feishu_clients()
    files = drive_api.search_files(query=keyword, docs_types=["bitable"])
    if not files:
        return "未发现多维表格。"
    
    res = ["发现以下多维表格:"]
    for f in files:
        title = f.get("title", "未命名")
        token = f.get("docs_token", "")
        res.append(f"- {title}\n  app_token: {token}")
    return "\n".join(res)

@mcp.tool()
def get_bitable_structure(app_token: str) -> str:
    """获取一个多维表格的完整结构：包括所有数据表名称和每张表的字段列表。"""
    _, bitable_api, _, _ = get_feishu_clients()
    tables = bitable_api.list_tables(app_token)
    if not tables:
        return "该表格中没有数据表。"
    
    res = [f"多维表格结构 (app_token: {app_token}):"]
    for t in tables:
        table_id = t["table_id"]
        table_name = t["name"]
        res.append(f"\n数据表: {table_name} (table_id: {table_id})")
        
        fields_data = bitable_api.get_table_schema(app_token, table_id)
        for f in fields_data["fields"]:
            res.append(f"  - {f['field_name']} (类型: {f['type']})")
        
    return "\n".join(res)

# ---------------------------------------------------------
# 工具定义：多维表格读写
# ---------------------------------------------------------

@mcp.tool()
def read_bitable_records(app_token: str, table_id: str, page_size: int = 20) -> str:
    """读取多维表格中的记录。默认返回前 20 条。"""
    _, bitable_api, _, _ = get_feishu_clients()
    result = bitable_api.search_records(app_token, table_id, page_size=page_size)
    items = result.get("items", [])
    if not items:
        return "该数据表目前没有记录。"
    return json.dumps(items, ensure_ascii=False, indent=2)

@mcp.tool()
def add_bitable_record(app_token: str, table_id: str, fields_json: str) -> str:
    """往多维表格插入一条记录。fields_json 是 JSON 字符串，格式为 {"字段名": "值", ...}。"""
    _, bitable_api, _, _ = get_feishu_clients()
    fields = json.loads(fields_json)
    fields = _normalize_bitable_fields(bitable_api, app_token, table_id, fields)
    res = bitable_api.create_record(app_token, table_id, fields)
    return f"记录已插入。Record ID: {res['record']['record_id']}"

@mcp.tool()
def update_bitable_record(app_token: str, table_id: str, record_id: str, fields_json: str) -> str:
    """更新多维表格中的一条记录。fields_json 是 JSON 字符串，格式为 {"字段名": "新值", ...}。"""
    _, bitable_api, _, _ = get_feishu_clients()
    fields = json.loads(fields_json)
    fields = _normalize_bitable_fields(bitable_api, app_token, table_id, fields)
    bitable_api.update_record(app_token, table_id, record_id, fields)
    return f"记录 {record_id} 已更新。"

@mcp.tool()
def delete_bitable_record(app_token: str, table_id: str, record_id: str) -> str:
    """删除多维表格中的一条记录。"""
    _, bitable_api, _, _ = get_feishu_clients()
    bitable_api.delete_record(app_token, table_id, record_id)
    return f"记录 {record_id} 已删除。"

@mcp.tool()
def search_bitable_records(app_token: str, table_id: str, field_name: str, value: str) -> str:
    """在多维表格中按字段搜索记录。"""
    _, bitable_api, _, _ = get_feishu_clients()
    filter_obj = {
        "conjunction": "and",
        "conditions": [{"field_name": field_name, "operator": "is", "value": [value]}]
    }
    records = bitable_api.search_records(app_token, table_id, filter=filter_obj)
    items = records.get("items", [])
    if not items:
        return "未找到匹配的记录。"
    return json.dumps(items, ensure_ascii=False, indent=2)

# ---------------------------------------------------------
# 工具定义：文档操作
# ---------------------------------------------------------

@mcp.tool()
def create_feishu_document(title: str) -> str:
    """在飞书云文档中创建一个新文档。返回文档 ID。"""
    docs_api, _, _, _ = get_feishu_clients()
    res = docs_api.create(title=title)
    doc_id = res["document"]["document_id"]
    return f"已成功创建文档: {title}\nID: {doc_id}"

@mcp.tool()
def append_text_to_document(document_id: str, text: str) -> str:
    """向指定的飞书文档末尾追加文本内容。"""
    docs_api, _, _, _ = get_feishu_clients()
    docs_api.append_text(document_id, text)
    return "内容已成功追加到文档。"

@mcp.tool()
def read_document_content(document_id: str) -> str:
    """读取并返回飞书文档的纯文本内容。"""
    docs_api, _, _, _ = get_feishu_clients()
    content = docs_api.get_raw_content(document_id)
    return content

if __name__ == "__main__":
    mcp.run()
