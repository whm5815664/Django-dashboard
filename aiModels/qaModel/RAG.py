# =========================
# 0) 配置与依赖
# =========================
import json
import re
import numpy as np
import requests
from pathlib import Path
from math import ceil

# 检索相关
from sentence_transformers import SentenceTransformer
import faiss
from rank_bm25 import BM25Okapi

# Django相关
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# ========== Ollama 配置==========
OLLAMA_BASE_URL = "http://localhost:11435"
MODEL_NAME = "deepseek-r1:1.5b"

# ========== 向量模型（中文/多语）==========
# 可替换：BAAI/bge-m3 或 moka-ai/m3e-base 等中文更强的模型
EMB_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ========== 数据文件路径 ==========
# 使用 __file__ 获取当前脚本目录，确保路径正确
DATA_PATH = Path(__file__).parent / "agriculture_dat.json"  # JSON: [{instruction,input,output}, ...]

# ========== RAG 参数 ==========
TOP_K = 5              # 每次注入上下文的文档数（融合后取前 K）
ALPHA = 0.6            # 融合权重：1=纯向量，0=纯BM25
MAX_CTX_CHARS = 4000   # 拼接到 prompt 的上下文字符上限

# ========== 门控阈值（命中质量判断）==========
MIN_DOCS = 1                # 至少命中多少条
MIN_BEST_SCORE = 0.60        # 融合分最高分阈值（0~1，按需调整）
MIN_ANY_OUTPUT_CHARS = 2   # 命中中至少有一条 output 的最小长度

# ========== 稳健性增强（可按需开关/调参）==========
USE_CHANNEL_QUOTA = True    # 对两通道分别限额，避免单通道塞满
USE_OVERLAP_FILTER = True   # 词重叠/Jaccard 过滤，防错配
VEC_QUOTA_FRACTION = 0.5    # 向量通道配额比例（余下给 BM25）
MIN_JACCARD = 0.07          # 查询与文档 instruction 的 Jaccard 下限
MIN_COMMON_TOKENS = 2       # 查询与文档 instruction 至少共有多少词

# ========== 纯LLM模式的system指令（当证据不足时启用）==========
SYSTEM_FOR_PLAIN = "你是一名中文助手，回答要准确、简要，在不了解事实时请明确说明。"

# ========== 全局变量 ==========
docs = None
embedder = None
index = None
bm25 = None
rag_initialized = False

# 导入聊天历史记录
from .deepseek_r1_api import chat_history

# 新增：重置RAG状态的辅助函数
def reset_rag_state():
    global docs, embedder, index, bm25, rag_initialized
    docs = None
    embedder = None
    index = None
    bm25 = None
    rag_initialized = False

# =========================
# 工具函数：分词/重叠度
# =========================
def tokenize(s: str):
    # 简单中英混合分词
    return [t for t in re.findall(r"[\w\u4e00-\u9fa5]+", (s or "").lower()) if t.strip()]

def jaccard(a_tokens, b_tokens):
    A, B = set(a_tokens), set(b_tokens)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

# =========================
# 1) 读取 JSON 并构建文档库
# =========================
def load_docs(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    docs = []
    for i, ex in enumerate(raw):
        # 优先使用原 JSON 中的 id 字段（若存在），否则回退为枚举索引 i
        json_id = ex.get("id", i)
        try:
            # 若可转换为整数则转为 int，保持引用展示一致性
            json_id = int(json_id)
        except Exception:
            # 若无法转换则保留原始值（可能为字符串）
            pass
        ins = (ex.get("instruction") or "").strip()
        inp = (ex.get("input") or "").strip()
        out = (ex.get("output") or "").strip()
        text = f"问题：{ins}\n补充：{inp}\n答案：{out}".strip()
        docs.append({
            "id": json_id,
            "instruction": ins,
            "input": inp,
            "output": out,
            "text": text
        })
    return docs

# =========================
# 2) 建立向量索引 + BM25 索引
# =========================
def build_indexes():
    global docs, embedder, index, bm25, rag_initialized
    
    if rag_initialized:
        return True
        
    try:
        # 加载文档
        docs = load_docs(DATA_PATH)
        assert len(docs) > 0, "知识库为空，请检查 agriculture_dat.json。"
        print(f"[INFO] 已载入知识库条目：{len(docs)}")

        # 建立向量索引
        embedder = SentenceTransformer(EMB_MODEL_NAME)
        corpus_texts = [d["text"] for d in docs]
        corpus_instructions = [d["instruction"] for d in docs]

        # 语义向量（对全文 text）
        emb_matrix = embedder.encode(
            corpus_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        dim = emb_matrix.shape[1]
        index = faiss.IndexFlatIP(dim)   # 内积（向量已单位化 ≈ 余弦）
        index.add(emb_matrix)

        # 关键词索引（对全文 text）
        bm25 = BM25Okapi([tokenize(t) for t in corpus_texts])

        print("[INFO] 向量与BM25索引就绪。")
        rag_initialized = True
        return True
        
    except Exception as e:
        print(f"[ERROR] RAG初始化失败: {e}")
        return False

# =========================
# 3) 稳健归一化 + 混合检索
# =========================
def minmax_norm(d: dict):
    """
    稳健归一化：
    - hi==lo==0  → 全部 0（该通道无有效区分度）
    - hi==lo!=0  → 全部 1（都同等强）
    - 其他       → 标准 min-max
    """
    if not d:
        return d
    vals = np.array(list(d.values()), dtype=float)
    lo, hi = float(vals.min()), float(vals.max())
    if abs(hi - lo) < 1e-12:
        if abs(hi) < 1e-12:
            return {k: 0.0 for k in d}
        else:
            return {k: 1.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}

def hybrid_search(query: str, top_k: int = TOP_K, alpha: float = ALPHA):
    # ===== 向量检索 =====
    q_emb = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    # 多取一点候选，便于后续过滤
    vec_take = max(top_k, 10)
    D, I = index.search(q_emb, vec_take)
    # 过滤相似度<=0（单位化向量时 <=0 表示反相关或无关）
    vec_pairs = [(int(i), float(s)) for i, s in zip(I[0], D[0]) if int(i) >= 0 and float(s) > 0.0]
    # 去重保留更高分
    vec_scores = {}
    for i, s in vec_pairs:
        if (i not in vec_scores) or (s > vec_scores[i]):
            vec_scores[i] = s

    # ===== BM25 检索 =====
    bm_scores_list = bm25.get_scores(tokenize(query))
    bm_idx_sorted = np.argsort(bm_scores_list)[::-1]
    bm_scores = {}
    for i in bm_idx_sorted:
        score = float(bm_scores_list[i])
        if score <= 0.0:
            break  # 后面更低，直接停止
        bm_scores[int(i)] = score
        if len(bm_scores) >= max(top_k, 10):
            break

    # 两通道都为空 → 无有效候选
    if not vec_scores and not bm_scores:
        return []

    # ===== 通道配额（可选）=====
    if USE_CHANNEL_QUOTA:
        vec_quota = ceil(top_k * VEC_QUOTA_FRACTION)
        bm_quota = top_k - vec_quota
        # 分别截取各通道前配额
        vec_scores = dict(sorted(vec_scores.items(), key=lambda x: x[1], reverse=True)[:vec_quota])
        bm_scores  = dict(sorted(bm_scores.items(),  key=lambda x: x[1], reverse=True)[:bm_quota])

    # ===== 归一化 =====
    vec_n = minmax_norm(vec_scores)
    bm_n  = minmax_norm(bm_scores)

    # ===== 融合：final = alpha*vec + (1-alpha)*bm =====
    all_ids = set(vec_n) | set(bm_n)
    merged = []
    for i in all_ids:
        s = alpha * vec_n.get(i, 0.0) + (1 - alpha) * bm_n.get(i, 0.0)
        merged.append((i, s))

    # 排序
    merged.sort(key=lambda x: x[1], reverse=True)

    # ===== 词重叠/Jaccard 过滤（可选）=====
    if USE_OVERLAP_FILTER:
        qtok = tokenize(query)
        def overlap_ok(doc_ins: str, min_jacc=MIN_JACCARD, min_common=MIN_COMMON_TOKENS):
            ins_tok = tokenize(doc_ins)
            common = len(set(qtok) & set(ins_tok))
            if common < min_common:
                return False
            return jaccard(qtok, ins_tok) >= min_jacc

        filtered = [(i, s) for (i, s) in merged if overlap_ok(docs[i]["instruction"])]
        if filtered:  # 若全被过滤则退回未过滤结果
            merged = filtered

    # 截断
    top = merged[:top_k]
    return [{"score": s, "doc": docs[i]} for i, s in top]

# =========================
# 4) 构造提示（RAG 模式）
# =========================
def build_prompt(query: str, retrieved, max_ctx_chars: int = MAX_CTX_CHARS):
    ctx_lines = []
    for r in retrieved:
        d = r["doc"]
        ctx = (
            f"[Doc#{d['id']} score={r['score']:.2f}]\n"
            f"指令：{d['instruction']}\n"
            f"补充：{d['input']}\n"
            f"答案：{d['output']}"
        ).strip()
        ctx_lines.append(ctx)

    context_blob = "\n\n---\n\n".join(ctx_lines)
    context_blob = context_blob[:max_ctx_chars]  # 粗控长度

    system_prompt = (
        "你是一名中文检索增强农业问答助手。仅依据\"检索上下文\"简要回答；"
        "若上下文不足以回答，请明确说明，不要编造。"
    )
    user_prompt = (
        f"用户问题：{query}\n\n"
        f"【检索上下文】（来自本地JSON知识库的匹配片段）：\n"
        f"{context_blob}\n\n"
        f"请给出结构化回答"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ]
    return messages

# =========================
# 5) LLM 调用（Ollama /api/chat）
# =========================
def strip_think(text: str) -> str:
    # DeepSeek-R1 可能输出 <think>…</think>
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def ollama_chat(messages,
                model: str = MODEL_NAME,
                temperature: float = 0.7,
                top_p: float = 0.9,
                max_tokens: int = 1024,
                hide_think: bool = True,
                timeout: int = 300):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens
        }
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data.get("message", {}).get("content", "")
    return strip_think(content) if hide_think else content

# =========================
# 6) 命中质量门控（决定是否启用RAG）
# =========================
def is_evidence_sufficient(retrieved,
                           min_docs: int = MIN_DOCS,
                           min_best_score: float = MIN_BEST_SCORE,
                           min_any_output_chars: int = MIN_ANY_OUTPUT_CHARS) -> bool:
    """
    轻量门控逻辑：
    - 至少命中 min_docs 条
    - 最高融合分 >= min_best_score
    - 命中条目中至少有一条 output 长度>= min_any_output_chars
    """
    if not retrieved or len(retrieved) < min_docs:
        return False
    best_score = max(r.get("score", 0.0) for r in retrieved)
    print('命中得分：', best_score)
    if best_score < min_best_score:
        return False
    any_output_ok = any(len((r["doc"].get("output") or "").strip()) >= min_any_output_chars
                        for r in retrieved)
    if not any_output_ok:
        return False
    return True

# =========================
# 7) 一键问答：RAG 或 纯 LLM（不足则提示并回退）
# =========================
def answer_with_rag_or_plain(query: str,
                             k: int = TOP_K,
                             alpha: float = ALPHA,
                             hide_think: bool = True,
                             system_for_plain: str = SYSTEM_FOR_PLAIN):
    """
    优先使用 RAG；如果证据不足，则回退为纯 LLM（不注入任何检索上下文），
    并在答案中明确提示"未在知识库中匹配到相关问题"。
    返回：
      answer: str
      retrieved: List[dict]
      used_rag: bool
      debug: dict
    """
    retrieved = hybrid_search(query, top_k=k, alpha=alpha)
    used_rag = is_evidence_sufficient(retrieved)

    if used_rag:
        messages = build_prompt(query, retrieved)
        answer = ollama_chat(messages, hide_think=hide_think)
    else:
        messages = [
            {"role": "system", "content": system_for_plain},
            {"role": "user",   "content": query}
        ]
        plain_answer = ollama_chat(messages, hide_think=hide_think)
        answer = f"提示：未在知识库中匹配到相关问题，以下为模型直接回答。\n\n{plain_answer}"

    # 调试信息
    if retrieved:
        scores = [float(r["score"]) for r in retrieved]
        debug = {
            "best_score": float(max(scores)),
            "avg_score": float(np.mean(scores)),
            "doc_ids": [int(r["doc"]["id"]) for r in retrieved]
        }
    else:
        debug = {"best_score": 0.0, "avg_score": 0.0, "doc_ids": []}

    return answer, retrieved, used_rag, debug

# =========================
# 8) 为答案增加引用标注（仅在使用RAG时添加）
# =========================
def append_citations(answer: str, retrieved, used_rag: bool = True):
    """
    仅当 used_rag=True 才追加 Doc# 引用；纯 LLM 回答不追加引用。
    """
    if not used_rag or not retrieved:
        return answer
    ids = []
    for r in retrieved:
        i = r["doc"]["id"]
        if i not in ids:
            ids.append(i)
    return answer.strip() + "\n\n参考：" + ", ".join([f"记录{i}" for i in ids])

# =========================
# 9) Django视图函数
# =========================
@csrf_exempt
@require_POST
def initialize_rag_view(request):
    """初始化RAG系统"""
    try:
        # 可选支持force参数：强制重建
        try:
            data = json.loads(request.body or '{}')
        except Exception:
            data = {}
        force = bool(data.get('force'))

        if force:
            reset_rag_state()

        if not rag_initialized:
            success = build_indexes()
            if success:
                return JsonResponse({
                    'success': True,
                    'message': '知识库初始化成功',
                    'doc_count': len(docs) if docs else 0,
                    'reinitialized': bool(force)
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': '知识库初始化失败'
                }, status=500)
        else:
            return JsonResponse({
                'success': True,
                'message': '知识库已初始化',
                'doc_count': len(docs) if docs else 0,
                'reinitialized': False
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'初始化异常: {str(e)}'
        }, status=500)

# 新增：明确的重新初始化接口
@csrf_exempt
@require_POST
def reinitialize_rag_view(request):
    """重新初始化RAG系统：清空内存并重建索引"""
    global chat_history
    
    try:
        # 清空聊天历史记录
        chat_history.clear()
        
        # 重新注入系统提示
        from .deepseek_r1_api import ensure_system_message
        ensure_system_message(chat_history)
        
        # 重置RAG状态
        reset_rag_state()
        success = build_indexes()
        if success:
            return JsonResponse({
                'success': True,
                'message': '知识库重新初始化成功',
                'doc_count': len(docs) if docs else 0
            })
        else:
            return JsonResponse({
                'success': False,
                'error': '知识库重新初始化失败'
            }, status=500)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'重新初始化异常: {str(e)}'
        }, status=500)

@csrf_exempt
@require_POST
def get_answer_rag_view(request):
    """使用RAG系统回答问题"""
    global chat_history
    
    try:
        if not rag_initialized:
            return JsonResponse({
                'error': 'RAG系统未初始化，请先点击知识库增强按钮'
            }, status=400)
            
        data = json.loads(request.body)
        question = data.get('question', '')
        
        if not question:
            return JsonResponse({'error': 'Empty question'}, status=400)
        
        # 添加用户问题到聊天历史
        chat_history.append({"role": "user", "content": question})
        
        # 使用RAG系统回答问题
        answer, retrieved, used_rag, debug = answer_with_rag_or_plain(question)
        
        # 添加引用标注
        if used_rag:
            answer = append_citations(answer, retrieved, used_rag)
        
        # 添加AI回答到聊天历史
        chat_history.append({"role": "assistant", "content": answer})
        
        return JsonResponse({
            'answer': answer,
            'used_rag': used_rag,
            'debug': debug
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'RAG回答异常: {str(e)}'
        }, status=500)

