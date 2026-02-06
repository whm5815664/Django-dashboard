"""
aiModels.agent.searchDB_agent

数据库智能体：负责MySQL数据库操作
- 连接和管理MySQL数据库
- 执行SQL查询、插入、更新
- 处理数据库连接异常
- 返回结构化查询结果
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from django.conf import settings
from django.db import connection
from django.apps import apps
from django.db.models import Model


class SearchDBAgent:
    """
    数据库智能体：使用Django ORM和原生SQL操作MySQL数据库
    """

    def __init__(self):
        """初始化数据库智能体"""
        self.db_config = getattr(settings, 'DATABASES', {}).get('default', {})
        self.allowed_apps = ['storageSystem', 'screen', 'aiModels']
        # 缓存表的字段列表，避免重复查询
        self._table_columns_cache: Dict[str, List[str]] = {}
        # 规则：根据自然语言中的关键词，智能匹配模型
        # 可以按需在这里扩展
        self.model_intent_rules: List[Dict[str, Any]] = [
            {
                "model": "storageSystem.Base",
                "keywords": ["基地", "经度", "纬度", "地图", "坐标", "base"],
                "description": "柑橘基地地理信息（用于地图展示）",
            },
            {
                "model": "screen.Base",
                "keywords": ["基地", "经度", "纬度", "地图", "坐标", "base"],
                "description": "柑橘基地地理信息（用于地图展示）",
            },
            {
                "model": "storageSystem.Device",
                "keywords": ["设备", "传感器", "网关", "冷库", "device"],
                "description": "冷库/基地中的物联网设备信息",
            },
            {
                "model": "screen.Citrus_variety_production_history_area",
                "keywords": ["品种", "柑橘品种", "月", "每月", "variety", "品种产量"],
                "description": "各地区按品种和月份统计的产量",
            },
            {
                "model": "storageSystem.Alarm",
                "keywords": ["告警", "报警", "警报", "异常"],
                "description": "设备告警/异常记录",
            },
            {
                "model": "storageSystem.DeviceReading",
                "keywords": ["温度", "湿度", "电量", "采集", "上报", "reading"],
                "description": "设备采集的历史传感数据",
            },
            {
                "model": "screen.Citrus",
                "keywords": ["当年", "当前", "地区", "柑橘", "产量", "citrus"],
                "description": "当前年度各地区柑橘产量",
            },
            {
                "model": "screen.Citrus_production_history",
                "keywords": ["年度", "历史", "年产量", "总产量", "历年"],
                "description": "全国历年柑橘总产量",
            },
            {
                "model": "screen.Citrus_production_history_area",
                "keywords": ["每日", "每天", "日期", "时间序列", "趋势"],
                "description": "各地区每日总产量（时间序列）",
            },
        ]
        
        # 原生表（没有Django Model）的配置
        self.raw_table_rules: List[Dict[str, Any]] = [
            {
                "table": "sensor_readings1",
                "keywords": ["传感器读数", "sensor", "readings", "sensor_readings", "传感器数据"],
                "description": "传感器原始读数数据表",
                "time_column": getattr(settings, "SENSOR_TIME_COL", "collected_at"),
            },
        ]

    def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """
        执行数据库任务
        
        Args:
            task: 任务类型（query, insert, update, list_models, describe_model等）
            **kwargs: 任务参数
            
        Returns:
            Dict包含success, data, error等信息
        """
        try:
            if task == 'query':
                return self._query_data(**kwargs)
            elif task == 'list_models':
                return self._list_models()
            elif task == 'describe_model':
                return self._describe_model(**kwargs)
            elif task == 'query_model':
                return self._query_model(**kwargs)
            elif task == 'raw_sql':
                return self._execute_raw_sql(**kwargs)
            elif task == 'auto_query':
                # 根据自然语言自动选择模型并查询
                return self._auto_query(**kwargs)
            elif task == 'query_table':
                # 查询原生表（如 sensor_readings1）
                return self._query_raw_table(**kwargs)
            else:
                return {
                    'success': False,
                    'error': f'未知任务类型: {task}',
                    'available_tasks': [
                        'query',
                        'list_models',
                        'describe_model',
                        'query_model',
                    'raw_sql',
                    'auto_query',
                    'query_table',
                ]
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}',
                'task': task
            }

    def _list_models(self) -> Dict[str, Any]:
        """列出可用的数据模型"""
        models_list = []
        for app_label in self.allowed_apps:
            try:
                app_config = apps.get_app_config(app_label)
                for model in app_config.get_models():
                    models_list.append({
                        'app': app_label,
                        'model': model.__name__,
                        'table': model._meta.db_table,
                        'full_name': f'{app_label}.{model.__name__}'
                    })
            except Exception as e:
                continue
        
        return {
            'success': True,
            'data': {
                'count': len(models_list),
                'models': models_list
            }
        }

    def _get_table_columns(self, table_name: str) -> List[str]:
        """
        获取数据库表的实际字段列表
        
        Args:
            table_name: 表名
            
        Returns:
            字段名列表
        """
        # 检查缓存
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]
        
        try:
            with connection.cursor() as cursor:
                # 使用 SHOW COLUMNS 获取表的实际字段列表
                cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                columns = cursor.fetchall()
                
                # 提取字段名
                # SHOW COLUMNS 返回格式：(Field, Type, Null, Key, Default, Extra)
                # 使用字典游标更安全，但如果没有，使用索引0
                if columns:
                    # 检查是否是字典格式
                    if isinstance(columns[0], dict):
                        field_names = [col.get("Field", col.get("field", "")) for col in columns]
                    else:
                        # 元组格式，第一个元素是字段名
                        field_names = [col[0] for col in columns]
                    # 过滤空字符串
                    field_names = [f for f in field_names if f]
                else:
                    field_names = []
                
                # 缓存结果
                self._table_columns_cache[table_name] = field_names
                
                print(f"[SearchDBAgent] 表 {table_name} 的实际字段: {field_names}")
                return field_names
        except Exception as e:
            print(f"[SearchDBAgent] 获取表 {table_name} 字段失败: {str(e)}")
            # 如果查询失败，返回空列表
            return []

    def _describe_model(self, model_name: str) -> Dict[str, Any]:
        """描述模型字段信息"""
        try:
            if '.' in model_name:
                app_label, model_class_name = model_name.split('.', 1)
            else:
                # 尝试在所有允许的app中查找
                model_class = None
                for app_label in self.allowed_apps:
                    try:
                        model_class = apps.get_model(app_label, model_name)
                        if model_class:
                            break
                    except:
                        continue
                if not model_class:
                    return {
                        'success': False,
                        'error': f'找不到模型: {model_name}'
                    }
                app_label = model_class._meta.app_label
                model_class_name = model_class.__name__
            
            model_class = apps.get_model(app_label, model_class_name)
            if not model_class:
                return {
                    'success': False,
                    'error': f'找不到模型: {model_name}'
                }

            fields = []
            for field in model_class._meta.get_fields():
                if getattr(field, 'auto_created', False) and not getattr(field, 'concrete', True):
                    continue
                field_info = {
                    'name': getattr(field, 'name', ''),
                    'type': field.__class__.__name__,
                    'is_relation': bool(getattr(field, 'is_relation', False)),
                }
                if hasattr(field, 'null'):
                    field_info['null'] = field.null
                if hasattr(field, 'blank'):
                    field_info['blank'] = field.blank
                if hasattr(field, 'primary_key'):
                    field_info['primary_key'] = field.primary_key
                if hasattr(field, 'max_length'):
                    field_info['max_length'] = field.max_length
                fields.append(field_info)

            return {
                'success': True,
                'data': {
                    'model': f'{app_label}.{model_class_name}',
                    'table': model_class._meta.db_table,
                    'fields': fields
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'描述模型失败: {type(e).__name__}: {str(e)}'
            }

    def _query_model(self, model_name: str, filters: Optional[Dict[str, Any]] = None,
                     values: Optional[List[str]] = None, limit: int = 50,
                     order_by: Optional[List[str]] = None) -> Dict[str, Any]:
        """使用Django ORM查询模型数据"""
        try:
            # 解析模型
            if '.' in model_name:
                app_label, model_class_name = model_name.split('.', 1)
            else:
                model_class = None
                for app_label in self.allowed_apps:
                    try:
                        model_class = apps.get_model(app_label, model_name)
                        if model_class:
                            break
                    except:
                        continue
                if not model_class:
                    return {
                        'success': False,
                        'error': f'找不到模型: {model_name}'
                    }
                app_label = model_class._meta.app_label
                model_class_name = model_class.__name__

            model_class = apps.get_model(app_label, model_class_name)
            if not model_class:
                return {
                    'success': False,
                    'error': f'找不到模型: {model_name}'
                }

            # 构建查询
            queryset = model_class.objects.all()
            
            # 应用过滤条件
            if filters:
                queryset = queryset.filter(**filters)
            
            # 应用排序
            if order_by:
                queryset = queryset.order_by(*order_by)
            
            # 限制数量
            limit = max(1, min(int(limit), 200))
            
            # 获取表的实际字段列表（从数据库查询）
            table_name = model_class._meta.db_table
            actual_columns = self._get_table_columns(table_name)
            actual_columns_set = set(actual_columns) if actual_columns else set()
            
            # 选择字段
            if values:
                # 过滤掉不存在的字段
                valid_values = [v for v in values if v in actual_columns_set] if actual_columns_set else values
                if not valid_values:
                    return {
                        'success': False,
                        'error': f'指定的字段都不存在于表中。表 {table_name} 的可用字段: {actual_columns}'
                    }
                if len(valid_values) < len(values):
                    missing = set(values) - set(valid_values)
                    print(f"[SearchDBAgent] 警告：以下字段不存在于表中，已自动过滤: {missing}")
                
                queryset = queryset.values(*valid_values)[:limit]
                rows = list(queryset)
            else:
                # 返回所有concrete字段，但只包含实际存在的字段
                model_fields = [f.name for f in model_class._meta.fields if not getattr(f, 'is_relation', False)]
                
                # 如果有实际字段列表，只使用存在的字段
                if actual_columns_set:
                    concrete_fields = [f for f in model_fields if f in actual_columns_set]
                    if not concrete_fields:
                        # 如果模型字段都不存在，尝试使用所有实际字段
                        concrete_fields = actual_columns
                        print(f"[SearchDBAgent] 模型字段与表字段不匹配，使用表的所有字段: {concrete_fields}")
                else:
                    # 如果无法获取实际字段列表，使用模型字段（可能失败，但至少尝试）
                    concrete_fields = model_fields
                    print(f"[SearchDBAgent] 无法获取表字段列表，使用模型字段: {concrete_fields}")
                
                queryset = queryset.values(*concrete_fields)[:limit]
                rows = list(queryset)

            return {
                'success': True,
                'data': {
                    'model': f'{app_label}.{model_class_name}',
                    'count': len(rows),
                    'limit': limit,
                    'rows': rows
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'查询失败: {type(e).__name__}: {str(e)}'
            }

    def _query_data(self, sql: Optional[str] = None, model_name: Optional[str] = None,
                   filters: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """通用查询接口"""
        if sql:
            return self._execute_raw_sql(sql=sql, **kwargs)
        elif model_name:
            return self._query_model(model_name=model_name, filters=filters, **kwargs)
        else:
            return {
                'success': False,
                'error': '需要提供sql或model_name参数'
            }

    # ---------- 智能模型选择 ----------

    def _infer_model_from_question(self, question: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """
        根据自然语言问题，智能判断应该使用的模型或原生表。
        返回:
            (model_name 或 None, table_name 或 None, 解释信息字典)
        """
        q = (question or "").strip()
        q_lower = q.lower()
        if not q:
            return None, None, {
                "reason": "问题为空，无法判断模型",
                "matched_keywords": [],
            }

        best_model: Optional[str] = None
        best_table: Optional[str] = None
        best_score = 0
        matched_info: Dict[str, Any] = {}
        is_raw_table = False

        # 先检查原生表
        for rule in self.raw_table_rules:
            table = rule["table"]
            keywords: List[str] = rule.get("keywords", [])
            score = 0
            matched: List[str] = []
            for kw in keywords:
                if kw.lower() in q_lower:
                    score += 1
                    matched.append(kw)
            if score > best_score and matched:
                best_score = score
                best_table = table
                best_model = None
                is_raw_table = True
                matched_info = {
                    "table": table,
                    "description": rule.get("description", ""),
                    "matched_keywords": matched,
                    "score": score,
                    "time_column": rule.get("time_column", "collected_at"),
                }

        # 再检查Django模型
        for rule in self.model_intent_rules:
            model = rule["model"]
            keywords: List[str] = rule.get("keywords", [])
            score = 0
            matched: List[str] = []
            for kw in keywords:
                if kw.lower() in q_lower:
                    score += 1
                    matched.append(kw)
            if score > best_score and matched:
                best_score = score
                best_model = model
                best_table = None
                is_raw_table = False
                matched_info = {
                    "model": model,
                    "description": rule.get("description", ""),
                    "matched_keywords": matched,
                    "score": score,
                }

        if best_model is None and best_table is None:
            return None, None, {
                "reason": "未匹配到合适的模型或表，请提供更具体的问题（例如包含：基地/设备/告警/产量/品种/传感器 等关键词）",
                "matched_keywords": [],
            }

        return best_model, best_table, matched_info

    def _auto_query(
        self,
        question: Optional[str] = None,
        limit: int = 50,
        values: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        根据自然语言问题自动选择模型或原生表并查询。

        参数:
            question: 用户自然语言问题
            limit: 返回条数上限（默认 50）
            values: 需要返回的字段列表（可选）
        """
        print(f"[SearchDBAgent] 开始自动查询，问题：{question}")
        
        model_name, table_name, info = self._infer_model_from_question(question or "")
        
        if not model_name and not table_name:
            print(f"[SearchDBAgent] 未匹配到模型或表，原因：{info.get('reason')}")
            return {
                "success": False,
                "error": info.get("reason", "无法根据问题判断模型或表"),
                "meta": {
                    "question": question,
                    "matched_keywords": info.get("matched_keywords", []),
                },
            }

        # 如果是原生表，使用原生SQL查询
        if table_name:
            print(f"[SearchDBAgent] 匹配到原生表：{table_name}，意图：{info.get('description')}")
            query_res = self._query_raw_table(
                table_name=table_name,
                limit=limit,
                columns=values,
            )
        else:
            print(f"[SearchDBAgent] 匹配到模型：{model_name}，意图：{info.get('description')}")
            # 使用Django ORM查询
            query_res = self._query_model(
                model_name=model_name,
                filters=None,
                values=values,
                limit=limit,
                order_by=None,
            )

        # 打印查询结果
        if query_res.get("success", False):
            data = query_res.get("data", {})
            count = data.get("count", 0)
            print(f"[SearchDBAgent] 查询成功，返回 {count} 条记录")
            if count > 0:
                print(f"[SearchDBAgent] 前3条数据示例：{json.dumps(data.get('rows', [])[:3], ensure_ascii=False)}")
        else:
            print(f"[SearchDBAgent] 查询失败：{query_res.get('error')}")

        # 包装结果，附带推理信息
        if not query_res.get("success", False):
            return query_res

        data = query_res.get("data", {})
        result = {
            "success": True,
            "data": {
                "question": question,
                "intent": info.get("description", ""),
                "matched_keywords": info.get("matched_keywords", []),
                "limit": data.get("limit", limit),
                "count": data.get("count", 0),
                "rows": data.get("rows", []),
            },
        }
        
        if model_name:
            result["data"]["model"] = data.get("model", model_name)
        if table_name:
            result["data"]["table"] = table_name
            
        return result

    def _query_raw_table(
        self,
        table_name: str,
        limit: int = 50,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询原生表（没有Django Model的表，如 sensor_readings1）
        
        参数:
            table_name: 表名
            limit: 返回条数上限
            columns: 需要返回的列（可选，不传则返回所有列）
            filters: 过滤条件（简单等值匹配）
            order_by: 排序字段（可选，如 "collected_at DESC"）
        """
        try:
            # 安全检查：表名白名单
            allowed_tables = [rule["table"] for rule in self.raw_table_rules]
            if table_name not in allowed_tables:
                return {
                    "success": False,
                    "error": f"不允许查询表：{table_name}，允许的表：{allowed_tables}",
                }
            
            # 获取表的实际字段列表
            actual_columns = self._get_table_columns(table_name)
            actual_columns_set = set(actual_columns) if actual_columns else set()
            
            # 构建SELECT语句
            if columns:
                # 过滤掉不存在的字段
                if actual_columns_set:
                    valid_columns = [col for col in columns if col in actual_columns_set]
                    if not valid_columns:
                        return {
                            "success": False,
                            "error": f"指定的字段都不存在于表中。表 {table_name} 的可用字段: {actual_columns}"
                        }
                    if len(valid_columns) < len(columns):
                        missing = set(columns) - set(valid_columns)
                        print(f"[SearchDBAgent] 警告：以下字段不存在于表中，已自动过滤: {missing}")
                    columns = valid_columns
                
                # 安全检查：防止SQL注入
                safe_columns = [f"`{col}`" for col in columns if col.replace("_", "").replace(".", "").isalnum()]
                select_clause = ", ".join(safe_columns)
            else:
                # 如果没有指定列，使用所有实际存在的列
                if actual_columns:
                    safe_columns = [f"`{col}`" for col in actual_columns]
                    select_clause = ", ".join(safe_columns)
                else:
                    # 如果无法获取字段列表，使用 *（可能失败）
                    select_clause = "*"
                    print(f"[SearchDBAgent] 警告：无法获取表 {table_name} 的字段列表，使用 * 查询")
            
            sql = f"SELECT {select_clause} FROM `{table_name}`"
            params_list: List[Any] = []
            
            # 添加WHERE条件
            if filters:
                where_parts = []
                for key, value in filters.items():
                    # 安全检查：字段名只允许字母数字和下划线
                    if key.replace("_", "").isalnum():
                        where_parts.append(f"`{key}` = %s")
                        params_list.append(value)
                if where_parts:
                    sql += " WHERE " + " AND ".join(where_parts)
            
            # 添加ORDER BY
            if order_by:
                # 简单安全检查
                order_by_safe = order_by.replace(";", "").replace("--", "")
                sql += f" ORDER BY {order_by_safe}"
            
            # 添加LIMIT
            limit = max(1, min(int(limit), 200))
            sql += f" LIMIT {limit}"
            
            print(f"[SearchDBAgent] 执行原生SQL查询：{sql}")
            
            # 执行查询
            with connection.cursor() as cursor:
                cursor.execute(sql, params_list)
                
                # 获取列名
                columns_list = [col[0] for col in cursor.description] if cursor.description else []
                
                # 获取数据
                rows = cursor.fetchall()
                
                # 转换为字典列表
                result = []
                for row in rows:
                    result.append(dict(zip(columns_list, row)))
            
            return {
                "success": True,
                "data": {
                    "table": table_name,
                    "count": len(result),
                    "limit": limit,
                    "columns": columns_list,
                    "rows": result,
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"查询原生表失败: {type(e).__name__}: {str(e)}",
            }

    def _execute_raw_sql(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行原生SQL查询（只读，安全限制）
        
        注意：为安全起见，只允许SELECT查询
        """
        try:
            # 安全检查：只允许SELECT语句
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith('SELECT'):
                return {
                    'success': False,
                    'error': '为安全起见，只允许执行SELECT查询语句'
                }

            with connection.cursor() as cursor:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                # 获取列名
                columns = [col[0] for col in cursor.description] if cursor.description else []
                
                # 获取数据
                rows = cursor.fetchall()
                
                # 转换为字典列表
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))

            return {
                'success': True,
                'data': {
                    'count': len(result),
                    'columns': columns,
                    'rows': result
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'SQL执行失败: {type(e).__name__}: {str(e)}'
            }


# 创建全局实例
_search_db_agent = None


def get_search_db_agent() -> SearchDBAgent:
    """获取数据库智能体单例"""
    global _search_db_agent
    if _search_db_agent is None:
        _search_db_agent = SearchDBAgent()
    return _search_db_agent
