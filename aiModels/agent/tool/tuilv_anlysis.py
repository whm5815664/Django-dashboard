import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from aiModels.agent.brain_agent import (
    create_agent_sse_response,
    resolve_model_config,
    send_async_message,
    stream_output,
    _resolve_parent_message_id,
)
from rank_bm25 import BM25Okapi
from aiModels.ollama_config import OPENCODE_BASE_URL
from aiModels.agent.tool.select_data import (
    get_base_env_data,
    get_base_info_data,
    get_recent_records,
    load_base_env_data,
    parse_agent_base_ids,
    parse_agent_days,
    parse_agent_request_json,
)

# 品种褪绿分析：数据就绪状态与当前品种
TUILV_ANALYSIS_READY: bool = False
TUILV_ANALYSIS_VARIETY: Optional[str] = None
TUILV_RAG_CACHE: Optional[Dict[str, Any]] = None

TUILV_ANALYSIS_DAYS = 3
TUILV_DISPLAY_LIMIT = 10
TUILV_RAG_TOP_K = 3

RAG_ALGO_SKILL = "skill"
RAG_ALGO_HYBRID = "hybrid"

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

_DEGREEN_KEYWORDS = ("褪绿", "脱绿", "褪绿环节", "乙烯", "转色", "通风", "温湿度", "采后", "贮藏")

_RAG_WARMUP_STARTED = False
_RAG_WARMUP_LOCK = threading.Lock()

_JSON_RAG_DOCS: Optional[List[Dict[str, Any]]] = None
_JSON_RAG_BM25: Optional[BM25Okapi] = None

_HYBRID_STATUS_STAGES = (
    (0, "正在加载 JSON 知识库…"),
    (1, "正在 BM25 检索…"),
)

SKILL_RAG_SEARCH_PROMPT_TEMPLATE = "本地知识库检索 {user_input} 褪绿方案"

RAG_REASON_PROMPT_TEMPLATE = """你是华中农业大学 AIoT 团队柑橘采后贮藏专家。请针对「{variety}」的褪绿方案，解读下方本地知识库检索结果。

## 检索算法
{algorithm_label}

## 检索查询
{query}

## 检索结果
{rag_section}

## 输出要求
请用中文输出，包含：
1. **检索过程说明**（简要说明检索策略与命中情况）
2. **思维链分析**（逐步分析每条命中条目与目标品种褪绿方案的相关性；若未命中则说明将跳过知识库直接生成）
3. **检索结论**（是否找到可用方案，后续生成应参考哪些要点）

不需要生成完整褪绿方案，仅完成检索解读。"""

PLAN_PROMPT_TEMPLATE = """请作为华中农业大学 AIoT 团队的柑橘采后贮藏专家，为「{variety}」生成**褪绿方案**，以报告格式直接输出，不需要生成文件。

## 知识库检索结论
{rag_section}

## 输出要求
请用中文输出**仅包含褪绿方案**，结构清晰：
1. **乙烯处理**（浓度、处理时长、注意事项）
2. **通风控制**（要点与参数）
3. **温湿度控制**（目标参数与调控要点）

若知识库未命中该品种专用方案，请基于柑橘采后褪绿通用原则给出保守方案，并注明依据。
**不要输出环境调控建议**（该部分单独生成）。"""

ENV_PROMPT_TEMPLATE = """请作为华中农业大学 AIoT 团队的柑橘采后贮藏专家，基于当前基地环境数据，为「{variety}」给出**简短的环境调控建议**，以报告格式直接输出，不需要生成文件。

## 已确定的褪绿方案
{plan_text}

## 基地信息
{base_info_json}

## 近 {days} 天环境检测数据
{env_data_json}

## 输出要求
**仅简要说明**温度、湿度、乙烯(C2H4)等指标应如何变化以配合上述褪绿方案。
不要重复完整褪绿方案内容。"""

EVALUATE_PROMPT_TEMPLATE = """请作为华中农业大学 AIoT 团队的柑橘采后贮藏专家，**仅基于目标品种与用户提供的褪绿方案**（步骤 3.2），评价其可行性，以报告格式直接输出，不需要生成文件。

## 重要说明
**请勿参考或结合任何基地环境数据**，仅从方案本身的专业性、安全性与可操作性进行评价。

## 目标品种
{variety}

## 用户提供的褪绿方案
{user_scheme}

## 输出要求
请用中文输出，结构清晰，包含：
1. **方案可行性总体评价**（可行/部分可行/不可行，并说明理由）
2. **参数合理性分析**（乙烯浓度、通风、温湿度等是否适宜该品种）
3. **风险与改进建议**（安全隐患、操作难点及优化方向）

基于方案本身给出客观、保守的评价。"""


def _rag_query(variety: str) -> str:
    return f"{variety} 柑橘 褪绿环节 褪绿 脱绿 乙烯 转色 通风 温湿度 贮藏 方案"


def _degreen_relevance_bonus(text: str, variety: str) -> float:
    """BM25 得分叠加：优先命中品种 + 褪绿环节相关条目。"""
    blob = (text or "")
    blob_lower = blob.lower()
    variety = (variety or "").strip()
    bonus = 0.0

    if variety and variety in blob:
        bonus += 2.5
    if variety and variety in blob and any(kw in blob for kw in ("褪绿", "脱绿", "褪绿环节")):
        bonus += 2.0

    for kw in _DEGREEN_KEYWORDS:
        if kw in blob:
            bonus += 0.8
    if "褪绿环节" in blob:
        bonus += 1.5

    return bonus


def _tokenize_list(text: str) -> List[str]:
    return [t for t in re.findall(r"[\w\u4e00-\u9fa5]+", (text or "").lower()) if t.strip()]


def _load_json_kb_docs() -> List[Dict[str, Any]]:
    """仅加载 knowledge 目录下 .json 文件（不扫描 txt/pdf 等）。"""
    global _JSON_RAG_DOCS
    if _JSON_RAG_DOCS is not None:
        return _JSON_RAG_DOCS

    docs: List[Dict[str, Any]] = []
    if not _KNOWLEDGE_DIR.is_dir():
        _JSON_RAG_DOCS = docs
        return docs

    for json_path in sorted(_KNOWLEDGE_DIR.rglob("*.json")):
        try:
            with open(json_path, "r", encoding="utf-8") as fp:
                raw = json.load(fp)
        except Exception as exc:
            print(f"[tuilv] 跳过 JSON 文件 {json_path.name}: {exc}")
            continue

        entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        for ex in entries:
            if not isinstance(ex, dict):
                continue
            ins = (ex.get("instruction") or "").strip()
            inp = (ex.get("input") or "").strip()
            out = (ex.get("output") or "").strip()
            if not (ins or inp or out):
                continue
            docs.append(
                {
                    "source": json_path.name,
                    "instruction": ins,
                    "input": inp,
                    "output": out,
                    # 索引文本补充「褪绿环节」，便于 BM25 聚焦采后褪绿相关条目
                    "text": f"褪绿环节 {ins} {inp} {out}".strip(),
                }
            )

    _JSON_RAG_DOCS = docs
    print(f"[tuilv] JSON 知识库已加载：{len(docs)} 条（仅 .json）")
    return docs


def _ensure_json_bm25_index() -> List[Dict[str, Any]]:
    """构建/复用 JSON 知识库 BM25 索引（无向量模型，毫秒级）。"""
    global _JSON_RAG_BM25
    docs = _load_json_kb_docs()
    if docs and _JSON_RAG_BM25 is None:
        _JSON_RAG_BM25 = BM25Okapi([_tokenize_list(d["text"]) for d in docs])
    return docs


def _hybrid_status_message(elapsed_sec: float) -> str:
    message = _HYBRID_STATUS_STAGES[0][1]
    for threshold, text in _HYBRID_STATUS_STAGES:
        if elapsed_sec >= threshold:
            message = text
    return message


def warmup_rag_indexes_async() -> None:
    """步骤1 后后台预热 JSON BM25 索引。"""
    global _RAG_WARMUP_STARTED

    with _RAG_WARMUP_LOCK:
        if _RAG_WARMUP_STARTED:
            return
        _RAG_WARMUP_STARTED = True

    def _build() -> None:
        try:
            _ensure_json_bm25_index()
            print("[tuilv] JSON BM25 索引预热完成")
        except Exception as exc:
            print(f"[tuilv] JSON BM25 索引预热失败: {exc}")

    threading.Thread(target=_build, daemon=True).start()


def _search_rag_hybrid(variety: str) -> Tuple[List[Dict[str, Any]], bool, str]:
    """算法2：仅检索 knowledge 下 JSON 文件的 BM25 RAG（不加载向量模型）。"""
    query = _rag_query(variety)
    try:
        docs = _ensure_json_bm25_index()
        if not docs or _JSON_RAG_BM25 is None:
            return [], False, query

        scores = _JSON_RAG_BM25.get_scores(_tokenize_list(query))
        ranked: List[Tuple[int, float, float]] = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            doc = docs[idx]
            blob = doc.get("text") or ""
            bm25_score = float(score)
            combined = bm25_score + _degreen_relevance_bonus(blob, variety)
            ranked.append((idx, combined, bm25_score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        if not ranked:
            return [], False, query

        max_score = float(ranked[0][1])
        items: List[Dict[str, Any]] = []
        for idx, combined, _bm25 in ranked:
            if len(items) >= TUILV_RAG_TOP_K:
                break
            doc = docs[idx]
            out = (doc.get("output") or "").strip()
            if len(out) < 2:
                continue
            items.append(
                {
                    "score": round(float(combined / max_score), 4),
                    "instruction": doc.get("instruction"),
                    "input": doc.get("input"),
                    "output": doc.get("output"),
                    "source": doc.get("source"),
                }
            )

        found = len(items) >= 1 and items[0]["score"] >= 0.25
        return items, found, query
    except Exception as exc:
        print(f"[tuilv] JSON BM25 检索失败: {exc}")
        return [], False, query


def _parse_skill_rag_items(text: str) -> List[Dict[str, Any]]:
    """从 kb-retriever Skill 回复中解析结构化检索条目。"""
    text = (text or "").strip()
    if not text:
        return []

    raw_json: Optional[str] = None
    block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if block_match:
        raw_json = block_match.group(1)
    else:
        array_match = re.search(r"(\[[\s\S]*\])", text)
        if array_match:
            raw_json = array_match.group(1)

    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                items: List[Dict[str, Any]] = []
                for idx, row in enumerate(parsed[:TUILV_RAG_TOP_K]):
                    if not isinstance(row, dict):
                        continue
                    items.append(
                        {
                            "score": round(float(row.get("score", 0.85 - idx * 0.05)), 4),
                            "instruction": row.get("instruction") or row.get("source") or f"条目 {idx + 1}",
                            "input": row.get("input") or "",
                            "output": row.get("output") or row.get("text") or row.get("summary") or "",
                        }
                    )
                return items
        except json.JSONDecodeError:
            pass

    paragraphs = [
        part.strip()
        for part in re.split(r"\n{2,}", text)
        if part.strip() and len(part.strip()) > 20 and not part.strip().startswith("```")
    ]
    items = []
    for idx, para in enumerate(paragraphs[:TUILV_RAG_TOP_K]):
        items.append(
            {
                "score": round(0.9 - idx * 0.05, 4),
                "instruction": f"Skill 检索片段 {idx + 1}",
                "input": "",
                "output": para[:1200],
            }
        )
    return items


def _algorithm_label(algorithm: str) -> str:
    if algorithm == RAG_ALGO_SKILL:
        return "算法1：OpenCode kb-retriever Skill 检索"
    return "算法2：JSON 知识库 BM25 RAG 检索"


def _store_rag_cache(
    variety: str,
    items: List[Dict[str, Any]],
    found: bool,
    query: str,
    algorithm: str,
    skill_raw_text: str = "",
) -> Dict[str, Any]:
    global TUILV_RAG_CACHE, TUILV_ANALYSIS_VARIETY

    rag_section = _format_rag_section(items, found)
    TUILV_ANALYSIS_VARIETY = variety
    TUILV_RAG_CACHE = {
        "variety": variety,
        "query": query,
        "items": items,
        "found": found,
        "rag_section": rag_section,
        "item_count": len(items),
        "algorithm": algorithm,
        "algorithm_label": _algorithm_label(algorithm),
        "skill_raw_text": skill_raw_text,
    }
    return TUILV_RAG_CACHE


def build_skill_rag_search_prompt(user_input: str) -> str:
    return SKILL_RAG_SEARCH_PROMPT_TEMPLATE.format(user_input=(user_input or "").strip())


def create_tuilv_skill_rag_sse_response(
    session_id: str,
    variety: str,
    model_config: Optional[Dict[str, Any]] = None,
) -> StreamingHttpResponse:
    """算法1：通过 opencode kb-retriever Skill 执行检索（SSE）。"""
    prompt = build_skill_rag_search_prompt(variety)
    query = _rag_query(variety)
    active_model = model_config or resolve_model_config(None)

    send_async_message(prompt, OPENCODE_BASE_URL, session_id, model_config=active_model)
    target_parent_id = _resolve_parent_message_id(session_id)

    def event_stream():
        reasoning_content = ""
        text_content = ""

        for chunk in stream_output(
            OPENCODE_BASE_URL,
            session_id,
            interval=0.5,
            parent_message_id=target_parent_id,
            max_stream_seconds=600.0,
        ):
            if chunk["type"] == "reasoning":
                reasoning_content += chunk["content"]
                yield f"data: {json.dumps({'type': 'reasoning', 'content': chunk['content']}, ensure_ascii=False)}\n\n"

            elif chunk["type"] == "text":
                text_content += chunk["content"]
                yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']}, ensure_ascii=False)}\n\n"

            elif chunk["type"] == "finished":
                if not text_content.strip():
                    if reasoning_content:
                        text_content = reasoning_content
                    else:
                        text_content = "（Skill 检索已完成，但未返回文字内容。）"

                items = _parse_skill_rag_items(text_content)
                found = bool(items)
                cache = _store_rag_cache(
                    variety,
                    items,
                    found,
                    query,
                    RAG_ALGO_SKILL,
                    skill_raw_text=text_content,
                )
                yield f"data: {json.dumps({'type': 'finished', 'reasoning': reasoning_content, 'text': text_content, 'rag_data': cache}, ensure_ascii=False)}\n\n"
                break

            elif chunk["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'error': chunk['content']}, ensure_ascii=False)}\n\n"
                break

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def create_tuilv_hybrid_rag_sse_response(variety: str) -> StreamingHttpResponse:
    """算法2：混合 RAG 检索（SSE 推送进度，避免长时间无响应）。"""
    variety = (variety or "").strip()

    def event_stream():
        start = time.time()
        last_message = ""

        def emit_status(message: str, progress: float) -> str:
            return f"data: {json.dumps({'type': 'status', 'content': message, 'progress': round(progress, 1)}, ensure_ascii=False)}\n\n"

        yield emit_status(_hybrid_status_message(0), 3)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_search_rag_hybrid, variety)
            while not future.done():
                elapsed = time.time() - start
                message = _hybrid_status_message(elapsed)
                progress = min(30.0, 3.0 + elapsed / 2.0)
                if message != last_message or int(elapsed * 2) % 2 == 0:
                    yield emit_status(message, progress)
                    last_message = message
                time.sleep(1.2)

            try:
                items, found, query = future.result()
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"
                return

        yield emit_status("混合检索完成，整理结果…", 31)
        cache = _store_rag_cache(variety, items, found, query, RAG_ALGO_HYBRID)
        payload = {"success": True, **cache}
        yield f"data: {json.dumps({'type': 'finished', 'rag_data': payload}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _format_rag_section(rag_items: List[Dict[str, Any]], found: bool) -> str:
    if not found or not rag_items:
        return "未在本地知识库中找到该品种的专用褪绿方案，请跳过知识库内容，直接基于专业知识生成方案。"

    lines = ["已在本地知识库中检索到以下相关条目："]
    for idx, item in enumerate(rag_items, start=1):
        lines.append(
            f"\n### 条目 {idx}（相关度 {item.get('score', 0)}）\n"
            f"- 问题：{item.get('instruction') or '—'}\n"
            f"- 补充：{item.get('input') or '—'}\n"
            f"- 答案：{item.get('output') or '—'}"
        )
    return "\n".join(lines)


def _env_for_prompt() -> Dict[str, Any]:
    """压缩环境数据供 LLM 使用（最近采样）。"""
    base_info = get_base_info_data() or {}
    env_data = get_base_env_data() or {}
    recent = get_recent_records(base_info, env_data, limit=TUILV_DISPLAY_LIMIT)
    return {
        "days": env_data.get("days", TUILV_ANALYSIS_DAYS),
        "total_record_count": env_data.get("record_count", 0),
        "sample_records": recent,
    }


def reset_tuilv_analysis_state() -> None:
    """重置品种褪绿分析内存状态。"""
    global TUILV_ANALYSIS_READY, TUILV_ANALYSIS_VARIETY, TUILV_RAG_CACHE
    TUILV_ANALYSIS_READY = False
    TUILV_ANALYSIS_VARIETY = None
    TUILV_RAG_CACHE = None


def prepare_tuilv_analysis_data(
    base_ids: List[str],
    days: int = TUILV_ANALYSIS_DAYS,
) -> Dict[str, Any]:
    """步骤1：加载选中基地的 base 信息与近 N 天环境数据。"""
    global TUILV_ANALYSIS_READY

    if not base_ids:
        raise ValueError("请先在主页或大屏勾选至少一个基地")

    result = load_base_env_data(base_ids, days=days, recent_limit=TUILV_DISPLAY_LIMIT)
    display_records = get_recent_records(
        result["base_info"],
        result["env_data"],
        limit=TUILV_DISPLAY_LIMIT,
    )
    chart_records = sorted(
        display_records,
        key=lambda item: item.get("collected_time") or "",
    )

    TUILV_ANALYSIS_READY = True
    warmup_rag_indexes_async()
    return {
        "base_info": result["base_info"],
        "env_data": result["env_data"],
        "recent_records": display_records,
        "chart_records": chart_records,
        "base_count": result["base_count"],
        "record_count": result["record_count"],
        "display_record_count": len(display_records),
        "days": result["days"],
        "display_limit": TUILV_DISPLAY_LIMIT,
    }


def is_tuilv_analysis_ready() -> bool:
    return (
        TUILV_ANALYSIS_READY
        and get_base_info_data() is not None
        and get_base_env_data() is not None
    )


def run_tuilv_rag_search(variety: str, algorithm: str = RAG_ALGO_HYBRID) -> Dict[str, Any]:
    """步骤 3.1.1：执行知识库检索并缓存结果。"""
    variety = (variety or "").strip()
    if not variety:
        raise ValueError("请输入要褪绿的柑橘品种")

    algorithm = (algorithm or RAG_ALGO_HYBRID).strip().lower()
    query = _rag_query(variety)

    if algorithm == RAG_ALGO_SKILL:
        raise ValueError("Skill 检索请使用 mode=rag_search_skill（SSE）")

    rag_items, rag_found, query = _search_rag_hybrid(variety)
    return _store_rag_cache(variety, rag_items, rag_found, query, RAG_ALGO_HYBRID)


def _require_rag_cache(variety: str) -> Dict[str, Any]:
    variety = (variety or "").strip()
    if not TUILV_RAG_CACHE:
        raise ValueError("请先完成步骤 3.1.1 知识库检索")
    if TUILV_RAG_CACHE.get("variety") != variety:
        raise ValueError("品种与检索缓存不一致，请重新发起生成流程")
    return TUILV_RAG_CACHE


def build_tuilv_rag_reason_prompt(variety: str) -> str:
    """步骤 3.1.1：智能体解读检索结果（思维链）。"""
    cache = _require_rag_cache(variety)
    return RAG_REASON_PROMPT_TEMPLATE.format(
        variety=variety,
        algorithm_label=cache.get("algorithm_label") or _algorithm_label(cache.get("algorithm") or RAG_ALGO_HYBRID),
        query=cache.get("query") or _rag_query(variety),
        rag_section=cache.get("rag_section") or "",
    )


def build_tuilv_plan_prompt(variety: str) -> str:
    """步骤 3.1.2：生成褪绿方案。"""
    variety = (variety or "").strip()
    if not variety:
        raise ValueError("请输入要褪绿的柑橘品种")
    cache = _require_rag_cache(variety)

    return PLAN_PROMPT_TEMPLATE.format(
        variety=variety,
        rag_section=cache.get("rag_section") or "",
    )


def build_tuilv_env_prompt(variety: str, plan_text: str) -> str:
    """步骤 3.1.3：生成环境调控建议。"""
    variety = (variety or "").strip()
    plan_text = (plan_text or "").strip()
    if not variety:
        raise ValueError("请输入要褪绿的柑橘品种")
    if not plan_text:
        raise ValueError("缺少步骤 3.1.2 生成的褪绿方案")
    if not is_tuilv_analysis_ready():
        raise ValueError("请先点击「品种褪绿分析」完成基地环境数据加载")

    base_info = get_base_info_data() or {}
    env_summary = _env_for_prompt()

    return ENV_PROMPT_TEMPLATE.format(
        variety=variety,
        plan_text=plan_text,
        base_info_json=json.dumps(base_info, ensure_ascii=False, indent=2),
        env_data_json=json.dumps(env_summary, ensure_ascii=False, indent=2),
        days=env_summary.get("days", TUILV_ANALYSIS_DAYS),
    )


def build_tuilv_evaluate_prompt(variety: str, user_scheme: str) -> str:
    """步骤 3.2：评价用户方案可行性（不结合基地环境数据）。"""
    variety = (variety or "").strip()
    user_scheme = (user_scheme or "").strip()
    if not variety:
        raise ValueError("缺少柑橘品种信息")
    if not user_scheme:
        raise ValueError("请输入您的褪绿方案")

    return EVALUATE_PROMPT_TEMPLATE.format(
        variety=variety,
        user_scheme=user_scheme,
    )


def _run_agent_with_prompt(session_id: str, prompt: str, data: Dict[str, Any]):
    model_config = resolve_model_config(data)
    return create_agent_sse_response(session_id, prompt, model_config=model_config)


# ---------------------------------------------------------------------------
# 工具：品种褪绿分析
# 步骤1：加载基地环境数据并展示（折线图 + 近10条表格）
# 步骤2：（前端）询问褪绿品种
# 步骤3：（前端）问卷 → 无则 3.1.1/3.1.2/3.1.3 分步生成；有则 3.2 评价
# ---------------------------------------------------------------------------

def tuilv_analysis_step1_prepare(
    base_ids: List[str],
    days: int = TUILV_ANALYSIS_DAYS,
) -> Dict[str, Any]:
    """【品种褪绿分析 · 步骤1】加载基地环境数据。"""
    return prepare_tuilv_analysis_data(base_ids, days=days)


@csrf_exempt
@require_POST
def agent_tuilv_analysis_prepare_view(request):
    """【品种褪绿分析 · 步骤1】HTTP 入口。"""
    try:
        reset_tuilv_analysis_state()
        data = parse_agent_request_json(request)
        base_ids, err = parse_agent_base_ids(data, "请先在主页或大屏勾选至少一个基地")
        if err:
            return err

        result = tuilv_analysis_step1_prepare(base_ids, days=parse_agent_days(data))
        return JsonResponse({"success": True, **result})
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def agent_tuilv_analysis_run_view(request):
    """【品种褪绿分析 · 步骤3.1.1/3.1.2/3.1.3/3.2】HTTP 入口（rag_search 返回 JSON，其余 SSE）。"""
    try:
        data = parse_agent_request_json(request)
        session_id = data.get("session_id")
        mode = (data.get("mode") or "rag_reason").strip().lower()
        variety = (data.get("variety") or data.get("message") or "").strip()
        user_scheme = (data.get("user_scheme") or data.get("scheme") or "").strip()
        plan_text = (data.get("plan_text") or "").strip()

        if not variety:
            return JsonResponse({"success": False, "error": "请输入要褪绿的柑橘品种"}, status=400)

        if mode == "rag_search_hybrid":
            return create_tuilv_hybrid_rag_sse_response(variety)

        if mode == "rag_search":
            algorithm = (data.get("rag_algorithm") or data.get("algorithm") or RAG_ALGO_HYBRID).strip().lower()
            cache = run_tuilv_rag_search(variety, algorithm=algorithm)
            return JsonResponse(
                {
                    "success": True,
                    "variety": cache["variety"],
                    "query": cache["query"],
                    "found": cache["found"],
                    "items": cache["items"],
                    "item_count": cache["item_count"],
                    "algorithm": cache.get("algorithm"),
                    "algorithm_label": cache.get("algorithm_label"),
                }
            )

        if mode == "rag_search_skill":
            if not session_id:
                return JsonResponse({"success": False, "error": "缺少 session_id"}, status=400)
            return create_tuilv_skill_rag_sse_response(
                session_id,
                variety,
                model_config=resolve_model_config(data),
            )

        if not session_id:
            return JsonResponse({"success": False, "error": "缺少 session_id"}, status=400)

        if mode == "rag_reason":
            prompt = build_tuilv_rag_reason_prompt(variety)
        elif mode == "plan":
            prompt = build_tuilv_plan_prompt(variety)
        elif mode == "env":
            prompt = build_tuilv_env_prompt(variety, plan_text)
        elif mode == "evaluate":
            prompt = build_tuilv_evaluate_prompt(variety, user_scheme)
        else:
            return JsonResponse({"success": False, "error": f"未知 mode: {mode}"}, status=400)

        return _run_agent_with_prompt(session_id, prompt, data)
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
