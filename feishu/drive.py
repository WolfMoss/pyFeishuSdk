"""
飞书云空间 (Drive) API 模块

用于搜索和管理云空间文件，AI Agent 可以通过此模块发现用户的多维表格等文档。
"""

from typing import Optional, List
from .client import FeishuClient


class DriveAPI:
    def __init__(self, client: FeishuClient):
        self.client = client

    def search_files(
        self,
        query: str = "",
        docs_types: Optional[List[str]] = None,
        count: int = 50,
        offset: int = 0,
    ) -> list:
        """
        搜索云空间文件

        Args:
            query: 搜索关键词（为空则返回最近文件）
            docs_types: 文档类型列表，可选值:
                        "doc" (旧版文档), "docx" (新版文档), 
                        "sheet" (电子表格), "bitable" (多维表格),
                        "mindnote" (思维笔记), "wiki" (知识库节点)
            count: 返回数量，最大 50
            offset: 偏移量，用于翻页

        Returns:
            文件列表，每项包含 title, url, docs_token, docs_type 等
        """
        body = {
            "search_key": query,
            "count": min(count, 50),
            "offset": offset,
        }
        if docs_types:
            body["docs_types"] = docs_types

        # 飞书搜索接口: POST /suite/docs-api/search/object
        data = self.client.post("suite/docs-api/search/object", json_body=body)

        # 返回结构: {"docs_entities": [...], "total": N, "has_more": bool}
        return data.get("docs_entities", [])

    def search_all(
        self,
        query: str = "",
        docs_types: Optional[List[str]] = None,
    ) -> list:
        """
        搜索所有匹配文件（自动翻页）
        """
        all_items = []
        offset = 0
        while True:
            items = self.search_files(query, docs_types, count=50, offset=offset)
            if not items:
                break
            all_items.extend(items)
            offset += len(items)
            if len(items) < 50:
                break
        return all_items

    def list_folder(self, folder_token: str = "") -> list:
        """
        列出指定文件夹下的文件

        Args:
            folder_token: 文件夹 token，为空则列出根目录
        """
        params = {"page_size": 50}
        if folder_token:
            params["folder_token"] = folder_token

        return self.client.get_all_pages(
            "drive/v1/files",
            params=params,
            items_key="files",
        )
