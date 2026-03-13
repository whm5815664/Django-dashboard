from django.shortcuts import render

# 需要导入相关的模块
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core import serializers
import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Dataset,Tag

import zipfile # 操作zip文件
import os
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_http_methods

# Create your views here.

# ----------------------------
# 删除 Vue SPA入口
# ----------------------------
# 返回 Vue 的入口页面
# def labdataset_spa(request):
#     return render(request, "labDataset/index.html")



# ----------------------------
# 工具函数
# ----------------------------
# Django serializer => 前端友好的dict形式
def _serialize_one(obj):
    raw = json.loads(serializers.serialize("json", [obj]))[0]
    return {"id": raw["pk"], **raw["fields"]}

def _serialize_many(qs):
    raw = json.loads(serializers.serialize("json", qs))
    return [{"id": item["pk"], **item["fields"]} for item in raw]



# ----------------------------
# CSRF
# ----------------------------
# 获取token
# 让浏览器拿到 csrftoken cookie, 且不用手动生成
@ensure_csrf_cookie
@require_http_methods(["GET"])
def csrf(request):
    return JsonResponse({"msg": "ok"})




# ----------------------------
# 页面渲染 views: 匹配渲染html
# ----------------------------
def dataset_list_view(request):
    tag_filter = request.GET.get('tag', 'all')
    datasets = Dataset.objects.all().order_by('-id')
    if tag_filter != 'all':
        datasets = datasets.filter(data_format__icontains=tag_filter)
    tags = Tag.objects.all().order_by('id')
    context = {
        'datasets': datasets,
        'tags': tags,
        'tagOptions': tags,
        'activeTag': tag_filter
    }
    return render(request, 'labDataset/dataset_list.html', context)

def dataset_detail_view(request, id):
    dataset = get_object_or_404(Dataset, pk=id)
    dataset_tags = [{'label': t, 'value': t} for t in dataset.data_format.split(',')] if dataset.data_format else []
    context = {
        'dataset': dataset,
        'dataset_tags': dataset_tags
    }
    return render(request, 'labDataset/dataset_detail.html', context)



# ----------------------------
# 接口 API
# ----------------------------
"""
    REST 标准：同一路径 GET/POST
"""

# 数据集信息
@require_http_methods(["GET", "POST"])
def datasets(request):

    # 获取数据集列表
    if request.method == "GET":
        try:
            qs = Dataset.objects.all().order_by("-id")  # 按照创建时间排序
            return JsonResponse({
                "msg": "success",
                "error_num": 0,
                "count": qs.count(),
                "results": _serialize_many(qs)
            })
        except Exception as e:
            return JsonResponse({
                "msg": str(e),
                "error_num": 1
            }, status=500)
    
    # 创建新数据集
    if request.method == "POST":
        try:
            # 获取并解析数据（不访问body）
            data = request.POST
            # data = json.loads(request.body.decode("utf-8"))

            # 必填字段: 校验
            required_fields = ["name", "description", "creator", "data_format", "storage_url"]
            for f in required_fields:
                if not data.get(f):
                    return JsonResponse({
                        "msg": f"Field `{f}` is required",
                        "error_num": 1
                    }, status=400)

            ds = Dataset.objects.create(
                name=data["name"].strip(),
                description=data["description"].strip(),
                creator=data["creator"].strip(),
                data_format=data["data_format"].strip(),
                storage_url=data["storage_url"].strip(),
            )

            # 先保存ds对象确保id生成
            ds.save()

            # to do:补齐封面图片上传功能
            cover_file = request.FILES.get("cover_file")
            if cover_file:
                cover_filename = f"{ds.id}.jpg"
                cover_path = os.path.join(settings.BASE_DIR, "static/labDataset/resource", cover_filename)
                with open(cover_path, "wb+") as f:
                    for chunk in cover_file.chunks():
                        f.write(chunk)
                ds.cover = cover_filename
                ds.save()



            # to do:补齐文件夹上传功能
            if 'file' not in request.FILES:
                return JsonResponse({ "msg":"No file upload","error_num":1 }, status=400)

            # 获取文件
            files = request.FILES.getlist('file')   # 对应前端字段"file"

            # 生成文件夹
            dataset_folder = os.path.join(settings.MEDIA_ROOT, f"datasets/{ds.id}")
            os.makedirs(dataset_folder, exist_ok=True)

            # 保存文件
            for f in files:
                # f.name 文件名; f.relative_path 文件夹路径
                save_path = os.path.join(dataset_folder, f.name)
                save_dir = os.path.dirname(save_path)
                os.makedirs(save_dir, exist_ok=True)
                with open(save_path, 'wb') as out_file:
                    for chunk in f.chunks():
                        out_file.write(chunk)


            return JsonResponse({
                "msg": "success",
                "error_num": 0,
                "data": _serialize_one(ds)
            })

        except json.JSONDecodeError:
            return JsonResponse({
                "msg": "Invalid JSON",
                "error_num": 1
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "msg": repr(e),
                "error_num": 1
            }, status=500)

# 根据id获取数据集信息
@require_http_methods(["GET"])
def dataset_detail(request, pk):
    try:
        ds = Dataset.objects.get(pk=pk)
        return JsonResponse({
            "msg": "success",
            "error_num": 0,
            "results": _serialize_one(ds)
        })
    except Dataset.DoesNotExist:
        return JsonResponse({
            "msg": f"Dataset {pk} not found",
            "error_num": 1
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "msg": str(e),
            "error_num": 1
        }, status=500)
        
# 数据集标签
@require_http_methods(["GET", "POST"])
def tags(request):
    
    # 获取所有数据集标签
    if request.method == "GET":
        try:
            qs = Tag.objects.all().order_by("id") 
            return JsonResponse({
                "msg": "success",
                "error_num": 0,
                "count": qs.count(),
                "results": _serialize_many(qs)
            })
        except Exception as e:
            return JsonResponse({
                "msg": str(e),
                "error_num": 1
            }, status=500)
        
    # 提交新数据集标签
    if request.method == "POST":
        try:
            # 获取并解析数据
            data = json.loads(request.body.decode("utf-8"))

            # 批量 or 单个
            # {"name": "nir"}
            # {"names": ["nir", "citrus"]}
            names = []
            if isinstance(data, dict) and data.get("name"):
                names = [data["name"]]
            elif isinstance(data, dict) and isinstance(data.get("names"), list):
                names = data["names"]

            cleaned = []
            for n in names:
                s = str(n).strip()
                if s:
                    cleaned.append(s)
            
            if not cleaned:
                return JsonResponse({"msg": "Field `name` or `names` is required", "error_num": 1}, status=400)
            
            created_or_existing = []
            if n in cleaned:
                obj, _ = Tag.objects.get_or_create(name=n)  # 防止重复
                created_or_existing.append(obj)

            return JsonResponse({
                "msg": "success",
                "error_num": 0,
                "results": [_serialize_one(t) for t in created_or_existing]
            }, status=201)
        
        except json.JSONDecodeError:
            return JsonResponse({"msg": "Invalid Json", "error_num": 1}, status=400)

        except Exception as e:
            return JsonResponse({
                "msg": str(e),
                "error_num": 1
            }, status=500)


# 下载数据集文件
# to do：目前暂时定为静态文件存储访问 media/datasets/id/xx + 打包为zip文件
@require_http_methods(["GET"])
def datasetFile(request, pk):    
    try:
        # 获取数据集对象 
        ds = get_object_or_404(Dataset, pk=pk)

        # 获取路径 media/datasets/id/xx
        dataset_folder = os.path.join(settings.MEDIA_ROOT, f"datasets/{pk}")   

        # 验证存在
        if not os.path.exists(dataset_folder):
            return JsonResponse({
                "msg": f"Dataset folder for ID {pk} not found",
                "error_num": 1
            }, status=404)
        
        # 获取文件
        dataset_files = []
        for root, dirs, files in os.walk(dataset_folder):
            for file in files:
                file_path = os.path.join(root, file)
                dataset_files.append(file_path)

        # 设置zip文件路径
        zip_filename = f"dataset_{pk}.zip"
        zip_path = os.path.join(settings.MEDIA_ROOT, zip_filename)

        # 创建zip文件(后面应该删掉media的zip文件)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in dataset_files:
                zipf.write(file, os.path.relpath(file, dataset_folder))

        # 返回zip文件
        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response["Content-Disposition"] = f'attachment; filename={zip_filename}'    # 浏览器:可下载附件
            return response
    
    except Dataset.DoesNotExist:
        return JsonResponse({
            "msg": f"Dataset with ID {pk} not found",
            "error_num": 1
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            "msg": str(e),
            "error_num": 1
        }, status=500)
