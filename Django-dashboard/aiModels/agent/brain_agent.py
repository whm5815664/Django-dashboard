import json
import time
from typing import Any, Dict, Optional, Generator

import requests
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from aiModels.ollama_config import OPENCODE_BASE_URL, OPENCODE_MODEL

OPENCODE_BASE_URL = OPENCODE_BASE_URL
model = OPENCODE_MODEL

#model = {'model': 'Big Pickle', 'modelID': 'big-pickle', 'providerID': 'opencode'}
#model = {'model': 'glm-4.7-flash:latest', 'modelID': 'glm-4.7-flash:latest', 'providerID': 'ollama'}
#model = {'model': 'gpt-oss:latest', 'modelID': 'gpt-oss:latest', 'providerID': 'ollama'}

# 列出所有会话
def get_session(base_url: str) -> list:
    r = requests.get(f"{base_url}/session")
    sessions = r.json()
    return [
        {'id': s.get('id'), 'title': s.get('title'), 'directory': s.get('directory')}
        for s in sessions
    ]


# 删除会话
def delete_session(base_url: str, session_id: str) -> Dict[str, Any]:
    r = requests.delete(f"{base_url}/session/{session_id}")
    return r.json()


# 智能体角色设定
AGENT_SYSTEM_PROMPT = """
你是华中农业大学aiot团队开发的智能体，智能体名称为：华中农业大学柑橘智能体
系统的开发者为：WHM
"""
AGENT_SYSTEM_TEMP = r"Django-dashboard\aiModels\agent\temp"


# 创建会话
def creat_session(base_url: str, title: str = "智能体助手") -> Dict[str, Any]:
    r = requests.post(f"{base_url}/session", json={"title": title})
    session = r.json()
    session_id = session.get("id")
    print('agent创建会话id:', session_id)
    
    # 创建会话后立即加载角色设定
    if session_id:
        init_msg = f"""请加载以下角色设定：\n{AGENT_SYSTEM_PROMPT}"""
        send_async_message(init_msg, base_url, session_id, model_config=model, no_reply=True)
    
    return session



# ---------- Django 视图：供 agent.html 调用 ----------

@csrf_exempt
@require_POST
def agent_create_session_view(request):
    """创建 opencode 会话，页面打开时调用。"""
    try:
        data = json.loads(request.body) if request.body else {}
        title = data.get("title", "智能体助手")
        session = creat_session(OPENCODE_BASE_URL, title=title)
        # session_id 取自 opencode 返回的 json['id']
        session_id = session.get("id") if isinstance(session, dict) else None
        if not session_id:
            return JsonResponse({"success": False, "error": "opencode 未返回 session id"})
        return JsonResponse({"success": True, "session_id": session_id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})




@csrf_exempt
@require_POST
def agent_delete_session_view(request):
    """删除 opencode 会话，页面关闭时调用。"""
    try:
        data = json.loads(request.body) or {}
        session_id = data.get("session_id")
        if not session_id:
            return JsonResponse({"success": False, "error": "缺少 session_id"})
        delete_session(OPENCODE_BASE_URL, session_id)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})



# ------新的异步消息方法-------------

def send_async_message(
    message: str,
    base_url: str,
    session_id: str,
    agent: Optional[str] = "general", 
    model_config: Optional[Dict[str, Any]] = model,
    no_reply: bool = False
):
    """异步发送消息到 opencode 会话"""
    data = {
        "parts": [{"type": "text", "text": message}]
    }
    if agent:
        data["agent"] = agent
    if model_config:
        data["model"] = model_config
    if no_reply:
        data["noReply"] = True
    
    r = requests.post(
        f"{base_url}/session/{session_id}/prompt_async",
        json=data,
        timeout=50
    )
    print("消息已发送")
    return r


def stream_output(
    base_url: str,
    session_id: str,
    interval: float = 5.0,
    parent_message_id: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """流式获取输出，返回生成器，每次 yield 一个包含 type 和 content 的字典。

    注意：
    - opencode 会对同一条 assistant message 进行"就地更新"，同一个 part 的 text 会从空字符串逐步补全。
    - 这里使用 part_id -> 已打印字符长度 的映射，每次只输出新增的部分。
    """
    printed_text_lens: Dict[str, int] = {}  # {part_id: 已打印的字符长度}
    printed_tool_ids = set()    
    last_message_id = None

    while True:
        try:
            r = requests.get(
                f"{base_url}/session/{session_id}/message",
                timeout=30
            )
            messages = r.json()
            print('--------------------------------')
            print('messages:', messages[-1])
            print('--------------------------------')

            if not messages:
                time.sleep(interval)
                continue

            # 找最后一条 assistant 消息
            assistant_msg = None
            for msg in reversed(messages):
                if msg.get("info", {}).get("role") == "assistant":
                    assistant_msg = msg
                    break

            if not assistant_msg:
                time.sleep(interval)
                continue

            # 如果指定了要跟踪的 parent_message_id，则只处理与当前问题对应的回复
            if parent_message_id:
                parent_id = assistant_msg.get("info", {}).get("parentID")
                if parent_id != parent_message_id:
                    # 这条 assistant 回复不是当前问题的回答，跳过
                    time.sleep(interval)
                    continue

            message_id = assistant_msg["info"]["id"]

            # 如果进入了一条新的 assistant 消息，清空已打印记录
            if message_id != last_message_id:
                printed_text_lens = {}
                printed_tool_ids = set()
                last_message_id = message_id
                print(f"\n===== assistant message: {message_id} =====", flush=True)

            finished = False

            for part in assistant_msg.get("parts", []):
                part_id = part.get("id")
                part_type = part.get("type")

                if not part_id:
                    continue

                # 只对 reasoning/text 做增量输出
                if part_type in ("reasoning", "text"):
                    current_text = part.get("text", "") or ""
                    old_len = printed_text_lens.get(part_id, 0)

                    # 只打印新增部分
                    if len(current_text) > old_len:
                        delta = current_text[old_len:]

                        # 第一次打印这个 part 时，先打印标签
                        if old_len == 0:
                            if part_type == "reasoning":
                                print(f"\n[reasoning] ", end="", flush=True)
                            else:
                                print(f"\n[text] ", end="", flush=True)

                        print(delta, end="", flush=True)
                        printed_text_lens[part_id] = len(current_text)
                        
                        # yield 给前端
                        yield {"type": part_type, "content": delta}

                #工具调用标识
                elif part_type == "tool":
                    if part_id in printed_tool_ids:
                        continue
                    printed_tool_ids.add(part_id)
                
                    tool_name = part.get("tool")
                    state = part.get("state", {}) or {}
                    status = state.get("status")
                
                    if tool_name == "question" and status in ("running", "pending"):
                        questions = state.get("input", {}).get("questions", []) or []
                
                        text = "我需要先确认以下信息，才能继续：\n"
                        for i, q in enumerate(questions, 1):
                            text += f"\n{i}. {q.get('question', q.get('header', f'问题{i}'))}"
                            options = q.get("options", []) or []
                            if options:
                                text += "\n   可选项：" + " / ".join(
                                    opt.get("label", "") for opt in options
                                )
                
                        print("\n[text] " + text, flush=True)
                        return
                    
                # 结束表示
                elif part_type == "step-finish":
                    finished = True

            if finished:
                print("\n--- 完成 ---", flush=True)
                yield {"type": "finished", "content": ""}
                break

        except Exception as e:
            print("查询失败：", e, flush=True)
            yield {"type": "error", "content": str(e)}
            break

        time.sleep(interval)


@csrf_exempt
@require_POST
def agent_send_message_view(request):
    """发送消息到 opencode 会话，使用流式输出（SSE）"""
    try:
        data = json.loads(request.body) or {}
        session_id = data.get("session_id")
        message = data.get("message", "").strip()
        if not session_id:
            return JsonResponse({"success": False, "error": "缺少 session_id"})
        if not message:
            return JsonResponse({"success": False, "error": "消息不能为空"})
        
        # 发送异步消息
        send_async_message(message, OPENCODE_BASE_URL, session_id, model_config=model)

        # 获取当前这次用户提问对应的 user message id，用于过滤之前的历史回复
        target_parent_id: Optional[str] = None
        try:
            # 简单轮询几次，确保新 user 消息已经写入 session
            for _ in range(5):
                msgs_resp = requests.get(
                    f"{OPENCODE_BASE_URL}/session/{session_id}/message",
                    timeout=10,
                )
                msgs = msgs_resp.json()
                # 从后往前找最近的 user 消息
                for m in reversed(msgs):
                    info = m.get("info", {})
                    if info.get("role") == "user":
                        target_parent_id = info.get("id")
                        break
                if target_parent_id:
                    break
                time.sleep(0.2)
        except Exception as e:
            print("获取当前 user message 失败：", e)

        # 创建 SSE 流式响应
        def event_stream():
            reasoning_content = ""
            text_content = ""
            
            for chunk in stream_output(
                OPENCODE_BASE_URL,
                session_id,
                interval=0.5,
                parent_message_id=target_parent_id,
            ):
                if chunk["type"] == "reasoning":
                    reasoning_content += chunk["content"]
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                
                elif chunk["type"] == "text":
                    text_content += chunk["content"]
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                
                elif chunk["type"] == "finished":
                    yield f"data: {json.dumps({'type': 'finished', 'reasoning': reasoning_content, 'text': text_content}, ensure_ascii=False)}\n\n"
                    break
                
                elif chunk["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'error': chunk['content']}, ensure_ascii=False)}\n\n"
                    break
        
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})