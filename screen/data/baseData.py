# 数据库操作（增删查改）

from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection

# 数据库结构（models数据结构）
from ..models import *

# 得到省的所有的柑橘基地信息
@require_GET
def get_base_by_province(request):
    province_name = request.GET.get('province_name')
    print('get_basemap:', province_name)
    # SELECT * FROM basemap WHERE province_name = 'value'
    # 使用原生sql查询
    # with connection.cursor() as cursor:
    #     cursor.execute("SELECT * FROM screen_basemap WHERE province = %s", province_name)
    #     columns = [col[0] for col in cursor.description]
    #     data = [
    #         dict(zip(columns, row))
    #         for row in cursor.fetchall()
    #     ]
    #print(data)

    # 使用django定义的models查询
    data = Basemap.objects.filter(province=province_name).values(
        'baseID',
        'baseName',
        'longitude',
        'latitude',
        'province',
        'city'
    ).order_by()
    data = list(data)

    print(data)
    return JsonResponse(data, safe=False)


@require_GET
def get_base_by_baseID(request):
    # 获取请求参数中的baseID
    base_id = request.GET.get('baseID')
    data = Basemap.objects.filter(baseID=base_id).values(
            'baseID',
            'baseName',
            'longitude',
            'latitude',
            'province',
            'city'
    ).order_by().first()
    return JsonResponse(data, safe=False)

# 获取指定省份的柑橘产量历史数据
@require_GET
def get_citrus_production_by_province(request):
    """获取指定省份的柑橘产量历史数据"""
    province_name = request.GET.get('province_name')
    print('get_citrus_production_by_province:', province_name)
    
    # 查询指定省份的所有产量数据，按日期排序
    data = Citrus_production_history_area.objects.filter(area=province_name).values(
        'date',
        'production_volume'
    ).order_by('date')
    
    data = list(data)
    print(f'{province_name}柑橘产量数据:', data)
    return JsonResponse(data, safe=False)


# 获取指定省份的品种总产量数据，按日期排序
    

from django.views.decorators.http import require_GET
from django.utils.dateformat import format as date_format


@require_GET
def get_variety_production_last_months(request):
    """按月份返回指定省份最近N个月（默认3个月）的各品种产量饼图数据。

    返回结构：
    {
      "success": true,
      "months": ["YYYY-MM", ...],   # 按日期升序，最多N个
      "data": {                       # 每月对应的品种分布
         "YYYY-MM": [{"name": 品种, "value": 产量}, ...],
         ...
      }
    }
    """
    province_name = request.GET.get('province_name')
    try:
        months_limit = int(request.GET.get('months', 3))
    except Exception:
        months_limit = 3

    if not province_name:
        return JsonResponse({
            'success': False,
            'error': '缺少参数 province_name'
        }, status=400)

    # 查询该省份所有记录，按日期排序
    qs = Citrus_variety_production_history_area.objects.filter(area=province_name) \
        .values('date', 'variety', 'production_volume') \
        .order_by('date')

    records = list(qs)
    if not records:
        return JsonResponse({'success': True, 'months': [], 'data': {}}, safe=False)

    # 取按日期去重后的最近N个月（以升序返回）
    unique_dates = []
    seen = set()
    for r in records:
        d = r['date']
        if d not in seen:
            seen.add(d)
            unique_dates.append(d)

    # 最近N个月（升序）
    unique_dates = unique_dates[-months_limit:]

    # 组装每月品种分布
    month_key_list = []
    month_to_items = {}
    for d in unique_dates:
        key = date_format(d, 'Y-m')  # YYYY-MM
        month_key_list.append(key)
        month_to_items[key] = []

    # 将对应月份的记录聚合为 [{name, value}]
    date_to_key = {d: date_format(d, 'Y-m') for d in unique_dates}
    for r in records:
        d = r['date']
        if d in date_to_key:
            key = date_to_key[d]
            month_to_items[key].append({
                'name': r['variety'],
                'value': r['production_volume']
            })

    return JsonResponse({
        'success': True,
        'months': month_key_list,
        'data': month_to_items
    }, safe=False)