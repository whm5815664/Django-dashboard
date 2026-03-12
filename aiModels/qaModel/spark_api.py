# qa_app/spark_api.py
import json
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

chat_history = []

api_key = "Bearer oKTbwLWlRaDSvqmaqDix:OWDoeINPFIKYdNYILHep"
# 接口地址：请根据实际部署/环境变量调整
url = "https://spark-api-open.xf-yun.com/v2/chat/completions"

# 请求模型，并将结果输出
def get_answer(message):
    #初始化请求体
    headers = {
        'Authorization': api_key,
        'content-type': "application/json"
    }
    body = {
        "model": "x1",
        "user": "user_id",
        "messages": message,
        # 下面是可选参数
        "stream": True,
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "enable": True,
                    "search_mode":"deep"
                }
            }
        ]
    }
    full_response = ""  # 存储返回结果
    isFirstContent = True  # 首帧标识

    response = requests.post(url=url,json= body,headers= headers,stream= True)

    # print(response)
    for chunks in response.iter_lines():
        # 打印返回的每帧内容
        #print('chunks:', chunks)
        if (chunks and '[DONE]' not in str(chunks)):
            data_org = chunks[6:]

            chunk = json.loads(data_org)
            text = chunk['choices'][0]['delta']
            # 判断思维链状态并输出
            if ('reasoning_content' in text and '' != text['reasoning_content']):
                reasoning_content = text["reasoning_content"]
                print(reasoning_content, end="")
            # 判断最终结果状态并输出
            if ('content' in text and '' != text['content']):
                content = text["content"]
                if (True == isFirstContent):
                    print("\n*******************以上为思维链内容，模型回复内容如下********************\n")
                    isFirstContent = False
                print(content, end="")
                full_response += content
    return full_response


# 管理对话历史，按序编为列表
def getText(text,role, content):
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

            # 更新对话历史
            question = checklen(getText(chat_history, "user", user_input))

            # 获取回答
            response = get_answer(question)

            # 将回答添加到对话历史
            getText(chat_history, "assistant", response)

            return JsonResponse({'answer': response})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)