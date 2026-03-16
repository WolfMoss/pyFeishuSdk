"""
飞书知识空间 (Wiki) API 模块

提供知识空间管理、节点操作等功能。
"""

from typing import Optional

from .client import FeishuClient


class WikiAPI:
    """
    飞书知识空间 API

    示例::

        from feishu import FeishuClient
        from feishu.wiki import WikiAPI

        client = FeishuClient(app_id="xxx", app_secret="xxx")
        wiki = WikiAPI(client)

        # 列出知识空间
        spaces = wiki.list_spaces()
    """

    def __init__(self, client: FeishuClient):
        self.client = client

    # ──────────────────────────────────────────────
    #  知识空间管理
    # ──────────────────────────────────────────────

    def list_spaces(self) -> list:
        """
        获取有权限访问的知识空间列表

        Returns:
            知识空间列表
        """
        return self.client.get_all_pages(
            "wiki/v2/spaces",
            items_key="items",
        )

    def get_space(self, space_id: str) -> dict:
        """
        获取知识空间详情

        Args:
            space_id: 知识空间 ID

        Returns:
            知识空间详细信息
        """
        return self.client.get(f"wiki/v2/spaces/{space_id}")

    # ──────────────────────────────────────────────
    #  节点管理
    # ──────────────────────────────────────────────

    def list_nodes(
        self,
        space_id: str,
        parent_node_token: Optional[str] = None,
    ) -> list:
        """
        获取知识空间的节点列表

        Args:
            space_id: 知识空间 ID
            parent_node_token: 父节点 token，不传则返回一级节点

        Returns:
            节点列表
        """
        params = {}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        return self.client.get_all_pages(
            f"wiki/v2/spaces/{space_id}/nodes",
            params=params,
            items_key="items",
        )

    def get_node(self, token: str, obj_type: Optional[str] = None) -> dict:
        """
        获取节点信息

        Args:
            token: 节点 token 或对应文档的 token
            obj_type: 文档类型（如 "docx", "sheet", "bitable" 等）

        Returns:
            节点信息
        """
        params = {"token": token}
        if obj_type:
            params["obj_type"] = obj_type
        return self.client.get("wiki/v2/spaces/get_node", params=params)

    def create_node(
        self,
        space_id: str,
        obj_type: str,
        parent_node_token: Optional[str] = None,
        title: Optional[str] = None,
        obj_token: Optional[str] = None,
    ) -> dict:
        """
        在知识空间中创建节点

        Args:
            space_id: 知识空间 ID
            obj_type: 节点类型
                - "docx": 新版文档
                - "sheet": 电子表格
                - "bitable": 多维表格
                - "mindnote": 思维笔记
                - "file": 文件
            parent_node_token: 父节点 token，不传则创建在根目录
            title: 节点标题
            obj_token: 关联的文档 token（若要将已有文档放入知识空间）

        Returns:
            新创建的节点信息
        """
        body: dict = {"obj_type": obj_type}
        if parent_node_token:
            body["parent_node_token"] = parent_node_token
        if title:
            body["title"] = title
        if obj_token:
            body["obj_token"] = obj_token
        return self.client.post(
            f"wiki/v2/spaces/{space_id}/nodes", json_body=body
        )

    def move_node(
        self,
        space_id: str,
        node_token: str,
        target_parent_token: Optional[str] = None,
        target_space_id: Optional[str] = None,
    ) -> dict:
        """
        移动知识空间节点

        Args:
            space_id: 当前知识空间 ID
            node_token: 要移动的节点 token
            target_parent_token: 目标父节点 token
            target_space_id: 目标知识空间 ID（跨空间移动时需要）

        Returns:
            移动结果
        """
        body: dict = {}
        if target_parent_token:
            body["target_parent_token"] = target_parent_token
        if target_space_id:
            body["target_space_id"] = target_space_id
        return self.client.post(
            f"wiki/v2/spaces/{space_id}/nodes/{node_token}/move",
            json_body=body,
        )

    def delete_node(self, space_id: str, node_token: str) -> dict:
        """
        删除知识空间节点（会同时删除关联的文档）

        Args:
            space_id: 知识空间 ID
            node_token: 节点 token

        Returns:
            删除结果
        """
        return self.client.delete(
            f"wiki/v2/spaces/{space_id}/nodes/{node_token}"
        )

    # ──────────────────────────────────────────────
    #  高级便捷方法（对 AI Agent 友好）
    # ──────────────────────────────────────────────

    def get_space_tree(
        self, space_id: str, max_depth: int = 3
    ) -> list:
        """
        获取知识空间的树形结构（便捷方法）

        递归获取知识空间的节点树，方便 AI 了解整体结构。

        Args:
            space_id: 知识空间 ID
            max_depth: 最大递归深度

        Returns:
            树形节点列表，每个节点包含 children 字段

        注意:
            深层级的知识空间可能产生大量 API 调用，请合理设置 max_depth。
        """

        def _build_tree(parent_token: Optional[str], depth: int) -> list:
            if depth >= max_depth:
                return []
            nodes = self.list_nodes(space_id, parent_node_token=parent_token)
            for node in nodes:
                token = node.get("node_token")
                if token and node.get("has_child"):
                    node["children"] = _build_tree(token, depth + 1)
                else:
                    node["children"] = []
            return nodes

        return _build_tree(None, 0)

    def find_node_by_title(
        self, space_id: str, title: str
    ) -> Optional[dict]:
        """
        按标题搜索知识空间节点（便捷方法）

        在一级节点中搜索指定标题的节点。

        Args:
            space_id: 知识空间 ID
            title: 节点标题

        Returns:
            匹配的节点信息，未找到则返回 None
        """
        nodes = self.list_nodes(space_id)
        for node in nodes:
            if node.get("title") == title:
                return node
        return None
