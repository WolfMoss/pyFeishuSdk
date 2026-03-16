"""
飞书 Python SDK - 为 AI Agent 设计的飞书开放平台封装

提供文档、多维表格、知识空间等核心能力的 Python 接口。

快速开始::

    from feishu import FeishuClient, DocumentAPI, BitableAPI, WikiAPI

    # 初始化客户端
    client = FeishuClient(app_id="cli_xxx", app_secret="xxx")

    # 操作文档
    docs = DocumentAPI(client)
    doc = docs.create(title="AI 生成的文档")
    docs.append_text(doc["document"]["document_id"], "Hello from AI Agent!")

    # 操作多维表格
    bitable = BitableAPI(client)
    records = bitable.search_all_records(app_token="bascnXXX", table_id="tblXXX")

    # 操作知识空间
    wiki = WikiAPI(client)
    spaces = wiki.list_spaces()
"""

from .client import FeishuClient
from .documents import DocumentAPI
from .bitable import BitableAPI
from .wiki import WikiAPI
from .drive import DriveAPI
from .exceptions import (
    FeishuError,
    FeishuAuthError,
    FeishuPermissionError,
    FeishuNotFoundError,
    FeishuRateLimitError,
    FeishuNetworkError,
)

__version__ = "1.0.0"

__all__ = [
    "FeishuClient",
    "DocumentAPI",
    "BitableAPI",
    "WikiAPI",
    "FeishuError",
    "FeishuAuthError",
    "FeishuPermissionError",
    "FeishuNotFoundError",
    "FeishuRateLimitError",
    "FeishuNetworkError",
]
