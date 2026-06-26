import json

from django.shortcuts import render

from aiModels.ollama_config import OPENCODE_MODEL, OPENCODE_MODELS


# 问答系统
def chat_view(request):
    # 导入聊天历史记录
    from aiModels.qaModel.deepseek_r1_api import chat_history
    
    # 将聊天历史记录传递给模板
    context = {
        'chat_history': chat_history
    }
    return render(request, 'qaModel/chat.html', context)


# 图像识别系统
def image_recognition_view(request):
    return render(request, 'diseaseModel/disease_recognition.html')


# 图谱抽取页面
def graph_view(request):
    return render(request, 'graph/graph.html')


# ChatKG 页面（读取并展示 agriculture_dat.json 数据，UI风格与 chat.html 类似）
def chatkg_view(request):
    # 已将原 chatKG 页面替换为知识库编辑页（editKnowledge.html）
    return render(request, 'qaModel/editKnowledge.html')


def _agent_page_context():
    return {
        'opencode_models_json': json.dumps(OPENCODE_MODELS, ensure_ascii=False),
        'opencode_default_model_id': OPENCODE_MODEL.get('modelID', ''),
    }


# 智能体助手弹窗页面
def agent_view(request):
    return render(request, 'agent/agent.html', _agent_page_context())

# 智能体助手单独页面
def agent_view_page(request):
    return render(request, 'agent/agent_view.html', _agent_page_context())


# 模型库入口页面：提供选择并跳转到各模型系统
def model_library_view(request):
    return render(request, 'model_library.html')