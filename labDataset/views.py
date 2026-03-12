from django.shortcuts import render

# 需要导入相关的模块
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core import serializers
import json


from .models import Dataset,Tag



# Create your views here.

# 返回 Vue 的入口页面
def labdataset_spa(request):
    return render(request, "labDataset/index.html")


"""
    接口 记得先在apifox测试
"""
# 获取数据集列表
@require_http_methods(["GET"])
def get_datasets(request):
    response = {}
    try:
        datasets = Dataset.objects.filter()
        response['list'] = json.loads(serializers.serialize("json",datasets))
        response['msg'] = 'success'
        response['error_num'] = 0
    except Exception as e:
        response['msg'] = str(e)
        response['error_num'] = 1
    return JsonResponse(response)


# 统一返回格式
def api_response(data=None, msg="success", error_num=0):
    return JsonResponse({'data': data, 'msg': msg, 'error_num': error_num})

@require_http_methods(["GET"])
def get_datasets(request):
    """获取列表，支持搜索和标签筛选"""
    try:
        tag_name = request.GET.get('tag')
        search_kw = request.GET.get('search')
        
        query = Dataset.objects.all()
        
        if tag_name and tag_name != '全部数据集':
            query = query.filter(tags__name=tag_name)
        if search_kw:
            query = query.filter(name__icontains=search_kw)

        dataset_list = []
        for d in query:
            dataset_list.append({
                "id": d.id,
                "name": d.name,
                "cover": d.cover,
                "creator": d.creator,
                "created_at": d.created_at.strftime('%Y-%m-%d'),
                "file_count": d.file_count,
                "data_format": d.data_format,
                "tags": [t.name for t in d.tags.all()]
            })
        return api_response(dataset_list)
    except Exception as e:
        return api_response(msg=str(e), error_num=1)

@require_http_methods(["GET"])
def get_dataset_detail(request, dataset_id):
    """获取详情页数据"""
    try:
        d = get_object_or_404(Dataset, id=dataset_id)
        # to do:从 FileNode 表递归获取
        file_tree = [
            {"name": "CSV", "is_folder": True, "children": []},
            {"name": "images", "is_folder": True, "children": []}
        ]
        
        detail = {
            "name": d.name,
            "description": d.description,
            "usage": d.usage_instructions,
            "size_display": d.size_display,
            "tags": [t.name for t in d.tags.all()],
            "file_tree": file_tree,
            "created_at": d.created_at.strftime('%Y-%m-%d')
        }
        return api_response(detail)
    except Exception as e:
        return api_response(msg=str(e), error_num=1)

@require_http_methods(["GET"])
def get_tags(request):
    """获取所有标签，用于顶部的 Tab 切换"""
    tags = Tag.objects.values_list('name', flat=True)
    return api_response(list(tags))