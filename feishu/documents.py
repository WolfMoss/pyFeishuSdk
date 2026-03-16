"""
飞书云文档 (Docx) API 模块

提供飞书新版文档 (docx 格式) 的创建、读取、编辑操作。
文档内容以"块 (Block)"为基本单位组织。
"""

from typing import Optional, List

from .client import FeishuClient


class DocumentAPI:
    """
    飞书云文档 API

    示例::

        from feishu import FeishuClient
        from feishu.documents import DocumentAPI

        client = FeishuClient(app_id="xxx", app_secret="xxx")
        docs = DocumentAPI(client)

        # 创建文档
        doc = docs.create(title="测试文档", folder_token="fldcnXXXX")

        # 获取文档纯文本
        text = docs.get_raw_content(doc["document"]["document_id"])
    """

    def __init__(self, client: FeishuClient):
        self.client = client

    # ──────────────────────────────────────────────
    #  文档级操作
    # ──────────────────────────────────────────────

    def create(
        self,
        title: Optional[str] = None,
        folder_token: Optional[str] = None,
    ) -> dict:
        """
        创建新文档

        Args:
            title: 文档标题
            folder_token: 目标文件夹 token，不传则创建在根目录

        Returns:
            文档信息，包含 document.document_id
        """
        body = {}
        if title:
            body["title"] = title
        if folder_token:
            body["folder_token"] = folder_token
        return self.client.post("docx/v1/documents", json_body=body)

    def get_info(self, document_id: str) -> dict:
        """
        获取文档基本信息（标题、版本等）

        Args:
            document_id: 文档 ID

        Returns:
            文档基本信息
        """
        return self.client.get(f"docx/v1/documents/{document_id}")

    def get_raw_content(self, document_id: str, lang: int = 0) -> str:
        """
        获取文档纯文本内容

        Args:
            document_id: 文档 ID
            lang: 指定语言，0=中文，1=英文，2=日文

        Returns:
            文档的纯文本字符串
        """
        data = self.client.get(
            f"docx/v1/documents/{document_id}/raw_content",
            params={"lang": lang},
        )
        return data.get("content", "")

    # ──────────────────────────────────────────────
    #  块 (Block) 操作
    # ──────────────────────────────────────────────

    def list_blocks(
        self,
        document_id: str,
        page_size: int = 500,
        page_token: Optional[str] = None,
        document_revision_id: int = -1,
    ) -> dict:
        """
        获取文档所有块（分页）

        Args:
            document_id: 文档 ID
            page_size: 每页数量，最大 500
            page_token: 分页标记
            document_revision_id: 文档版本，-1 表示最新版本

        Returns:
            包含 items (块列表) 和分页信息的 dict
        """
        params = {
            "page_size": page_size,
            "document_revision_id": document_revision_id,
        }
        if page_token:
            params["page_token"] = page_token
        return self.client.get(
            f"docx/v1/documents/{document_id}/blocks", params=params
        )

    def get_all_blocks(self, document_id: str) -> list:
        """
        获取文档所有块（自动分页）

        Args:
            document_id: 文档 ID

        Returns:
            所有块的列表
        """
        return self.client.get_all_pages(
            f"docx/v1/documents/{document_id}/blocks",
            items_key="items",
            page_size=500,
        )

    def get_block(self, document_id: str, block_id: str) -> dict:
        """
        获取单个块的信息

        Args:
            document_id: 文档 ID
            block_id: 块 ID

        Returns:
            块信息
        """
        return self.client.get(
            f"docx/v1/documents/{document_id}/blocks/{block_id}"
        )

    def get_block_children(
        self,
        document_id: str,
        block_id: str,
        page_size: int = 500,
        page_token: Optional[str] = None,
    ) -> dict:
        """
        获取块的子块列表（分页）

        Args:
            document_id: 文档 ID
            block_id: 块 ID
            page_size: 每页数量
            page_token: 分页标记

        Returns:
            子块列表和分页信息
        """
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        return self.client.get(
            f"docx/v1/documents/{document_id}/blocks/{block_id}/children",
            params=params,
        )

    def create_block_children(
        self,
        document_id: str,
        block_id: str,
        children: List[dict],
        index: Optional[int] = None,
    ) -> dict:
        """
        在指定块下创建子块

        Args:
            document_id: 文档 ID
            block_id: 父块 ID（文档级别的 block_id 等于 document_id）
            children: 子块定义列表，每个元素为 block 结构体
            index: 插入位置索引，不传则追加到末尾

        Returns:
            创建结果，包含新创建的块信息

        示例::

            # 添加一段文本到文档末尾
            docs.create_block_children(
                document_id="docxXXX",
                block_id="docxXXX",  # 文档根块 ID = document_id
                children=[{
                    "block_type": 2,  # 2=文本块
                    "text": {
                        "elements": [{
                            "text_run": {
                                "content": "Hello, World!"
                            }
                        }]
                    }
                }]
            )
        """
        body: dict = {"children": children}
        if index is not None:
            body["index"] = index
        return self.client.post(
            f"docx/v1/documents/{document_id}/blocks/{block_id}/children",
            json_body=body,
        )

    def update_block(
        self, document_id: str, block_id: str, update_body: dict
    ) -> dict:
        """
        更新指定块的内容

        Args:
            document_id: 文档 ID
            block_id: 块 ID
            update_body: 更新内容，具体结构参考飞书文档

        Returns:
            更新结果
        """
        return self.client.patch(
            f"docx/v1/documents/{document_id}/blocks/{block_id}",
            json_body=update_body,
        )

    def batch_delete_blocks(
        self,
        document_id: str,
        block_id: str,
        start_index: int,
        end_index: int,
    ) -> dict:
        """
        批量删除指定块的子块

        Args:
            document_id: 文档 ID
            block_id: 父块 ID
            start_index: 起始索引（包含）
            end_index: 结束索引（不包含）

        Returns:
            删除结果
        """
        body = {
            "start_index": start_index,
            "end_index": end_index,
        }
        return self.client.delete(
            f"docx/v1/documents/{document_id}/blocks/{block_id}/children/batch_delete",
            json_body=body,
        )

    # ──────────────────────────────────────────────
    #  高级便捷方法（对 AI Agent 友好）
    # ──────────────────────────────────────────────

    def append_text(self, document_id: str, text: str) -> dict:
        """
        在文档末尾追加一段文本（便捷方法）

        Args:
            document_id: 文档 ID
            text: 要追加的文本内容

        Returns:
            创建结果
        """
        children = [
            {
                "block_type": 2,  # 文本块
                "text": {
                    "elements": [
                        {
                            "text_run": {
                                "content": text,
                            }
                        }
                    ]
                },
            }
        ]
        return self.create_block_children(
            document_id=document_id,
            block_id=document_id,  # 文档根块
            children=children,
        )

    def append_heading(
        self, document_id: str, text: str, level: int = 1
    ) -> dict:
        """
        在文档末尾追加标题（便捷方法）

        Args:
            document_id: 文档 ID
            text: 标题文本
            level: 标题级别 (1-9)

        Returns:
            创建结果
        """
        # block_type: 3=H1, 4=H2, 5=H3, 6=H4, 7=H5, 8=H6, 9=H7, 10=H8, 11=H9
        block_type = 2 + level
        children = [
            {
                "block_type": block_type,
                "heading1" if level == 1 else
                "heading2" if level == 2 else
                "heading3" if level == 3 else
                "heading4" if level == 4 else
                "heading5" if level == 5 else
                "heading6" if level == 6 else
                "heading7" if level == 7 else
                "heading8" if level == 8 else
                "heading9": {
                    "elements": [
                        {
                            "text_run": {
                                "content": text,
                            }
                        }
                    ]
                },
            }
        ]
        return self.create_block_children(
            document_id=document_id,
            block_id=document_id,
            children=children,
        )

    def append_bullet_list(
        self, document_id: str, items: List[str]
    ) -> dict:
        """
        在文档末尾追加无序列表（便捷方法）

        Args:
            document_id: 文档 ID
            items: 列表项文本列表

        Returns:
            创建结果
        """
        children = [
            {
                "block_type": 13,  # 无序列表
                "bullet": {
                    "elements": [
                        {
                            "text_run": {
                                "content": item,
                            }
                        }
                    ]
                },
            }
            for item in items
        ]
        return self.create_block_children(
            document_id=document_id,
            block_id=document_id,
            children=children,
        )

    def append_ordered_list(
        self, document_id: str, items: List[str]
    ) -> dict:
        """
        在文档末尾追加有序列表（便捷方法）

        Args:
            document_id: 文档 ID
            items: 列表项文本列表

        Returns:
            创建结果
        """
        children = [
            {
                "block_type": 14,  # 有序列表
                "ordered": {
                    "elements": [
                        {
                            "text_run": {
                                "content": item,
                            }
                        }
                    ]
                },
            }
            for item in items
        ]
        return self.create_block_children(
            document_id=document_id,
            block_id=document_id,
            children=children,
        )

    def append_code_block(
        self, document_id: str, code: str, language: int = 0
    ) -> dict:
        """
        在文档末尾追加代码块（便捷方法）

        Args:
            document_id: 文档 ID
            code: 代码内容
            language: 编程语言类型编号（0=PlainText, 1=ABAP, ...）

        Returns:
            创建结果
        """
        children = [
            {
                "block_type": 15,  # 代码块
                "code": {
                    "elements": [
                        {
                            "text_run": {
                                "content": code,
                            }
                        }
                    ],
                    "language": language,
                },
            }
        ]
        return self.create_block_children(
            document_id=document_id,
            block_id=document_id,
            children=children,
        )
