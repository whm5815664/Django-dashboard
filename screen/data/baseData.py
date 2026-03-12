# 数据库操作（增删查改）

from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.core.paginator import Paginator
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

@require_GET
def generate_base_id(request):
    """
    自动生成下一个可用的基地编号
    GET /generate_base_id/?province_name=湖北
    返回: {"base_id": "HB001"} 格式：省份缩写+3位数字序号
    """
    try:
        province_name = request.GET.get('province_name', '').strip()
        if not province_name:
            return JsonResponse({'success': False, 'error': '缺少参数 province_name'}, status=400)
        
        province_abbr = get_province_abbr(province_name)
        
        # 查找该省份下已有的基地编号，找出最大序号
        existing_bases = Base.objects.filter(
            base_id__startswith=province_abbr
        ).values_list('base_id', flat=True)
        
        max_num = 0
        for base_id in existing_bases:
            # 提取编号部分（省份缩写后的数字部分）
            if len(base_id) > len(province_abbr):
                try:
                    num_part = base_id[len(province_abbr):]
                    num = int(num_part)
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
        
        # 生成下一个编号（3位数字，从001开始）
        next_num = max_num + 1
        new_base_id = f"{province_abbr}{next_num:03d}"
        
        return JsonResponse({
            'success': True,
            'base_id': new_base_id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'生成编号失败：{str(e)}'}, status=500)

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
        
        # 处理图片：命名为与基地编号一致
        if not pic_file.content_type.startswith('image/'):
            return JsonResponse({'success': False, 'error': '请上传图片文件'}, status=400)
        
        ext = os.path.splitext(pic_file.name)[1] or '.jpg'
        # 图片命名与基地编号一致（基地编号已包含省份缩写）
        pic_filename = f"{base_id}{ext}"
        
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
@csrf_exempt
@require_POST
def delete_base(request):
    """
    删除基地及其所有关联数据
    POST /delete_base/
    Content-Type: application/json 或 application/x-www-form-urlencoded
    参数: base_id
    删除所有包含该 base_id 的数据（包括 Base 表和 Device 表等）
    """
    try:
        # 兼容 JSON 和 form-data 两种格式
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            base_id = data.get('base_id', '').strip()
        else:
            base_id = request.POST.get('base_id', '').strip()
        
        if not base_id:
            return JsonResponse({'success': False, 'error': '缺少参数 base_id'}, status=400)
        
        # 检查基地是否存在
        base_obj = Base.objects.filter(base_id=base_id).first()
        if not base_obj:
            return JsonResponse({'success': False, 'error': f'基地编号 {base_id} 不存在'}, status=404)
        
        # 保存预览图文件名（删除 Base 后无法访问）
        base_pic_filename = base_obj.base_pic if base_obj.base_pic else None
        
        # 导入 Device 模型（从 storageSystem.models）
        try:
            from storageSystem.models import Device, DeviceReading
            DeviceAvailable = True
        except ImportError:
            # 如果导入失败，使用原生 SQL
            Device = None
            DeviceReading = None
            DeviceAvailable = False
        
        deleted_tables = []
        deleted_counts = {}
        
        # 1. 删除 DeviceReading 表中关联的数据（如果存在 base_id 字段或通过 device 关联）
        if DeviceAvailable and DeviceReading:
            try:
                # 先找到所有关联的设备
                devices = Device.objects.filter(base_id=base_id)
                device_codes = [d.code for d in devices]
                
                # 如果 DeviceReading 有 device 外键，删除相关记录
                if device_codes:
                    count = DeviceReading.objects.filter(device__code__in=device_codes).delete()[0]
                    if count > 0:
                        deleted_tables.append('device_reading')
                        deleted_counts['device_reading'] = count
            except Exception as e:
                print(f'删除 DeviceReading 数据时出错（可能表不存在）: {e}')
        
        # 2. 删除 Device 表中关联的数据
        if DeviceAvailable and Device:
            try:
                count = Device.objects.filter(base_id=base_id).delete()[0]
                if count > 0:
                    deleted_tables.append('device')
                    deleted_counts['device'] = count
            except Exception as e:
                print(f'删除 Device 数据时出错: {e}')
        else:
            # 使用原生 SQL 删除 device 表数据
            try:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM device WHERE base_id = %s", [base_id])
                    count = cursor.rowcount
                    if count > 0:
                        deleted_tables.append('device')
                        deleted_counts['device'] = count
            except Exception as e:
                print(f'使用 SQL 删除 Device 数据时出错（可能表不存在）: {e}')
        
        # 3. 删除 Base 表中的数据
        base_obj.delete()
        deleted_tables.append('base')
        deleted_counts['base'] = 1
        
        # 4. 删除预览图文件（如果存在）
        if base_pic_filename:
            try:
                import os
                pic_path = os.path.join(settings.BASE_DIR, 'screen', 'static', 'base_pic', base_pic_filename)
                if os.path.exists(pic_path):
                    os.remove(pic_path)
                    deleted_tables.append('base_pic_file')
                    deleted_counts['base_pic_file'] = 1
            except Exception as e:
                print(f'删除预览图文件时出错: {e}')
        
        return JsonResponse({
            'success': True,
            'message': f'基地 {base_id} 及其关联数据删除成功',
            'deleted_tables': deleted_tables,
            'deleted_counts': deleted_counts
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'删除失败：{str(e)}'}, status=500)


# 查找基地
@require_GET
def get_base(request):
    try:
        # 1. 获取分页参数
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))

        # 2. 查询数据库（输出字段名与前端保持一致：baseID/baseName/province/city/description）
        qs = Base.objects.all()

        # 支持Layui表格 where: { baseName: 'xxx' } 的模糊搜索
        base_name_kw = request.GET.get('baseName')
        if base_name_kw:
            qs = qs.filter(base_name__icontains=base_name_kw.strip())

        # 不使用 F/annotate：先取模型原字段，再在 Python 中组装为前端需要的别名
        rows = list(qs.values(
            'base_id', 'base_name', 'longitude', 'latitude',
            'province_name', 'city_name', 'base_description', 'base_pic'
        ))
        queryset = [
            {
                'baseID': r.get('base_id'),
                'baseName': r.get('base_name'),
                'longitude': r.get('longitude'),
                'latitude': r.get('latitude'),
                'province': r.get('province_name'),
                'city': r.get('city_name'),
                'description': r.get('base_description'),
                'basePic': r.get('base_pic'),
            }
            for r in rows
        ]

        # 3. 分页处理
        paginator = Paginator(queryset, limit)
        current_page = paginator.page(page)

        # 4. 构造符合Layui规范的响应数据
        response_data = {
            "code": 200,  # 必须为200表示成功
            "msg": "success",  # 提示信息
            "count": paginator.count,  # 总数据量
            "data": list(current_page)  # 当前页数据
        }

    except Exception as e:
        # 错误处理
        response_data = {
            "code": 500,
            "msg": f"服务器错误: {str(e)}",
            "count": 0,
            "data": []
        }

    return JsonResponse(response_data, safe=False)

# 修改基地
@csrf_exempt
@require_POST
def edit_base(request):
    """
    修改基地名称和描述
    POST /edit_base/
    - 支持 application/json 和 form-data
    - 只允许修改 base_name 与 base_description
    """
    try:
        # 兼容 JSON 与表单两种提交方式
        if request.content_type and request.content_type.startswith("application/json"):
            payload = json.loads(request.body or "{}")
            base_id = (payload.get("base_id") or "").strip()
            base_name = (payload.get("base_name") or "").strip()
            base_description = (payload.get("base_description") or "").strip()
        else:
            base_id = (request.POST.get("base_id") or "").strip()
            base_name = (request.POST.get("base_name") or "").strip()
            base_description = (request.POST.get("base_description") or "").strip()

        if not base_id:
            return JsonResponse({"success": False, "error": "缺少参数 base_id"}, status=400)

        base_obj = Base.objects.filter(base_id=base_id).first()
        if not base_obj:
            return JsonResponse({"success": False, "error": f"基地编号 {base_id} 不存在"}, status=404)

        if not base_name:
            return JsonResponse({"success": False, "error": "基地名称不能为空"}, status=400)

        # 只更新名称和描述
        base_obj.base_name = base_name
        base_obj.base_description = base_description
        base_obj.save(update_fields=["base_name", "base_description"])

        return JsonResponse({
            "success": True,
            "message": "基地信息更新成功",
            "data": {
                "base_id": base_obj.base_id,
                "base_name": base_obj.base_name,
                "base_description": base_obj.base_description or "",
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"修改失败：{str(e)}"}, status=500)
