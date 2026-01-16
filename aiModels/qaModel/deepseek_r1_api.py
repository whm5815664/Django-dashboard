# qa_app/deepseek_r1_api.py
import json
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .deepseek_prompt import select_prompts_for_question

chat_history = []

# Ollama API配置
OLLAMA_BASE_URL = "http://localhost:11435"
MODEL_NAME = "deepseek-r1:1.5b"


def ensure_system_message(messages_list):
    """确保首次会话包含固定系统角色设定，仅插入一次。"""
    has_system = any(item.get("role") == "system" for item in messages_list)
    if not has_system:
        system_content = ("""
            你现在的身份是：AIoT农业问答模型；
            开发单位：华中农业大学AIoT实验室；
            模型基础：DeepSeek-R1-AIot；
            任务要求：记住你的身份，根据提示，用中文简要回答问题"""
        )
        getText(messages_list, "system", system_content)
        print('初始化系统信息')
    return messages_list


# 请求模型，并将结果输出
def get_answer(message):
    # 初始化请求体
    headers = {
        'Content-Type': "application/json"
    }
    
    # 构建请求体，适配Ollama API格式
    body = {
        "model": MODEL_NAME,
        "messages": message,
        "stream": False,  # Ollama默认不支持流式输出，设为False
        "think": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2048
        }
    }
    
    try:
        response = requests.post(
            url=f"{OLLAMA_BASE_URL}/api/chat",  # 使用 /api/chat 端点
            json=body,
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            # Ollama返回格式：{"message": {"content": "模型回复内容"}}
            full_response = result.get('message', {}).get('content', '')
            return full_response
        else:
            print(f"API请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return f"模型请求失败，错误码: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return f"网络请求异常: {str(e)}"
    except json.JSONDecodeError as e:
        print(f"JSON解析异常: {e}")
        return "响应解析失败"
    except Exception as e:
        print(f"未知异常: {e}")
        return f"未知错误: {str(e)}"


# 管理对话历史，按序编为列表
def getText(text, role, content):
    jsoncon = {}
    jsoncon["role"] = role
    jsoncon["content"] = content
    text.append(jsoncon)
    return text

# 获取对话中的所有角色的content长度
def getlength(text):
    length = 0
    for content in text:
        temp = content["content"]
        leng = len(temp)
        length += leng
    return length

# 判断长度是否超长，当前限制8K tokens
def checklen(text):
    while (getlength(text) > 11000):
        del text[0]
    return text


@csrf_exempt
def get_answer_view(request):
    global chat_history

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_input = data.get('question', '')
            print('user_input:', user_input)

            if not user_input:
                return JsonResponse({'error': 'Empty question'}, status=400)

            # 确保首次请求包含固定system设定
            ensure_system_message(chat_history)

            # 根据用户输入匹配提示规则，将命中的提示作为 system 消息注入
            matched_prompts = select_prompts_for_question(user_input)
            for p in matched_prompts:
                checklen(getText(chat_history, "system", p))

            # 添加原始用户输入到历史记录
            getText(chat_history, "user", user_input)
            
            # 创建临时消息列表用于发送给模型（包含提示后缀）
            user_input_with_prompt = user_input + "。请简要回答，不要回答与问题无关的内容"
            temp_messages = chat_history.copy()
            # 更新最后一个用户消息为带提示的版本
            temp_messages[-1] = {"role": "user", "content": user_input_with_prompt}
            question = checklen(temp_messages)
            print('question:', question)

            # 获取回答
            response = get_answer(question)

            print('response:', response)
            # 去除思维链内容，只保留最终回答
            # 检查是否包含思维链分隔符
            if '*******************以上为思维链内容，模型回复内容如下********************' in response:
                # 分割内容，只保留最终回复部分
                parts = response.split('*******************以上为思维链内容，模型回复内容如下********************')
                if len(parts) > 1:
                    response = parts[1].strip()
                else:
                    response = parts[0].strip()

            # # 条件性文本替换：需要同时满足自我介绍句式和特定关键词两个条件
            has_self_intro = any(keyword in response for keyword in ["我是", "我的", "我来自", "我由", "我属于", "我代表", "我是由"])
            # 检查是否包含需要替换的特定关键词
            has_target_keywords = any(keyword in response for keyword in ["深度求索（DeepSeek）公司", "深度求索公司", "DeepSeek-R1", "DeepSeek"])
            
            # 只有同时满足两个条件时才进行替换
            if has_self_intro and has_target_keywords:
                response = response.replace("深度求索（DeepSeek）公司", "AIoT实验室")
                response = response.replace("深度求索公司", "AIoT实验室")
                response = response.replace("AI助手", "农业问答模型")
                response = response.replace("智能助手DeepSeek-R1", "农业大模型语音问答系统")
                response = response.replace("DeepSeek-R1", "DeepSeek-R1-AIoT")
                response = response.replace("中国的", "华农的")

            # 将回答添加到对话历史
            getText(chat_history, "assistant", response)

            return JsonResponse({'answer': response})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def get_chat_history_view(request):
    """获取聊天历史记录的API接口"""
    global chat_history
    
    if request.method == 'GET':
        try:
            # 过滤掉system消息，只返回用户和助手的对话
            filtered_history = []
            for message in chat_history:
                if message.get('role') in ['user', 'assistant']:
                    filtered_history.append({
                        'role': message.get('role'),
                        'content': message.get('content')
                    })
            
            return JsonResponse({
                'success': True,
                'history': filtered_history
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def clear_chat_history_view(request):
    """清空聊天历史记录的API接口"""
    global chat_history
    
    if request.method == 'POST':
        try:
            # 清空聊天历史记录
            chat_history.clear()
            
            # 重新注入系统提示
            ensure_system_message(chat_history)
            
            return JsonResponse({
                'success': True,
                'message': '聊天历史记录已清空'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)