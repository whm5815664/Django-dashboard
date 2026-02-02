from django.shortcuts import render


def lab_datasets_index(request):
    """
    实验室数据集管理页面 - Vue 应用入口
    提供 Vue 应用的 HTML 入口页面
    """
    return render(request, 'labDatasets/index.html')


def lab_datasets_catch_all(request, path=''):
    """
    捕获所有路由，用于支持 Vue Router 的 history 模式
    所有未匹配的路由都会返回 Vue 应用的入口页面
    """
    return render(request, 'labDatasets/index.html')

