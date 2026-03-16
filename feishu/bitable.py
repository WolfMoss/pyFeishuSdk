"""
飞书多维表格 (Bitable / Base) API 模块

提供多维表格的数据表管理、字段管理、记录增删改查、视图管理等完整操作。
"""

from typing import Optional, List, Dict, Any

from .client import FeishuClient


class BitableAPI:
    """
    飞书多维表格 API

    示例::

        from feishu import FeishuClient
        from feishu.bitable import BitableAPI

        client = FeishuClient(app_id="xxx", app_secret="xxx")
        bitable = BitableAPI(client)

        # 列出数据表记录
        records = bitable.search_records(
            app_token="bascnXXXX",
            table_id="tblXXXX",
        )
    """

    def __init__(self, client: FeishuClient):
        self.client = client

    def _base_path(self, app_token: str) -> str:
        return f"bitable/v1/apps/{app_token}"

    def _table_path(self, app_token: str, table_id: str) -> str:
        return f"bitable/v1/apps/{app_token}/tables/{table_id}"

    # ──────────────────────────────────────────────
    #  多维表格级操作
    # ──────────────────────────────────────────────

    def get_app_info(self, app_token: str) -> dict:
        """
        获取多维表格元数据

        Args:
            app_token: 多维表格的唯一标识

        Returns:
            多维表格的基本信息
        """
        return self.client.get(self._base_path(app_token))

    # ──────────────────────────────────────────────
    #  数据表管理
    # ──────────────────────────────────────────────

    def list_tables(self, app_token: str) -> list:
        """
        列出多维表格下的所有数据表

        Args:
            app_token: 多维表格标识

        Returns:
            数据表列表
        """
        return self.client.get_all_pages(
            f"{self._base_path(app_token)}/tables",
            items_key="items",
        )

    def create_table(
        self,
        app_token: str,
        name: str,
        fields: Optional[List[dict]] = None,
    ) -> dict:
        """
        创建新的数据表

        Args:
            app_token: 多维表格标识
            name: 数据表名称
            fields: 初始字段定义列表

        Returns:
            新数据表信息
        """
        body: dict = {"table": {"name": name}}
        if fields:
            body["table"]["fields"] = fields
        return self.client.post(
            f"{self._base_path(app_token)}/tables", json_body=body
        )

    # ──────────────────────────────────────────────
    #  字段管理
    # ──────────────────────────────────────────────

    def list_fields(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None,
    ) -> list:
        """
        列出数据表的所有字段

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            view_id: 视图 ID，指定后只返回该视图可见字段

        Returns:
            字段列表
        """
        params = {}
        if view_id:
            params["view_id"] = view_id
        return self.client.get_all_pages(
            f"{self._table_path(app_token, table_id)}/fields",
            params=params,
            items_key="items",
        )

    def create_field(
        self,
        app_token: str,
        table_id: str,
        field_name: str,
        type: int,
        property: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        创建字段

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            field_name: 字段名称
            type: 字段类型
                1=文本, 2=数字, 3=单选, 4=多选, 5=日期,
                7=复选框, 11=人员, 13=电话, 15=超链接,
                17=附件, 18=关联, 19=公式, 20=创建时间,
                21=修改时间, 22=创建人, 23=修改人, 1001=自动编号,
                1002=货币, 1003=进度, 1004=评分, 1005=邮箱, ...
            property: 字段属性（不同类型有不同属性）
            description: 字段描述

        Returns:
            新字段信息
        """
        body: dict = {
            "field_name": field_name,
            "type": type,
        }
        if property:
            body["property"] = property
        if description:
            body["description"] = {"text": description}
        return self.client.post(
            f"{self._table_path(app_token, table_id)}/fields",
            json_body=body,
        )

    def update_field(
        self,
        app_token: str,
        table_id: str,
        field_id: str,
        field_name: Optional[str] = None,
        type: Optional[int] = None,
        property: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        更新字段

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            field_id: 字段 ID
            field_name: 新字段名称
            type: 新字段类型
            property: 新字段属性
            description: 新字段描述

        Returns:
            更新后的字段信息
        """
        body: dict = {}
        if field_name is not None:
            body["field_name"] = field_name
        if type is not None:
            body["type"] = type
        if property is not None:
            body["property"] = property
        if description is not None:
            body["description"] = {"text": description}
        return self.client.put(
            f"{self._table_path(app_token, table_id)}/fields/{field_id}",
            json_body=body,
        )

    def delete_field(
        self, app_token: str, table_id: str, field_id: str
    ) -> dict:
        """
        删除字段

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            field_id: 字段 ID

        Returns:
            删除结果
        """
        return self.client.delete(
            f"{self._table_path(app_token, table_id)}/fields/{field_id}"
        )

    # ──────────────────────────────────────────────
    #  记录管理
    # ──────────────────────────────────────────────

    def search_records(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None,
        filter: Optional[dict] = None,
        sort: Optional[List[dict]] = None,
        field_names: Optional[List[str]] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        automatic_fields: bool = False,
    ) -> dict:
        """
        搜索/查询记录（推荐使用此接口）

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            view_id: 视图 ID
            filter: 筛选条件，格式参考飞书文档
            sort: 排序条件列表
            field_names: 要返回的字段名列表
            page_size: 每页数量，最大 500
            page_token: 分页标记
            automatic_fields: 是否返回自动计算字段

        Returns:
            包含 items (记录列表) 和分页信息的 dict

        过滤条件示例::

            filter = {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "状态",
                        "operator": "is",
                        "value": ["进行中"]
                    }
                ]
            }
        """
        body: dict = {}
        if view_id:
            body["view_id"] = view_id
        if filter:
            body["filter"] = filter
        if sort:
            body["sort"] = sort
        if field_names:
            body["field_names"] = field_names
        if automatic_fields:
            body["automatic_fields"] = automatic_fields

        params: dict = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token

        return self.client.post(
            f"{self._table_path(app_token, table_id)}/records/search",
            json_body=body,
            params=params,
        )

    def search_all_records(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None,
        filter: Optional[dict] = None,
        sort: Optional[List[dict]] = None,
        field_names: Optional[List[str]] = None,
        automatic_fields: bool = False,
    ) -> list:
        """
        搜索所有记录（自动分页）

        Args:
            与 search_records 相同

        Returns:
            所有匹配记录的列表
        """
        all_records = []
        page_token = None

        while True:
            data = self.search_records(
                app_token=app_token,
                table_id=table_id,
                view_id=view_id,
                filter=filter,
                sort=sort,
                field_names=field_names,
                page_size=500,
                page_token=page_token,
                automatic_fields=automatic_fields,
            )
            items = data.get("items", [])
            if items:
                all_records.extend(items)
            if not data.get("has_more", False):
                break
            page_token = data.get("page_token")
            if not page_token:
                break

        return all_records

    def get_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict:
        """
        获取单条记录

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            record_id: 记录 ID

        Returns:
            记录详情
        """
        return self.client.get(
            f"{self._table_path(app_token, table_id)}/records/{record_id}"
        )

    def create_record(
        self,
        app_token: str,
        table_id: str,
        fields: Dict[str, Any],
    ) -> dict:
        """
        新增单条记录

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            fields: 记录字段，key 为字段名，value 为字段值

        Returns:
            新记录信息

        示例::

            bitable.create_record(
                app_token="bascnXXXX",
                table_id="tblXXXX",
                fields={
                    "任务名称": "完成 SDK 开发",
                    "状态": "进行中",
                    "优先级": "高",
                    "截止日期": 1700000000000,  # 毫秒时间戳
                }
            )
        """
        body = {"fields": fields}
        return self.client.post(
            f"{self._table_path(app_token, table_id)}/records",
            json_body=body,
        )

    def batch_create_records(
        self,
        app_token: str,
        table_id: str,
        records: List[Dict[str, Any]],
    ) -> dict:
        """
        批量新增记录（单次最多 500 条）

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            records: 记录列表，每个元素为 {"fields": {字段名: 字段值}}

        Returns:
            新增结果
        """
        body = {"records": records}
        return self.client.post(
            f"{self._table_path(app_token, table_id)}/records/batch_create",
            json_body=body,
        )

    def update_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: Dict[str, Any],
    ) -> dict:
        """
        更新单条记录

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            record_id: 记录 ID
            fields: 要更新的字段

        Returns:
            更新后的记录信息
        """
        body = {"fields": fields}
        return self.client.put(
            f"{self._table_path(app_token, table_id)}/records/{record_id}",
            json_body=body,
        )

    def batch_update_records(
        self,
        app_token: str,
        table_id: str,
        records: List[dict],
    ) -> dict:
        """
        批量更新记录（单次最多 500 条）

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            records: 记录列表，每个元素需包含 record_id 和 fields

        Returns:
            更新结果

        示例::

            bitable.batch_update_records(
                app_token="bascnXXXX",
                table_id="tblXXXX",
                records=[
                    {
                        "record_id": "recXXX1",
                        "fields": {"状态": "已完成"}
                    },
                    {
                        "record_id": "recXXX2",
                        "fields": {"状态": "已完成"}
                    }
                ]
            )
        """
        body = {"records": records}
        return self.client.post(
            f"{self._table_path(app_token, table_id)}/records/batch_update",
            json_body=body,
        )

    def delete_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict:
        """
        删除单条记录

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            record_id: 记录 ID

        Returns:
            删除结果
        """
        return self.client.delete(
            f"{self._table_path(app_token, table_id)}/records/{record_id}"
        )

    def batch_delete_records(
        self,
        app_token: str,
        table_id: str,
        record_ids: List[str],
    ) -> dict:
        """
        批量删除记录（单次最多 500 条）

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            record_ids: 要删除的记录 ID 列表

        Returns:
            删除结果
        """
        body = {"records": record_ids}
        return self.client.post(
            f"{self._table_path(app_token, table_id)}/records/batch_delete",
            json_body=body,
        )

    # ──────────────────────────────────────────────
    #  视图管理
    # ──────────────────────────────────────────────

    def list_views(self, app_token: str, table_id: str) -> list:
        """
        列出数据表的所有视图

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID

        Returns:
            视图列表
        """
        return self.client.get_all_pages(
            f"{self._table_path(app_token, table_id)}/views",
            items_key="items",
        )

    def get_view(
        self, app_token: str, table_id: str, view_id: str
    ) -> dict:
        """
        获取视图详情

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            view_id: 视图 ID

        Returns:
            视图详细信息
        """
        return self.client.get(
            f"{self._table_path(app_token, table_id)}/views/{view_id}"
        )

    # ──────────────────────────────────────────────
    #  高级便捷方法（对 AI Agent 友好）
    # ──────────────────────────────────────────────

    def get_table_schema(
        self, app_token: str, table_id: str
    ) -> Dict[str, Any]:
        """
        获取数据表完整结构信息（便捷方法）

        返回数据表的字段定义和视图信息，方便 AI 了解表结构后操作数据。

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID

        Returns:
            包含 fields 和 views 的字典
        """
        fields = self.list_fields(app_token, table_id)
        views = self.list_views(app_token, table_id)
        return {
            "fields": fields,
            "views": views,
        }

    def upsert_record(
        self,
        app_token: str,
        table_id: str,
        key_field: str,
        key_value: Any,
        fields: Dict[str, Any],
    ) -> dict:
        """
        插入或更新记录（便捷方法）

        根据指定字段查找记录，存在则更新，不存在则创建。

        Args:
            app_token: 多维表格标识
            table_id: 数据表 ID
            key_field: 用于查找的字段名
            key_value: 用于查找的字段值
            fields: 要设置的字段值（包含 key_field）

        Returns:
            操作结果
        """
        # 搜索现有记录
        search_result = self.search_records(
            app_token=app_token,
            table_id=table_id,
            filter={
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": key_field,
                        "operator": "is",
                        "value": [str(key_value)],
                    }
                ],
            },
            page_size=1,
        )

        items = search_result.get("items", [])
        if items:
            # 更新已有记录
            record_id = items[0]["record_id"]
            return self.update_record(app_token, table_id, record_id, fields)
        else:
            # 创建新记录
            fields[key_field] = key_value
            return self.create_record(app_token, table_id, fields)
