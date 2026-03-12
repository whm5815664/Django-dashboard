# 数据库操作（增删查改）

from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection

# 数据库结构（models数据结构）
from ..models import *
from ..models import EnvironmentData  


#
# 得到柑橘地区今年产量
def get_citrus_data(request):
    data = list(Citrus.objects.values('area', 'value'))
    print('get_citrus_data:', data)
    return JsonResponse(data, safe=False)


# 得到柑橘产量最大的5个地区+其它总和
def get_citrus_data_max(request):
    data = list(Citrus.objects.values('area', 'value'))
    sorted_data = sorted(data, key=lambda x: x['value'], reverse=True)
    top_area = sorted_data[:5]
    other_area = {'area': '其它', 'value': sum(item['value'] for item in sorted_data[5:])}
    top_area.append(other_area)
    print('get_citrus_data_max:', top_area)
    return JsonResponse(top_area, safe=False)

# 得到柑橘年产量数据
def get_citrus_production_history(request):
    queryset = Citrus_production_history.objects.order_by('year').values('year', 'production_volume')
    data = list(queryset)
    # 计算同比增长量
    for i in range(1, len(data)):
        prev_volume = data[i - 1]['production_volume']
        current_volume = data[i]['production_volume']
        growth = current_volume - prev_volume
        data[i]['growth'] = growth  # 添加增长量字段
    # 第一年没有同比增长数据
    if len(data) > 0:
        data[0]['growth'] = 0
    return JsonResponse(data, safe=False)



#--------------------------------
# 从远程数据库 pig 的 environment_data 表中查询全部环境数据
@require_GET
def get_environment_data(request):
    """
    从远程 MySQL 数据库 pig 中的 environment_data 表查询数据（按基地编号 base_id 过滤）
    用法示例：/api/environment-data/?base_id=HB001
    """

    base_id = request.GET.get("base_id")
    
    if not base_id:
        return JsonResponse({"error": "缺少参数 base_id"}, status=400)
    
    # 提取后三位数字部分并转换为整数（例如 "HB001" → "001" → 1）
    mapped_pigsty_id = int(base_id[-3:])
    
    queryset = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=mapped_pigsty_id)
        .order_by("-collected_time")
        .values(
        "id",
        "CO2",
        "temperature",
        "humidity",
        "collected_time",
        "device_id",
        "pigsty_id",
        "C2H4",
        "C2H5OH",
        "VOC",
        "H2",
        "image",
        )
    )
    data = list(queryset)
    
    # 直接返回原始时间数据，不进行时区转换
    print('get_environment_data:', data[0] if data else 'No data')
    return JsonResponse(data, safe=False)

