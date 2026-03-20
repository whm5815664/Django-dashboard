# storageSystem/views/api_dashboard.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import json
import traceback

from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import connections, models, transaction
from django.db.models import Q, Count, Max, OuterRef, Subquery
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from storageSystem.models import Base, Device, DeviceReading

# 使用远程数据库（pig）连接
REMOTE_DB = "pig"


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
    用 Django introspection 获取真实表结构列，避免"模型有字段但数据库无此列"导致 1054 报错。
    """
    table = model_cls._meta.db_table
    # 每次使用时从 connections 获取连接，避免线程安全问题
    connection = connections[REMOTE_DB]
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


def _format_dt(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v
def _norm_base_id(v: str):
    """
    base_id 来自 URL（比如 'HB001' 或 '1'），数据库 pigsty_id 是 bigint。
    如果输入是字符串格式（如 'HB001'），取后三位转为 int（'HB001' -> 1）。
    如果输入是纯数字字符串（如 '1'），直接转为 int。
    """
    s = (v or "").strip()
    if not s:
        return None
    # 如果是纯数字字符串，直接转为 int
    if s.isdigit():
        return int(s)
    # 如果是字符串格式（如 'HB001'），取后三位转为 int
    if len(s) >= 3:
        last_three = s[-3:]
        if last_three.isdigit():
            return int(last_three)
    # 如果后三位不是数字，返回 None 或原值（根据业务需求）
    # 这里返回 None 表示无效的 base_id
    return None

# ========= 适配你当前 device 表字段 =========

DEVICE_ID_F = "id"
DEVICE_NAME_F = _pick_field(Device, "name", "device_name")
# 你的 device 表字段是 device_code
DEVICE_CODE_F = _pick_field(Device, "device_code", "code", "device_code")
DEVICE_DESC_F = _pick_field(Device, "description")
DEVICE_NOTES_F = _pick_field(Device, "notes")

# 读数表时间字段：你 models 里把 collected_time 映射成 reported_at
READ_TIME_F = _pick_field(DeviceReading, "reported_at", "collected_time", "collected_at", "created_at")


def _build_device_q(dev_id, dev_name: str, dev_code: str) -> Optional[Q]:
    """
    定位优先级：id > name > device_code
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


def _annotate_device_last_seen_and_base(qs):
    """
    给 Device queryset 增加两个注解：
    - last_seen_ts：environment_data 最新采集时间
    - base_src_id：environment_data 最新 pigsty_id（库房来源）
    """
    if not READ_TIME_F:
        # 没有时间字段就不注解
        return qs

    last_seen_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .values("device_id")
        .annotate(mx=Max(READ_TIME_F))
        .values("mx")[:1]
    )

    # 最新一条记录的 pigsty_id
    base_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .order_by(f"-{READ_TIME_F}")
        .values("pigsty_id")[:1]
    )

    # 最新一条记录的图片路径
    image_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .order_by(f"-{READ_TIME_F}")
        .values("image_path")[:1]
    )

    return qs.annotate(
        last_seen_ts=Subquery(last_seen_sq),
        base_src_id=Subquery(base_sq),
        last_image_path=Subquery(image_sq),
    )


def _serialize_device(obj: Device, base_name_map: Dict[str, str] | None = None) -> Dict[str, Any]:
    name = getattr(obj, DEVICE_NAME_F, None) if DEVICE_NAME_F else None
    code = getattr(obj, DEVICE_CODE_F, None) if DEVICE_CODE_F else None
    desc = getattr(obj, DEVICE_DESC_F, None) if DEVICE_DESC_F else None

    collect_interval = getattr(obj, "collect_interval", None)
    created_at = getattr(obj, "created_at", None)
    updated_at = getattr(obj, "updated_at", None)

    last_seen = getattr(obj, "last_seen_ts", None)
    base_id = getattr(obj, "base_src_id", None)
    last_image_path = getattr(obj, "last_image_path", None)

    report_ts = last_seen or updated_at
    base_id_str = None if base_id is None else str(base_id)
    base_name = base_name_map.get(base_id_str) if (base_name_map and base_id_str) else None

    return {
        # ✅ 新字段（你现在页面表格要用的）
        "id": obj.pk,
        "name": name,
        "device_code": code,
        "description": desc,
        "collect_interval": collect_interval,
        "created_at": _format_dt(created_at),
        "updated_at": _format_dt(report_ts),
        "device_updated_at": _format_dt(updated_at),

        # ✅ 旧字段兼容
        "device_name": name,
        "code": code,
        "last_seen": _format_dt(last_seen),
        "base_id": base_id_str,
        "base_name": base_name,
        "image_path": last_image_path,
    }


# ========= API =========

@require_GET
def device_names(request):
    """
    GET /storage/api/device-names/?base_id=1
    返回：
      devices=[{id,name,device_code},...]
      device_names=[name...](旧兼容)
    """
    try:
        base_id = _norm_base_id(request.GET.get("base_id") or "")

        qs = Device.objects.using(REMOTE_DB).all()

        # ✅ 如果传了 base_id：只要这个设备在 environment_data 出现过 pigsty_id=base_id 就保留
        if base_id is not None:
            dev_ids = (
                DeviceReading.objects.using(REMOTE_DB)
                .filter(pigsty_id=base_id)
                .values_list("device_id", flat=True)
                .distinct()
            )
            qs = qs.filter(id__in=dev_ids)

        rows = list(
            qs.only("id", "name", "device_code")
              .values("id", "name", "device_code")
              .order_by("name", "id")
        )

        return _json_ok({
            "base_id": base_id,
            "devices": rows,
            "device_names": [r["name"] for r in rows if r.get("name")],
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def stats(request):
    """
    KPI：在新结构里没有 status 字段，因此 online/offline 用“最后上报时间”推断：
    - last_seen >= now - online_minutes => online
    - 否则 offline
    GET /storage/api/dashboard/stats/?online_minutes=10
    """
    try:
        try:
            online_minutes = int(request.GET.get("online_minutes") or 10)
        except Exception:
            online_minutes = 10
        online_minutes = max(1, min(online_minutes, 24 * 60))

        total = Device.objects.using(REMOTE_DB).count()
        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).all())

        th = datetime.now() - timedelta(minutes=online_minutes)
        online = qs.filter(last_seen_ts__gte=th).count()
        offline = int(total) - int(online)

        return _json_ok({
            "kpi": {
                "total": int(total),
                "online": int(online),
                "offline": int(offline),
                "alarm": 0,
            },
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": f"online/offline 按 last_seen >= now-{online_minutes}min 推断（device 表无 status 字段）",
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def dashboard_devices(request):
    try:
        # 分页
        try:
            page = max(int(request.GET.get("page", "1")), 1)
            page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
        except Exception:
            page, page_size = 1, 10

        device_code = (request.GET.get("device_code") or "").strip()
        keyword = (request.GET.get("keyword") or "").strip()
        date_from = _parse_date_ymd(request.GET.get("date_from") or "")
        date_to = _parse_date_ymd(request.GET.get("date_to") or "")

        # ✅ 新增：base_id（= environment_data.pigsty_id）
        base_id = _norm_base_id(request.GET.get("base_id") or "")

        qs = Device.objects.using(REMOTE_DB).all().only(
            "id", "name", "device_code", "description", "collect_interval", "created_at", "updated_at"
        )

        if device_code and DEVICE_CODE_F:
            qs = qs.filter(**{f"{DEVICE_CODE_F}": device_code})

        if keyword:
            q_kw = Q()
            if DEVICE_NAME_F:
                q_kw |= Q(**{f"{DEVICE_NAME_F}__icontains": keyword})
            if DEVICE_CODE_F:
                q_kw |= Q(**{f"{DEVICE_CODE_F}__icontains": keyword})
            if DEVICE_DESC_F:
                q_kw |= Q(**{f"{DEVICE_DESC_F}__icontains": keyword})
            qs = qs.filter(q_kw)

        # 注解 last_seen_ts（来自 environment_data 最新采集时间）和 base_src_id（最新 pigsty_id）
        qs = _annotate_device_last_seen_and_base(qs)

        # ✅ base_id 过滤：按“最新一条读数的 pigsty_id”判断设备当前属于哪个基地
        if base_id is not None:
            qs = qs.filter(base_src_id=base_id)

        # 日期过滤：按“最后上报时间”
        if date_from:
            qs = qs.filter(
                Q(last_seen_ts__date__gte=date_from) |
                Q(last_seen_ts__isnull=True, updated_at__date__gte=date_from)
            )
        if date_to:
            qs = qs.filter(
                Q(last_seen_ts__date__lte=date_to) |
                Q(last_seen_ts__isnull=True, updated_at__date__lte=date_to)
            )

        qs = qs.order_by("-id")
        total = qs.count()

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)

        items = []
        for obj in page_obj.object_list:
            last_seen = getattr(obj, "last_seen_ts", None)
            report_ts = last_seen or getattr(obj, "updated_at", None)

            items.append({
                "id": obj.pk,
                "name": getattr(obj, "name", None),
                "device_code": getattr(obj, "device_code", None),
                "description": getattr(obj, "description", None),
                "collect_interval": getattr(obj, "collect_interval", None),
                "created_at": _format_dt(getattr(obj, "created_at", None)),
                "updated_at": _format_dt(report_ts),

                # 兼容字段
                "device_name": getattr(obj, "name", None),
                "code": getattr(obj, "device_code", None),
                "last_seen": _format_dt(last_seen),

                # ✅ 让前端知道这是哪个基地过滤出来的
                "base_id": None if getattr(obj, "base_src_id", None) is None else str(getattr(obj, "base_src_id")),

                # ✅ 最新一条读数的图片路径（用于前端拼接 imageUrl）
                "image_path": getattr(obj, "last_image_path", None),
            })

        return _json_ok({
            "base_id": base_id,
            "items": items,
            "total": int(total),
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def trend(request):
    """
    GET /storage/api/dashboard/trend/?device_id=3&base_id=1&range=30d&limit=500
    - 数据来自 environment_data
    - 先按 device_id 过滤
    - 如果传 base_id：再按 pigsty_id 过滤
    - 窗口用“过滤后的数据”的 max(time) 往前 days 天
    """
    device_id_raw = (request.GET.get("device_id") or request.GET.get("id") or "").strip()
    device_name = (request.GET.get("device_name") or request.GET.get("name") or "").strip()
    device_code = (request.GET.get("device_code") or request.GET.get("code") or "").strip()

    # ✅ 新增：base_id（= pigsty_id）
    base_id = _norm_base_id(request.GET.get("base_id") or "")

    range_ = (request.GET.get("range") or "7d").strip().lower()
    days = 7 if range_ == "7d" else 30

    try:
        limit = int(request.GET.get("limit") or 800)
    except Exception:
        limit = 800
    limit = max(50, min(limit, 2000))

    try:
        time_f = _pick_field(DeviceReading, "reported_at", "collected_time", "collected_at", "created_at")
        if not time_f:
            return _json_ok({"x": [], "series": [], "note": "找不到时间字段"})

        existing_fields = _get_existing_model_field_names(DeviceReading)
        if time_f not in existing_fields:
            return _json_ok({"x": [], "series": [], "note": f"时间字段 {time_f} 不存在于真实表"})

        numeric_types = (
            models.IntegerField, models.BigIntegerField, models.SmallIntegerField,
            models.PositiveIntegerField, models.PositiveSmallIntegerField,
            models.FloatField, models.DecimalField,
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
            return _json_ok({"x": [], "series": [], "note": "没有可绘制数值列"})

        # 解析 device_id
        resolved_id: Optional[int] = None

        if device_id_raw:
            try:
                resolved_id = int(device_id_raw)
            except Exception:
                return _json_err(ValueError("device_id/id 必须是整数"), status=400)

        if resolved_id is None and device_code and DEVICE_CODE_F:
            dev = Device.objects.using(REMOTE_DB).filter(**{DEVICE_CODE_F: device_code}).only("id").first()
            if dev:
                resolved_id = int(dev.id)

        if resolved_id is None and device_name and DEVICE_NAME_F:
            dev = Device.objects.using(REMOTE_DB).filter(**{DEVICE_NAME_F: device_name}).only("id").order_by("id").first()
            if dev:
                resolved_id = int(dev.id)

        if resolved_id is None:
            return _json_ok({"x": [], "series": [], "note": "缺少 device_id（也可传 id / device_name / device_code）"})

        # ✅ 先按 device_id 过滤
        qs = DeviceReading.objects.using(REMOTE_DB).filter(device_id=resolved_id)

        # ✅ 再按 base_id 过滤（只取该基地 pigsty_id 的读数）
        if base_id is not None:
            qs = qs.filter(pigsty_id=base_id)

        # ✅ 用过滤后的 max(time) 计算窗口
        max_t = qs.aggregate(mx=Max(time_f)).get("mx")
        if not max_t:
            return _json_ok({
                "x": [],
                "series": [],
                "note": f"device_id={resolved_id} 在 environment_data 中没有数据（base_id={base_id}）",
                "device_id": resolved_id,
                "base_id": base_id,
            })

        start_t = max_t - timedelta(days=days)
        qs = qs.filter(**{f"{time_f}__gte": start_t})

        value_fields = [time_f] + series_cols
        rows = list(qs.order_by(f"-{time_f}").values(*value_fields)[:limit])
        rows.reverse()

        x = []
        for r in rows:
            t = r.get(time_f)
            x.append(t.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t, datetime) else str(t or ""))

        series = [{"name": col, "data": [rr.get(col) for rr in rows]} for col in series_cols]
        return _json_ok({
            "x": x,
            "series": series,
            "device_id": resolved_id,
            "base_id": base_id,
        })

    except Exception as e:
        return _json_err(e)


# ========= 不支持的旧接口（防止前端误调用报 500） =========

@csrf_exempt
@require_POST
def save_device_location(request):
    """
    你当前 device 表没有 longitude/latitude/location 字段，因此不支持保存位置。
    """
    return _json_err(RuntimeError("当前 device 表无经纬度/位置信息字段，save_device_location 接口不支持"), status=400)


# ========= 更新设备（适配新 device 表字段） =========

@csrf_exempt
@require_POST
def update_device(request):
    """
    POST /storage/api/dashboard/device-update/
    支持更新字段（适配新 device 表）：
      - device_name / name
      - device_code / code
      - description
      - notes
      - collect_interval
      - extract_air_time
      - extract_tested_gas_tin
      - extract_wait_time
    """
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or data.get("name") or "").strip()
    dev_code = (data.get("device_code") or data.get("code") or "").strip()

    match_name = (data.get("match_device_name") or "").strip()
    match_code = (data.get("match_device_code") or "").strip()

    try:
        q = _build_device_q(dev_id, match_name or dev_name, match_code or dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name/name 或 device_code/code"), status=400)

        obj = Device.objects.using(REMOTE_DB).filter(q).order_by("id").first()
        if not obj:
            return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        update_fields: List[str] = []

        # name
        if _key_in(data, "device_name", "name") and DEVICE_NAME_F:
            text = "" if (data.get("device_name") is None and data.get("name") is None) else str(data.get("device_name") or data.get("name")).strip()
            field = obj._meta.get_field(DEVICE_NAME_F)
            if text == "":
                setattr(obj, DEVICE_NAME_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_NAME_F, text)
            update_fields.append(DEVICE_NAME_F)

        # device_code
        if _key_in(data, "device_code", "code") and DEVICE_CODE_F:
            text = "" if (data.get("device_code") is None and data.get("code") is None) else str(data.get("device_code") or data.get("code")).strip()
            field = obj._meta.get_field(DEVICE_CODE_F)
            if text == "":
                setattr(obj, DEVICE_CODE_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_CODE_F, text)
            update_fields.append(DEVICE_CODE_F)

        # description / notes
        if _key_in(data, "description") and DEVICE_DESC_F:
            text = "" if data.get("description") is None else str(data.get("description")).strip()
            field = obj._meta.get_field(DEVICE_DESC_F)
            if text == "":
                setattr(obj, DEVICE_DESC_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_DESC_F, text)
            update_fields.append(DEVICE_DESC_F)

        if _key_in(data, "notes") and DEVICE_NOTES_F:
            text = "" if data.get("notes") is None else str(data.get("notes")).strip()
            field = obj._meta.get_field(DEVICE_NOTES_F)
            if text == "":
                setattr(obj, DEVICE_NOTES_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_NOTES_F, text)
            update_fields.append(DEVICE_NOTES_F)

        # float fields
        float_map = {
            "collect_interval": "collect_interval",
            "extract_air_time": "extract_air_time",
            "extract_tested_gas_tin": "extract_tested_gas_tin",
            "extract_wait_time": "extract_wait_time",
        }
        for k, field_name in float_map.items():
            if _key_in(data, k) and _field_exists(Device, field_name):
                v = _to_float_or_none(data.get(k))
                setattr(obj, field_name, v)
                update_fields.append(field_name)

        if not update_fields:
            return _json_err(ValueError("没有提供任何可更新字段（新 device 表不支持 base/status/经纬度/location）"), status=400)

        update_fields = list(dict.fromkeys(update_fields))
        with transaction.atomic(using=REMOTE_DB):
            obj.save(update_fields=update_fields, using=REMOTE_DB)

        # 重新注解 last_seen/base_src 以便返回
        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).filter(pk=obj.pk))
        obj2 = qs.first() or obj

        return _json_ok({"updated": 1, "device": _serialize_device(obj2)})

    except Exception as e:
        return _json_err(e)


# ========= 删除设备 =========

@csrf_exempt
@require_POST
def delete_device(request):
    """
    POST /storage/api/dashboard/device-delete/
    { "id": 123 } 或 { "device_name": "xxx" } 或 { "device_code": "SN001" }
    """
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or data.get("name") or "").strip()
    dev_code = (data.get("device_code") or data.get("code") or "").strip()

    try:
        q = _build_device_q(dev_id, dev_name, dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name/name 或 device_code/code"), status=400)

        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).filter(q).order_by("id"))
        obj = qs.first()
        if not obj:
            return _json_err(RuntimeError("未删除：设备不存在或条件未命中"), status=404)

        row = _serialize_device(obj)
        obj.delete(using=REMOTE_DB)

        return _json_ok({"deleted": 1, "device": row})

    except Exception as e:
        return _json_err(e)
