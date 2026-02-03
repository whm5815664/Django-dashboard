# 数据库操作（增删查改）

from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import json

# 数据库结构（models数据结构）
from ..models import *

# 得到省的所有的柑橘基地信息
@require_GET
def get_base_by_province(request):
    province_name = request.GET.get('province_name')
    print('get_base:', province_name)
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

    # 使用 models.py 的 Base 原字段名输出（命名与模型一致）
    data = Base.objects.filter(province_name=province_name).values(
        'base_id',
        'base_name',
        'longitude',
        'latitude',
        'province_name',
        'city_name',
        'base_description',
        'base_pic',
    ).order_by()
    data = list(data)

    print(data)
    return JsonResponse(data, safe=False)


@require_GET
def get_base_by_baseID(request):
    # 兼容旧参数 baseID，同时支持新参数 base_id
    base_id = request.GET.get('base_id') or request.GET.get('baseID')
    data = Base.objects.filter(base_id=base_id).values(
        'base_id',
        'base_name',
        'longitude',
        'latitude',
        'province_name',
        'city_name',
        'base_description',
        'base_pic',
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



    # 添加基地
import os

# 省份名称到缩写的映射
PROVINCE_ABBR = {
    '湖北': 'HB', '湖南': 'HN', '广东': 'GD', '广西': 'GX', '河南': 'HA',
    '河北': 'HE', '山东': 'SD', '山西': 'SX', '江苏': 'JS', '浙江': 'ZJ',
    '安徽': 'AH', '福建': 'FJ', '江西': 'JX', '四川': 'SC', '贵州': 'GZ',
    '云南': 'YN', '陕西': 'SN', '甘肃': 'GS', '青海': 'QH', '新疆': 'XJ',
    '西藏': 'XZ', '内蒙古': 'NM', '黑龙江': 'HL', '吉林': 'JL', '辽宁': 'LN',
    '北京': 'BJ', '上海': 'SH', '天津': 'TJ', '重庆': 'CQ', '海南': 'HI',
    '宁夏': 'NX', '台湾': 'TW', '香港': 'HK', '澳门': 'MO'
}

def get_province_abbr(province_name):
    """获取省份缩写，如果找不到则取前两个字符"""
    province_name = province_name.replace('省', '').replace('市', '').replace('自治区', '').replace('特别行政区', '')
    return PROVINCE_ABBR.get(province_name, province_name[:2].upper() if len(province_name) >= 2 else province_name.upper())

@csrf_exempt
@require_POST
def add_base(request):
    """
    添加基地到 base 表（支持图片上传）
    POST /add_base/
    Content-Type: multipart/form-data
    图片自动命名为：省份缩写+编号，例如 HB001.jpg
    """
    try:
        base_id = request.POST.get('base_id', '').strip()
        base_name = request.POST.get('base_name', '').strip()
        longitude = request.POST.get('longitude', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        province_name = request.POST.get('province_name', '').strip()
        city_name = request.POST.get('city_name', '').strip()
        base_description = request.POST.get('base_description', '').strip()
        pic_file = request.FILES.get('base_pic')
        
        # 验证必填字段
        if not all([base_id, base_name, longitude, latitude, province_name, city_name, pic_file]):
            return JsonResponse({'success': False, 'error': '请填写所有必填字段'}, status=400)
        
        # 转换经纬度为浮点数
        try:
            lng, lat = float(longitude), float(latitude)
        except ValueError:
            return JsonResponse({'success': False, 'error': '经纬度格式错误'}, status=400)
        
        # 检查基地编号是否已存在
        if Base.objects.filter(base_id=base_id).exists():
            return JsonResponse({'success': False, 'error': f'基地编号 {base_id} 已存在'}, status=400)
        
        # 处理图片：命名为 省份缩写+编号
        if not pic_file.content_type.startswith('image/'):
            return JsonResponse({'success': False, 'error': '请上传图片文件'}, status=400)
        
        ext = os.path.splitext(pic_file.name)[1] or '.jpg'
        province_abbr = get_province_abbr(province_name)
        pic_filename = f"{province_abbr}{base_id}{ext}"
        
        # 保存图片
        static_dir = os.path.join(settings.BASE_DIR, 'screen', 'static', 'base_pic')
        os.makedirs(static_dir, exist_ok=True)
        pic_path = os.path.join(static_dir, pic_filename)
        with open(pic_path, 'wb+') as f:
            for chunk in pic_file.chunks():
                f.write(chunk)
        
        # 创建基地
        new_base = Base(
            base_id=base_id,
            base_name=base_name,
            longitude=lng,
            latitude=lat,
            province_name=province_name,
            city_name=city_name,
            base_description=base_description,
            base_pic=pic_filename
        )
        new_base.save()
        
        return JsonResponse({
            'success': True,
            'message': '基地添加成功',
            'data': {'base_id': new_base.base_id, 'base_name': new_base.base_name}
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'添加失败：{str(e)}'}, status=500)

    # 删除基地