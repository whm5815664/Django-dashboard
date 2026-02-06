"""
aiModels.agent.brain_agent

大脑智能体（决策路由中心）：
- **LLM**：使用 Ollama `/api/chat`
- **智能体路由**：分析用户输入，决定调用哪个子智能体
- **子智能体**：
  - searchDB_agent: 数据库智能体（MySQL操作）
  - spider_agent: 网页爬虫智能体（网络搜索）
- **工具系统**：保留原有工具调用能力

说明：
- 本文件作为核心控制器，负责任务分发和结果整合
- 必须显示调用过程：`print(f"正在调用：{agent_name}智能体")`
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from django.db.models import Model

# 导入子智能体
from aiModels.agent.searchDB_agent import get_search_db_agent
from aiModels.agent.spider_agent import get_spider_agent

# ========== Ollama 配置 ==========
OLLAMA_BASE_URL = "http://localhost:11435"
MODEL_NAME = "deepseek-r1:1.5b"

# ========== 智能体 System Prompt ==========
SYSTEM_FOR_AGENT = """你是一个中文智能体助手（大脑智能体）。你可以调用子智能体来完成任务。

【智能体架构】
你作为大脑智能体，需要分析用户问题，决定调用哪个子智能体：

1. **数据库智能体（searchDB_agent）**：用于数据库查询操作
   - 关键词：查询、数据、数据库、表、模型、基地、设备、产量等
   - 任务类型：
     * auto_query：根据自然语言自动选择模型并查询（推荐使用，只需传入 question 参数）
     * query_model：按模型名和条件查询
     * list_models：列出所有可用模型
     * describe_model：查看模型字段信息

2. **网页爬虫智能体（spider_agent）**：用于网络搜索和网页抓取
   - 关键词：搜索、网页、网络、爬取、抓取、最新信息等
   - 任务类型：search（默认使用百度搜索引擎）, fetch, extract

【调用格式】
你每次只能输出 JSON，且只能二选一：
1) 调用子智能体：
   {"agent": "<智能体名>", "task": "<任务类型>", "args": {...}}
   智能体名：searchDB_agent 或 spider_agent
   对于数据库查询，优先使用 auto_query 任务，args 中传入 {"question": "用户原始问题"}
2) 最终答复：
   {"final": "<给用户的中文答复>"}

【重要流程】
1) 当调用 searchDB_agent 时，它会返回查询结果（包含 success、data、rows 等字段）
2) 你必须仔细阅读查询结果，特别是 data.rows 中的数据
3) 基于查询结果中的实际数据生成最终答案，不要编造数据
4) 如果查询结果为空（count=0），如实告知用户
5) 如果查询失败（success=false），告知用户错误原因

【强约束】
1) 数据必须以智能体返回结果为准，不要编造内容。
2) 如果用户问题需要多个智能体协作，先调用一个，根据结果再决定是否调用另一个。
3) 如果用户问题缺少关键信息，先向用户提问澄清。
4) 生成最终答案时，必须基于查询结果中的实际数据，可以总结、格式化，但不能编造。
"""


# ---------------------- 工具系统 ----------------------

ToolFunc = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: ToolFunc


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, name: str, description: str, func: ToolFunc) -> None:
        self._tools[name] = ToolSpec(name=name, description=description, func=func)

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"未知工具: {name}")
        return self._tools[name]

    def list(self) -> List[Dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]


def _iter_target_models() -> List[type[Model]]:
    """只暴露这两个 app 的模型：storageSystem / screen。"""
    out: List[type[Model]] = []
    for app_label in ("storageSystem", "screen"):
        try:
            out.extend(list(apps.get_app_config(app_label).get_models()))
        except Exception:
            # app 未安装或加载失败
            continue
    return out


def _resolve_model(model: str) -> type[Model]:
    """
    解析模型：支持两种写法
    - "app_label.ModelName" 例如 "screen.Base"
    - "ModelName"（若在目标 apps 中唯一）
    """
    model = (model or "").strip()
    if not model:
        raise ValueError("model 不能为空")

    if "." in model:
        app_label, model_name = model.split(".", 1)
        m = apps.get_model(app_label=app_label, model_name=model_name)
        if m is None:
            raise ValueError(f"找不到模型: {model}")
        if m._meta.app_label not in ("storageSystem", "screen"):
            raise ValueError("仅允许查询 storageSystem / screen 的模型")
        return m

    # 仅 modelName：在目标 apps 内唯一才允许
    candidates = []
    for m in _iter_target_models():
        if m.__name__.lower() == model.lower():
            candidates.append(m)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        raise ValueError(f"找不到模型名: {model}")
    raise ValueError(f"模型名不唯一，请用 app_label.ModelName：{[f'{c._meta.app_label}.{c.__name__}' for c in candidates]}")


def tool_list_models() -> Dict[str, Any]:
    models = _iter_target_models()
    items = []
    for m in models:
        items.append(
            {
                "model": f"{m._meta.app_label}.{m.__name__}",
                "db_table": m._meta.db_table,
                "managed": bool(getattr(m._meta, "managed", True)),
            }
        )
    items.sort(key=lambda x: x["model"])
    return {"count": len(items), "models": items}


def tool_describe_model(model: str) -> Dict[str, Any]:
    M = _resolve_model(model)
    fields = []
    for f in M._meta.get_fields():
        # 过滤反向关系字段，保持简洁
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", True):
            continue
        fields.append(
            {
                "name": getattr(f, "name", ""),
                "type": f.__class__.__name__,
                "is_relation": bool(getattr(f, "is_relation", False)),
                "null": bool(getattr(f, "null", False)) if hasattr(f, "null") else None,
                "blank": bool(getattr(f, "blank", False)) if hasattr(f, "blank") else None,
                "primary_key": bool(getattr(f, "primary_key", False)) if hasattr(f, "primary_key") else None,
            }
        )
    return {"model": f"{M._meta.app_label}.{M.__name__}", "db_table": M._meta.db_table, "fields": fields}


def tool_query_model(
    model: str,
    filters: Optional[Dict[str, Any]] = None,
    values: Optional[List[str]] = None,
    limit: int = 50,
    order_by: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    只读查询：
    - model: "storageSystem.Device" / "screen.Base" 等
    - filters: ORM filter kwargs，例如 {"base_id": "HB001"} 或 {"province_name__icontains": "湖北"}
    - values: 仅返回这些字段；不传则返回所有字段（concrete fields）
    - limit: 默认 50，最大 200
    - order_by: ["-created_at"] / ["base_id"] 等
    """
    M = _resolve_model(model)
    f = filters or {}

    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 50
    limit_i = max(1, min(limit_i, 200))

    qs = M.objects.all()
    if f:
        qs = qs.filter(**f)
    if order_by:
        qs = qs.order_by(*order_by)

    if values:
        qs2 = qs.values(*values)[:limit_i]
        rows = list(qs2)
    else:
        # 默认返回 concrete fields
        concrete = [ff.name for ff in M._meta.fields]
        qs2 = qs.values(*concrete)[:limit_i]
        rows = list(qs2)

    return {
        "model": f"{M._meta.app_label}.{M.__name__}",
        "count": len(rows),
        "limit": limit_i,
        "rows": rows,
    }


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("list_models", "列出可查询的模型（storageSystem 与 screen）", tool_list_models)
    reg.register("describe_model", "查看模型字段信息。参数：model", tool_describe_model)
    reg.register(
        "query_model",
        "按条件查询模型数据（只读）。参数：model, filters?, values?, limit?, order_by?",
        tool_query_model,
    )
    return reg


# ---------------------- Ollama Client ----------------------

class OllamaChatClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = MODEL_NAME, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], options: Optional[Dict[str, Any]] = None) -> str:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options

        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # Ollama 返回结构：{"message": {"role": "...", "content": "..."}, ...}
        return (data.get("message") or {}).get("content") or ""


# ---------------------- 智能体注册表 ----------------------

class AgentRegistry:
    """智能体注册表：管理所有子智能体"""
    
    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}
        self._register_default_agents()
    
    def _register_default_agents(self) -> None:
        """注册默认智能体"""
        self.register("searchDB_agent", "数据库智能体：负责MySQL数据库查询操作", get_search_db_agent())
        self.register("spider_agent", "网页爬虫智能体：负责网络搜索和网页内容抓取", get_spider_agent())
    
    def register(self, name: str, description: str, agent_instance: Any) -> None:
        """注册智能体"""
        self._agents[name] = {
            "name": name,
            "description": description,
            "instance": agent_instance
        }
    
    def get(self, name: str) -> Any:
        """获取智能体实例"""
        if name not in self._agents:
            raise KeyError(f"未知智能体: {name}，可用智能体: {list(self._agents.keys())}")
        return self._agents[name]["instance"]
    
    def list(self) -> List[Dict[str, str]]:
        """列出所有注册的智能体"""
        return [
            {"name": info["name"], "description": info["description"]}
            for info in self._agents.values()
        ]


# ---------------------- 智能体路由分析器 ----------------------

class AgentRouter:
    """智能体路由分析器：分析用户输入，决定调用哪个智能体"""
    
    def __init__(self) -> None:
        # 数据库智能体关键词
        self.db_keywords = [
            '查询', '数据', '数据库', '表', '模型', '基地', '设备', '产量',
            '柑橘', '冷库', '告警', '传感器', '温度', '湿度',
            'list', 'query', 'select', 'find', 'get', 'search database'
        ]
        # 爬虫智能体关键词
        self.spider_keywords = [
            '搜索', '网页', '网络', '爬取', '抓取', '最新', '新闻', '信息',
            '网站', 'url', '链接', '内容', '提取',
            'search', 'fetch', 'crawl', 'scrape', 'web', 'internet'
        ]
    
    def analyze(self, user_input: str) -> Dict[str, Any]:
        """
        分析用户输入，返回推荐的智能体和任务类型
        
        Returns:
            {
                "agent": "searchDB_agent" | "spider_agent" | None,
                "task": "任务类型",
                "confidence": 0.0-1.0
            }
        """
        user_lower = user_input.lower()
        
        # 计算关键词匹配度
        db_score = sum(1 for kw in self.db_keywords if kw.lower() in user_lower)
        spider_score = sum(1 for kw in self.spider_keywords if kw.lower() in user_lower)
        
        # 特殊模式匹配
        if re.search(r'(查询|查找|获取).*?(数据|表|模型|基地|设备)', user_input):
            db_score += 2
        if re.search(r'(搜索|查找|获取).*?(网页|网站|网络|最新)', user_input):
            spider_score += 2
        
        # 决定调用哪个智能体
        if db_score > spider_score and db_score > 0:
            return {
                "agent": "searchDB_agent",
                "task": self._infer_db_task(user_input),
                "confidence": min(db_score / 3.0, 1.0)
            }
        elif spider_score > db_score and spider_score > 0:
            return {
                "agent": "spider_agent",
                "task": self._infer_spider_task(user_input),
                "confidence": min(spider_score / 3.0, 1.0)
            }
        else:
            # 无法确定，返回None让LLM决定
            return {
                "agent": None,
                "task": None,
                "confidence": 0.0
            }
    
    def _infer_db_task(self, user_input: str) -> str:
        """推断数据库任务类型"""
        if re.search(r'(列出|所有|有哪些).*?(模型|表)', user_input):
            return "list_models"
        elif re.search(r'(描述|字段|结构).*?(模型|表)', user_input):
            return "describe_model"
        else:
            # 默认使用 auto_query，让智能体自动选择模型
            return "auto_query"
    
    def _infer_spider_task(self, user_input: str) -> str:
        """推断爬虫任务类型"""
        if re.search(r'(搜索|查找)', user_input):
            return "search"
        elif re.search(r'(提取|抓取|获取).*?(内容|信息)', user_input):
            return "extract"
        else:
            return "fetch"


# ---------------------- 大脑智能体（主控制器） ----------------------

class BrainAgent:
    """
    大脑智能体：核心控制器
    - 分析用户输入意图
    - 维护智能体注册表
    - 路由任务到对应智能体
    - 格式化输出结果
    - 显示调用过程
    """

    def __init__(self, llm: Optional[OllamaChatClient] = None, 
                 agent_registry: Optional[AgentRegistry] = None,
                 router: Optional[AgentRouter] = None) -> None:
        self.llm = llm or OllamaChatClient()
        self.agent_registry = agent_registry or AgentRegistry()
        self.router = router or AgentRouter()
        # 保留工具系统（向后兼容）
        self.tool_registry = build_registry()

    def answer(self, user_question: str, max_steps: int = 6, status_callback: Optional[Callable[[str], None]] = None) -> Tuple[str, Optional[str]]:
        """
        回答用户问题
        
        Args:
            user_question: 用户问题
            max_steps: 最大推理步数
            status_callback: 状态回调函数，在调用智能体时调用
            
        Returns:
            (最终答案字符串, 调用的智能体名称)
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_FOR_AGENT},
            {"role": "user", "content": user_question},
        ]

        # 先尝试路由分析（辅助决策）
        route_hint = self.router.analyze(user_question)
        if route_hint["agent"] and route_hint["confidence"] > 0.5:
            # 高置信度直接调用
            try:
                agent_name = route_hint["agent"]
                task = route_hint["task"]
                print(f"正在调用：{agent_name}智能体")
                
                # 通知调用状态
                if status_callback:
                    status_callback(agent_name)
                
                agent_instance = self.agent_registry.get(agent_name)
                
                # 根据任务类型传递参数
                if task == 'auto_query':
                    result = agent_instance.execute(task, question=user_question)
                elif task in ['query', 'query_model']:
                    result = agent_instance.execute(task, query=user_question)
                else:
                    result = agent_instance.execute(task, query=user_question)
                
                # 打印查询结果（调试用）
                print(f"[{agent_name}] 查询结果：")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                
                # 将结果格式化后返回给LLM生成最终答案
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                messages.append({
                    "role": "assistant",
                    "content": f"已调用{agent_name}（任务：{task}），查询结果：\n{result_str}"
                })
                messages.append({
                    "role": "user",
                    "content": "请仔细阅读上面的查询结果，特别是 data.rows 中的实际数据。基于这些真实数据生成给用户的中文回答。如果查询结果为空，如实告知用户；如果查询失败，说明错误原因。"
                })
                
                final_response = self.llm.chat(messages)
                return (self._extract_final_answer(final_response), agent_name)
            except Exception as e:
                # 如果直接调用失败，回退到LLM路由
                pass

        # LLM路由模式
        called_agent = None
        for step in range(max_steps):
            raw = self.llm.chat(messages)
            raw_str = (raw or "").strip()

            # 尝试解析 JSON
            parsed = _safe_parse_first_json(raw_str)
            if not parsed:
                messages.append({
                    "role": "assistant",
                    "content": "你刚才的输出不是合法 JSON。请严格按要求仅输出 JSON。"
                })
                continue

            if "final" in parsed:
                return (str(parsed["final"]), called_agent)

            # 调用子智能体
            agent_name = parsed.get("agent")
            task = parsed.get("task")
            args = parsed.get("args") or {}
            
            if not agent_name:
                messages.append({
                    "role": "assistant",
                    "content": "缺少 agent 字段。请仅输出 JSON，格式：{\"agent\": \"智能体名\", \"task\": \"任务类型\", \"args\": {...}}"
                })
                continue

            # 执行智能体调用
            try:
                print(f"正在调用：{agent_name}智能体")
                called_agent = agent_name  # 记录调用的智能体
                
                # 通知调用状态
                if status_callback:
                    status_callback(agent_name)
                
                agent_instance = self.agent_registry.get(agent_name)
                
                # 合并参数：将用户问题也传入
                if task == 'auto_query':
                    # auto_query 需要 question 参数
                    if "question" not in args:
                        args["question"] = user_question
                elif "query" not in args and "question" not in args:
                    args["query"] = user_question
                
                result = agent_instance.execute(task, **args)
                
                # 打印查询结果（调试用）
                print(f"[{agent_name}] 查询结果：")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                
                # 将结果加入对话历史
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                messages.append({
                    "role": "assistant",
                    "content": f"已调用{agent_name}（任务：{task}），查询结果：\n{result_str}"
                })
                messages.append({
                    "role": "user",
                    "content": "请仔细阅读上面的查询结果，特别是 data.rows 中的实际数据。基于这些真实数据生成给用户的中文回答。如果查询结果为空，如实告知用户；如果查询失败，说明错误原因。如果信息不足，可以继续调用其他智能体。"
                })
            except KeyError as e:
                result = {"error": f"智能体不存在: {str(e)}"}
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"error": str(result)}, ensure_ascii=False)
                })
            except Exception as e:
                result = {"error": f"智能体执行失败: {type(e).__name__}: {str(e)}"}
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"error": str(result)}, ensure_ascii=False)
                })
                messages.append({
                    "role": "user",
                    "content": "智能体执行失败，请尝试其他智能体或生成最终回答。"
                })

        return ("当前问题需要更多信息或步骤超限。请提供更具体的查询条件或重新表述问题。", called_agent)

    def _extract_final_answer(self, text: str) -> str:
        """从LLM响应中提取最终答案"""
        # 尝试提取JSON中的final字段
        parsed = _safe_parse_first_json(text)
        if parsed and "final" in parsed:
            return str(parsed["final"])
        # 否则返回原始文本
        return text.strip()


# ---------------------- 向后兼容：保留 DBToolAgent ----------------------

class DBToolAgent:
    """
    向后兼容的数据库工具智能体（保留原有接口）
    现在内部使用 BrainAgent
    """
    
    def __init__(self, llm: Optional[OllamaChatClient] = None, registry: Optional[ToolRegistry] = None) -> None:
        self.brain_agent = BrainAgent(llm=llm)
    
    def answer(self, user_question: str, max_steps: int = 4) -> str:
        """使用大脑智能体回答（向后兼容）"""
        answer, _ = self.brain_agent.answer(user_question, max_steps=max_steps)
        return answer


def _safe_parse_first_json(text: str) -> Optional[Dict[str, Any]]:
    """
    从文本中提取并解析第一个 JSON 对象。
    兼容 LLM 输出前后夹杂解释文字的情况。
    """
    if not text:
        return None

    # 先直接尝试
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        return None
    except Exception:
        pass

    # 再尝试提取第一个 {...}
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                try:
                    obj = json.loads(chunk)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    return None
    return None


# ---------------------- Django API（对外问答入口） ----------------------

def _agent_answer_stream(question: str):
    """
    生成器函数：流式返回智能体处理过程
    使用队列和线程来实现实时状态推送
    """
    import queue
    import threading
    
    status_queue = queue.Queue()
    answer_result = [None, None]  # [answer, called_agent]
    error_result = [None]
    
    def status_callback(agent_name: str):
        """状态回调：当调用智能体时推送状态"""
        # 将智能体名称转换为中文显示
        agent_display_name = agent_name
        if agent_name == 'searchDB_agent':
            agent_display_name = '数据库'
        elif agent_name == 'spider_agent':
            agent_display_name = '网页爬虫'
        
        # 将状态放入队列
        status_queue.put({
            "type": "status",
            "agent": agent_name,
            "message": f"正在调用：{agent_display_name}智能体"
        })
    
    def run_agent():
        """在后台线程中运行智能体"""
        try:
            agent = BrainAgent()
            answer, called_agent = agent.answer(question, status_callback=status_callback)
            answer_result[0] = answer
            answer_result[1] = called_agent
            status_queue.put("DONE")  # 标记完成
        except Exception as e:
            error_result[0] = f"{type(e).__name__}: {str(e)}"
            status_queue.put("DONE")
    
    # 启动后台线程
    thread = threading.Thread(target=run_agent)
    thread.daemon = True
    thread.start()
    
    # 流式推送状态
    while True:
        try:
            item = status_queue.get(timeout=0.1)
            if item == "DONE":
                break
            
            # 推送状态更新
            status_data = json.dumps(item, ensure_ascii=False)
            yield f"data: {status_data}\n\n"
        except queue.Empty:
            # 检查线程是否还在运行
            if not thread.is_alive():
                break
            continue
    
    # 等待线程完成
    thread.join(timeout=30)
    
    # 推送最终结果
    if error_result[0]:
        error_data = json.dumps({
            "type": "error",
            "success": False,
            "error": error_result[0]
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"
    else:
        result_data = json.dumps({
            "type": "result",
            "success": True,
            "answer": answer_result[0],
            "called_agent": answer_result[1]
        }, ensure_ascii=False)
        yield f"data: {result_data}\n\n"


@csrf_exempt
@require_POST
def agent_answer_view(request):
    """
    POST /aiModels/brain
    Body: {"question": "..."}
    Return: StreamingHttpResponse (SSE格式)
    
    使用大脑智能体（BrainAgent）处理用户问题，流式返回状态更新
    """
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"success": False, "error": "缺少参数 question"}, status=400)

    # 使用流式响应
    response = StreamingHttpResponse(
        _agent_answer_stream(question),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response