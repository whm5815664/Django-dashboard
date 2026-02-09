# storageSystem/views/api_dashboard.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import json
import traceback

from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import connection, models, transaction
from django.db.models import Q, Count, Max
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from storageSystem.models import Base, Device, DeviceReading


# ========= JSON 返回 =========

def _json_ok(data: Dict[str, Any]) -> JsonResponse:
    payload = {"ok": True}
    payload.update(data)
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


def _json_err(e: Exception, status: int = 500) -> JsonResponse:
    traceback.print_exc()
    payload = {"ok": False, "error": repr(e)}
    return JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})


# ========= 基础工具 =========

def _parse_date_ymd(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_json_body(request) -> Dict[str, Any]:
    ctype = (request.META.get("CONTENT_TYPE") or "").lower()
    if "application/json" in ctype:
        try:
            raw = request.body.decode("utf-8") if request.body else ""
            return json.loads(raw) if raw else {}
        except Exception:
            return {}
    return {}


def _to_float_or_none(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return None
    return float(s)


def _to_int_or_none(v):
    if v is None:
        return None
    if isinstance(v, int):
        return int(v)
    s = str(v).strip()
    if s == "":
        return None
    return int(s)


def _key_in(d: Dict[str, Any], *keys: str) -> bool:
    return any(k in d for k in keys)


def _field_exists(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _pick_field(model_cls, *candidates: str) -> Optional[str]:
    for name in candidates:
        if _field_exists(model_cls, name):
            return name
    return None


def _get_existing_db_columns(model_cls) -> set[str]:
    """
    用 Django introspection 获取真实表结构列，避免“模型有字段但数据库无此列”导致 1054 报错。
    """
    table = model_cls._meta.db_table
    with connection.cursor() as cur:
        desc = connection.introspection.get_table_description(cur, table)
    return {c.name for c in desc}


def _get_existing_model_field_names(model_cls) -> set[str]:
    db_cols = _get_existing_db_columns(model_cls)
    names = set()
    for f in model_cls._meta.fields:
        if f.column in db_cols:
            names.add(f.name)
    return names


def _get_fk_id(instance, fk_field_name: Optional[str]):
    if not fk_field_name:
        return None
    attr_id = f"{fk_field_name}_id"
    if hasattr(instance, attr_id):
        return getattr(instance, attr_id)
    val = getattr(instance, fk_field_name, None)
    if hasattr(val, "pk"):
        return val.pk
    return val


def _format_dt(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


# ========= Device 字段映射（兼容 name/device_name 等命名） =========

DEVICE_ID_F = "id"
DEVICE_NAME_F = _pick_field(Device, "name", "device_name")
DEVICE_CODE_F = _pick_field(Device, "code", "device_code")
DEVICE_COLD_F = _pick_field(Device, "cold_room", "coldroom")
DEVICE_LOCATION_F = _pick_field(Device, "location")
DEVICE_STATUS_F = _pick_field(Device, "status")
DEVICE_LAST_SEEN_F = _pick_field(Device, "last_seen", "last_report_time", "reported_at")
DEVICE_LON_F = _pick_field(Device, "longitude", "lng")
DEVICE_LAT_F = _pick_field(Device, "latitude", "lat")


def _serialize_device(obj: Device) -> Dict[str, Any]:
    last_seen_val = getattr(obj, DEVICE_LAST_SEEN_F, None) if DEVICE_LAST_SEEN_F else None
    # 获取 base_id：Device 有 base 外键，base.base_id 是字符串主键
    base_id_val = None
    if hasattr(obj, "base") and obj.base:
        base_id_val = obj.base.base_id if hasattr(obj.base, "base_id") else None
    elif hasattr(obj, "base_id"):
        base_id_val = getattr(obj, "base_id", None)
    
    return {
        "id": obj.pk,
        "device_name": getattr(obj, DEVICE_NAME_F, None) if DEVICE_NAME_F else None,
        "code": getattr(obj, DEVICE_CODE_F, None) if DEVICE_CODE_F else None,
        "base_id": base_id_val,  # 使用 base_id 而不是 cold_room
        "longitude": getattr(obj, DEVICE_LON_F, None) if DEVICE_LON_F else None,
        "latitude": getattr(obj, DEVICE_LAT_F, None) if DEVICE_LAT_F else None,
        "location": getattr(obj, DEVICE_LOCATION_F, None) if DEVICE_LOCATION_F else None,
        "status": getattr(obj, DEVICE_STATUS_F, None) if DEVICE_STATUS_F else None,
        "last_seen": _format_dt(last_seen_val),
    }


def _build_device_q(dev_id, dev_name: str, dev_code: str) -> Optional[Q]:
    """
    定位优先级：id > device_name > device_code
    """
    if dev_id not in (None, "", 0):
        try:
            return Q(pk=int(dev_id))
        except Exception:
            raise ValueError("id 必须是整数")
    if dev_name and DEVICE_NAME_F:
        return Q(**{DEVICE_NAME_F: dev_name})
    if dev_code and DEVICE_CODE_F:
        return Q(**{DEVICE_CODE_F: dev_code})
    return None


# ========= API =========

@require_GET
def device_names(request):
    """
    下拉框设备列表
    GET /storage/api/device-names/
    """
    try:
        if not DEVICE_NAME_F:
            return _json_ok({"device_names": []})

        names = (
            Device.objects
            .exclude(**{f"{DEVICE_NAME_F}__isnull": True})
            .exclude(**{DEVICE_NAME_F: ""})
            .values_list(DEVICE_NAME_F, flat=True)
            .distinct()
            .order_by(DEVICE_NAME_F)
        )
        return _json_ok({"device_names": list(names)})
    except Exception as e:
        return _json_err(e)


@require_GET
def stats(request):
    """
    KPI：统计 online/offline/alarm
    GET /storage/api/dashboard/stats/
    """
    try:
        total = Device.objects.count()

        if DEVICE_STATUS_F:
            agg = Device.objects.aggregate(
                online=Count("id", filter=Q(**{DEVICE_STATUS_F: "online"})),
                offline=Count("id", filter=Q(**{DEVICE_STATUS_F: "offline"})),
                alarm=Count("id", filter=Q(**{DEVICE_STATUS_F: "alarm"})),
            )
            row = {
                "total": int(total),
                "online": int(agg.get("online") or 0),
                "offline": int(agg.get("offline") or 0),
                "alarm": int(agg.get("alarm") or 0),
            }
        else:
            row = {"total": int(total), "online": 0, "offline": 0, "alarm": 0}

        return _json_ok({"kpi": row, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as e:
        return _json_err(e)


@require_GET
def dashboard_devices(request):
    """
    设备明细表：分页 + 筛选
    GET /storage/api/dashboard/devices/?page=1&page_size=10&base_id=HB001&status=online&device_name=xxx&keyword=xxx&date_from=2026-01-01&date_to=2026-01-31
    说明：
    - base_id：按基地编号过滤
    - date_from/date_to：按 last_report_time 过滤
    """
    try:
        # 分页
        try:
            page = max(int(request.GET.get("page", "1")), 1)
            page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
        except Exception:
            page, page_size = 1, 10

        base_id = (request.GET.get("base_id") or "").strip()
        status = (request.GET.get("status") or "").strip().lower()
        device_name = (request.GET.get("device_name") or "").strip()
        keyword = (request.GET.get("keyword") or "").strip()
        date_from = _parse_date_ymd(request.GET.get("date_from") or "")
        date_to = _parse_date_ymd(request.GET.get("date_to") or "")

        qs = Device.objects.all()

        # base_id 过滤（Device 模型有 base 外键，对应 base_id 列）
        if base_id:
            # 支持按 base_id 字符串值过滤（Base.base_id 是字符串字段）
            qs = qs.filter(base_id=base_id)

        # status
        if status and DEVICE_STATUS_F:
            qs = qs.filter(**{DEVICE_STATUS_F: status})

        # device_name
        if device_name and DEVICE_NAME_F:
            qs = qs.filter(**{DEVICE_NAME_F: device_name})

        # keyword
        if keyword:
            q_kw = Q()
            if DEVICE_NAME_F:
                q_kw |= Q(**{f"{DEVICE_NAME_F}__icontains": keyword})
            if DEVICE_CODE_F:
                q_kw |= Q(**{f"{DEVICE_CODE_F}__icontains": keyword})
            if DEVICE_LOCATION_F:
                q_kw |= Q(**{f"{DEVICE_LOCATION_F}__icontains": keyword})
            if q_kw:
                qs = qs.filter(q_kw)

        # date range on last_seen
        if DEVICE_LAST_SEEN_F and date_from:
            qs = qs.filter(**{f"{DEVICE_LAST_SEEN_F}__date__gte": date_from})
        if DEVICE_LAST_SEEN_F and date_to:
            qs = qs.filter(**{f"{DEVICE_LAST_SEEN_F}__date__lte": date_to})

        qs = qs.order_by("-id")
        total = qs.count()

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        items = [_serialize_device(obj) for obj in page_obj.object_list]

        # KPI（全表）
        if DEVICE_STATUS_F:
            k = Device.objects.aggregate(
                online=Count("id", filter=Q(**{DEVICE_STATUS_F: "online"})),
                offline=Count("id", filter=Q(**{DEVICE_STATUS_F: "offline"})),
                alarm=Count("id", filter=Q(**{DEVICE_STATUS_F: "alarm"})),
            )
            kpi = {
                "online": int(k.get("online") or 0),
                "offline": int(k.get("offline") or 0),
                "alarm": int(k.get("alarm") or 0),
            }
        else:
            kpi = {"online": 0, "offline": 0, "alarm": 0}

        return _json_ok({"items": items, "total": total, "kpi": kpi})

    except Exception as e:
        return _json_err(e)


@require_GET
def trend(request):
    """
    趋势折线（纯 ORM）：
    - 从 DeviceReading 读取
    - X轴：时间字段（优先 reported_at）
    - Y轴：数值列（自动识别 + 只取数据库真实存在的列，避免 1054）
    - 可选按 device_name 过滤（若有 device_name 字段；否则尝试通过 FK device 关联过滤）
    """
    device_name = (request.GET.get("device_name") or "").strip()

    range_ = (request.GET.get("range") or "7d").strip().lower()
    days = 7 if range_ == "7d" else 30

    try:
        limit = int(request.GET.get("limit") or 800)
    except Exception:
        limit = 800
    limit = max(50, min(limit, 2000))

    try:
        # 1) 时间字段
        time_f = _pick_field(DeviceReading, "reported_at", "collected_at", "last_report_time", "created_at")
        if not time_f:
            return _json_ok({"x": [], "series": [], "note": "DeviceReading 模型中找不到时间字段（reported_at/collected_at）"})

        # 2) 只保留“真实数据库存在”的字段，防止 Unknown column
        existing_fields = _get_existing_model_field_names(DeviceReading)
        if time_f not in existing_fields:
            return _json_ok({"x": [], "series": [], "note": f"时间字段 {time_f} 不存在于真实数据表中"})

        # 3) 自动识别数值字段
        numeric_types = (
            models.IntegerField,
            models.BigIntegerField,
            models.SmallIntegerField,
            models.PositiveIntegerField,
            models.PositiveSmallIntegerField,
            models.FloatField,
            models.DecimalField,
        )

        series_cols: List[str] = []
        excluded = {"id", time_f, "device_name", "image_path"}

        for f in DeviceReading._meta.fields:
            if f.name in excluded:
                continue
            if f.name not in existing_fields:
                continue
            if isinstance(f, numeric_types):
                series_cols.append(f.name)

        if not series_cols:
            return _json_ok({"x": [], "series": [], "note": "没有可绘制的数值列"})

        qs = DeviceReading.objects.all()

        # 4) 时间窗口：以最大时间往前 days 天
        max_t = qs.aggregate(mx=Max(time_f)).get("mx")
        if not max_t:
            return _json_ok({"x": [], "series": []})

        start_t = max_t - timedelta(days=days)
        qs = qs.filter(**{f"{time_f}__gte": start_t})

        # 5) 设备过滤
        note = None
        if device_name:
            if _field_exists(DeviceReading, "device_name") and "device_name" in existing_fields:
                qs = qs.filter(device_name=device_name)
            elif _field_exists(DeviceReading, "device"):
                q_dev = Q()
                if DEVICE_NAME_F:
                    q_dev |= Q(**{f"device__{DEVICE_NAME_F}": device_name})
                if DEVICE_CODE_F:
                    q_dev |= Q(**{f"device__{DEVICE_CODE_F}": device_name})
                if q_dev:
                    qs = qs.filter(q_dev)
                else:
                    note = "提示：无法按设备过滤（Device 模型缺少 name/code 字段）"
            else:
                note = "提示：DeviceReading 无 device_name/device 关联，已忽略按设备过滤"

        value_fields = [time_f] + series_cols
        rows = list(qs.order_by(f"-{time_f}").values(*value_fields)[:limit])
        rows.reverse()

        x: List[str] = []
        for r in rows:
            t = r.get(time_f)
            if isinstance(t, datetime):
                x.append(t.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                x.append(str(t) if t is not None else "")

        series = [{"name": col, "data": [rr.get(col) for rr in rows]} for col in series_cols]

        out = {"x": x, "series": series}
        if note:
            out["note"] = note
        return _json_ok(out)

    except Exception as e:
        return _json_err(e)


# ========= 保存经纬度 =========

@csrf_exempt
@require_POST
def save_device_location(request):
    """
    POST /storage/api/dashboard/device-location/
    {
      "id": 123,            # 推荐
      "device_name": "xxx", # 可选
      "device_code": "SN001", # 可选
      "longitude": 113.123456,
      "latitude": 23.123456,
      "location": "详细地址/备注" # 可选
    }
    """
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    lng = data.get("longitude")
    lat = data.get("latitude")
    loc = data.get("location")

    if lng is None or lat is None:
        return _json_err(ValueError("缺少 longitude/latitude"), status=400)

    try:
        lng_f = float(lng)
        lat_f = float(lat)
    except Exception:
        return _json_err(ValueError("longitude/latitude 必须是数字"), status=400)

    if not (-180.0 <= lng_f <= 180.0) or not (-90.0 <= lat_f <= 90.0):
        return _json_err(ValueError("longitude/latitude 超出范围"), status=400)

    if not DEVICE_LON_F or not DEVICE_LAT_F:
        return _json_err(RuntimeError("Device 模型缺少 longitude/latitude 字段"), status=400)

    try:
        q = _build_device_q(dev_id, dev_name, dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

        obj = Device.objects.filter(q).order_by("id").first()
        if not obj:
            return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        update_fields = [DEVICE_LON_F, DEVICE_LAT_F]
        setattr(obj, DEVICE_LON_F, lng_f)
        setattr(obj, DEVICE_LAT_F, lat_f)

        if _key_in(data, "location") and DEVICE_LOCATION_F:
            text = "" if loc is None else str(loc).strip()
            field = obj._meta.get_field(DEVICE_LOCATION_F)
            if text == "":
                setattr(obj, DEVICE_LOCATION_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_LOCATION_F, text)
            update_fields.append(DEVICE_LOCATION_F)

        obj.save(update_fields=update_fields)

        return _json_ok({
            "updated": 1,
            "longitude": lng_f,
            "latitude": lat_f,
            "location": getattr(obj, DEVICE_LOCATION_F, None) if DEVICE_LOCATION_F else None,
        })

    except Exception as e:
        return _json_err(e)


# ========= 更新设备 =========

@csrf_exempt
@require_POST
def update_device(request):
    """
    POST /storage/api/dashboard/device-update/
    Content-Type: application/json
    {
      "id": 123,                 # 推荐：用 id 定位（优先）
      "device_name": "新名称",    # 可选
      "device_code": "SN001",    # 可选
      "base_id": "HB001",        # 可选（基地编号，字符串）
      "longitude": 113.1,        # 可选（null/"" -> NULL）
      "latitude": 30.4,          # 可选
      "location": "武汉",        # 可选（"" -> NULL）
      "status": "online"         # 可选：online/offline/alarm/normal（与前端一致）
    }
    """
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    match_name = (data.get("match_device_name") or "").strip()
    match_code = (data.get("match_device_code") or "").strip()

    try:
        q = _build_device_q(dev_id, match_name or dev_name, match_code or dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

        if not any(
            k in data for k in [
                "device_name", "device_code",
                "base_id",
                "longitude", "latitude",
                "location",
                "status",
            ]
        ):
            return _json_err(ValueError("没有提供任何可更新字段"), status=400)

        obj = Device.objects.filter(q).order_by("id").first()
        if not obj:
            return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        update_fields: List[str] = []

        # device_name -> name/device_name
        if _key_in(data, "device_name") and DEVICE_NAME_F:
            text = "" if data.get("device_name") is None else str(data.get("device_name")).strip()
            field = obj._meta.get_field(DEVICE_NAME_F)
            if text == "":
                setattr(obj, DEVICE_NAME_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_NAME_F, text)
            update_fields.append(DEVICE_NAME_F)

        # device_code -> code/device_code
        if _key_in(data, "device_code") and DEVICE_CODE_F:
            text = "" if data.get("device_code") is None else str(data.get("device_code")).strip()
            field = obj._meta.get_field(DEVICE_CODE_F)
            if text == "":
                setattr(obj, DEVICE_CODE_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_CODE_F, text)
            update_fields.append(DEVICE_CODE_F)

        # base_id 更新（Device 有 base 外键，引用 Base.base_id）
        if _key_in(data, "base_id"):
            raw = data.get("base_id", None)
            if raw is None:
                # 清空 base 关联
                obj.base = None
                update_fields.append("base")
            else:
                base_id_str = str(raw).strip()
                if base_id_str:
                    # 通过 base_id 查找 Base 对象
                    try:
                        base_obj = Base.objects.get(base_id=base_id_str)
                        obj.base = base_obj
                        update_fields.append("base")
                    except Base.DoesNotExist:
                        return _json_err(ValueError(f"base_id '{base_id_str}' 不存在"), status=400)
                else:
                    obj.base = None
                    update_fields.append("base")

        # longitude
        if _key_in(data, "longitude"):
            if not DEVICE_LON_F:
                return _json_err(ValueError("Device 模型缺少 longitude 字段"), status=400)
            lng = _to_float_or_none(data.get("longitude"))
            if lng is not None and not (-180.0 <= lng <= 180.0):
                return _json_err(ValueError("longitude 超出范围"), status=400)
            setattr(obj, DEVICE_LON_F, lng)
            update_fields.append(DEVICE_LON_F)

        # latitude
        if _key_in(data, "latitude"):
            if not DEVICE_LAT_F:
                return _json_err(ValueError("Device 模型缺少 latitude 字段"), status=400)
            lat = _to_float_or_none(data.get("latitude"))
            if lat is not None and not (-90.0 <= lat <= 90.0):
                return _json_err(ValueError("latitude 超出范围"), status=400)
            setattr(obj, DEVICE_LAT_F, lat)
            update_fields.append(DEVICE_LAT_F)

        # location
        if _key_in(data, "location") and DEVICE_LOCATION_F:
            text = "" if data.get("location") is None else str(data.get("location")).strip()
            field = obj._meta.get_field(DEVICE_LOCATION_F)
            if text == "":
                setattr(obj, DEVICE_LOCATION_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_LOCATION_F, text)
            update_fields.append(DEVICE_LOCATION_F)

        # status
        if _key_in(data, "status") and DEVICE_STATUS_F:
            st = "" if data.get("status") is None else str(data.get("status")).strip().lower()
            if st:
                allow = {"online", "offline", "alarm", "normal"}
                if st not in allow:
                    return _json_err(ValueError(f"status 不合法：{st}（允许 {sorted(list(allow))}）"), status=400)
            field = obj._meta.get_field(DEVICE_STATUS_F)
            if st == "":
                setattr(obj, DEVICE_STATUS_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_STATUS_F, st)
            update_fields.append(DEVICE_STATUS_F)

        if not update_fields:
            return _json_err(RuntimeError("提供了字段但没有形成任何可更新列（请检查字段名）"), status=400)

        update_fields = list(dict.fromkeys(update_fields))
        with transaction.atomic():
            obj.save(update_fields=update_fields)

        return _json_ok({"updated": 1, "device": _serialize_device(obj)})

    except Exception as e:
        return _json_err(e)


# ========= 删除设备 =========

@csrf_exempt
@require_POST
def delete_device(request):
    """
    POST /storage/api/dashboard/device-delete/
    { "id": 123 }  # 推荐
    或 { "device_name": "xxx" }
    或 { "device_code": "SN001" }
    """
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    try:
        q = _build_device_q(dev_id, dev_name, dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

        obj = Device.objects.filter(q).order_by("id").first()
        if not obj:
            return _json_err(RuntimeError("未删除：设备不存在或条件未命中"), status=404)

        row = _serialize_device(obj)
        obj.delete()

        return _json_ok({"deleted": 1, "device": row})

    except Exception as e:
        return _json_err(e)
