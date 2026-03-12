import os
from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.shortcuts import render



# js数据大屏主页
def index(request):
    return render(request, 'screen/index.html')

# 省份地图
def province_map(request, province_name):
    # js 自动数据加载
    js_folder = os.path.join(os.path.dirname(__file__), 'static/js/province')
    js_files = [f for f in os.listdir(js_folder) if f.endswith('.js')]

    # 传递参数
    context = {
        'province_name': province_name,
        'js_files': js_files
    }
    print("province_map:", context)
    return render(request, 'screen/province_map.html', context)


# 数据大屏基地高德地图
def base_map(request, province_name):
    # 传递参数
    context = {
        'province_name': province_name,
    }
    print("province_map:", context)
    return render(request, 'screen/base_map.html', context)


# 基地管理页面
def baseIndex(request):
    return render(request, 'base/baseIndex.html')








