from django.shortcuts import render


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
    return render(request, 'qaModel/chatKG.html')

