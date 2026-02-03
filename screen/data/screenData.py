# 数据库操作（增删查改）

from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection

# 数据库结构（models数据结构）
from ..models import *


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

# 按省份统计base的数量



