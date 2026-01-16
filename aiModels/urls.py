from django.urls import path

from . import views

# 问答功能api
from aiModels.qaModel import spark_api
from aiModels.qaModel import deepseek_r1_api

# 工具功能
from aiModels.diseaseModel import diseaseRecognition

# 图谱抽取功能
from aiModels.graph import graph

# RAG知识库增强功能
from aiModels.qaModel import RAG

# ChatKG 知识库数据接口
from aiModels.qaModel.editJson import get_knowledge_data_view, delete_knowledge_item_view, add_knowledge_item_view

urlpatterns = [
    # 问答系统
    path('chat', views.chat_view, name='chat'),
    path('get_answer', spark_api.get_answer_view, name='get_answer'),
    path('get_answer_deepseek', deepseek_r1_api.get_answer_view, name='get_answer_deepseek'),
    path('get_chat_history', deepseek_r1_api.get_chat_history_view, name='get_chat_history'),
    path('clear_chat_history', deepseek_r1_api.clear_chat_history_view, name='clear_chat_history'),
    
    # RAG知识库增强系统
    path('initialize_rag', RAG.initialize_rag_view, name='initialize_rag'),
    path('get_answer_rag', RAG.get_answer_rag_view, name='get_answer_rag'),
    path('reinitialize_rag', RAG.reinitialize_rag_view, name='reinitialize_rag'),
    
    # ChatKG 页面（嵌入问答系统，为RAG数据来源）
    path('tool/chatkg', views.chatkg_view, name='chatkg'),
    path('knowledge/data', get_knowledge_data_view, name='knowledge_data'),
    path('knowledge/delete', delete_knowledge_item_view, name='knowledge_delete'),
    path('knowledge/add', add_knowledge_item_view, name='knowledge_add'),

    # 图片上传功能与识别测试
    path('tool/upload/', views.image_recognition_view, name='upload'),  # 上传页面
    path('tool/recognize/', diseaseRecognition.recognize_image, name='recognize'),  # 图片识别
    
    # 图谱抽取页面
    path('tool/graph/', views.graph_view, name='graph'),
    path('tool/graph/extract/', graph.extract_api_view, name='graph_extract'),
]

