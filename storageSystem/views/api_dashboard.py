# storageSystem/views/api_dashboard.py
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import json
import re
import traceback

import pymysql
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt


# ========= 配置与连接 =========

def _get_cfg() -> dict:
    cfg = getattr(settings, "REMOTE_MYSQL", None)
    if not cfg:
        raise RuntimeError("settings.REMOTE_MYSQL 未配置")
    return cfg


def _pick(cfg: dict, *keys, default=None):
    for k in keys:
        if k in cfg and cfg[k] not in (None, ""):
            return cfg[k]
    return default


def _get_remote_conn():
    cfg = _get_cfg()

    host = _pick(cfg, "HOST", "host")
    user = _pick(cfg, "USER", "user", "USERNAME", "username")
    password = _pick(cfg, "PASSWORD", "password", "PASS", "pass") or ""
    database = _pick(cfg, "NAME", "name", "DATABASE", "database", "DB", "db")
    port = int(_pick(cfg, "PORT", "port", default=3306))
    charset = _pick(cfg, "CHARSET", "charset", default="utf8mb4")

    missing = [k for k, v in [("host", host), ("user", user), ("database", database)] if not v]
    if missing:
        raise RuntimeError(f"REMOTE_MYSQL 配置缺失字段: {', '.join(missing)}（请检查 settings.REMOTE_MYSQL 键名）")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset=charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=20,
        write_timeout=20,
    )


# ========= JSON 返回 =========

def _json_ok(data: Dict[str, Any]) -> JsonResponse:
    payload = {"ok": True}
    payload.update(data)
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


def _json_err(e: Exception, status: int = 500) -> JsonResponse:
    traceback.print_exc()
    payload = {"ok": False, "error": repr(e)}
    if getattr(settings, "DEBUG", False):
        payload["traceback"] = traceback.format_exc()
    return JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})


# ========= 安全：表名/列名校验（防止注入） =========

_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _safe_ident(name: str, what: str = "identifier") -> str:
    name = (name or "").strip()
    if not name or not _IDENT_RE.match(name):
        raise RuntimeError(f"非法{what}: {name!r}")
    return name


# ========= 工具：字段/表结构 =========

_NUM_PREFIX = ("int", "bigint", "smallint", "tinyint", "mediumint", "float", "double", "decimal")


def _is_numeric_mysql_type(mysql_type: str) -> bool:
    t = (mysql_type or "").lower()
    return any(t.startswith(p) for p in _NUM_PREFIX)


def _get_table_columns(cur, table: str) -> Tuple[List[dict], List[str], List[str]]:
    table = _safe_ident(table, "table")
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()  # Field, Type, Null, Key, Default, Extra
    pk_cols = [c["Field"] for c in cols if c.get("Key") == "PRI"]
    all_names = [c["Field"] for c in cols]
    return cols, pk_cols, all_names


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
    """只要 key 存在就算（即使值是 null/""）"""
    return any(k in d for k in keys)


def _build_device_where(dev_id, dev_name: str, dev_code: str):
    """
    返回 (where_sql, where_params)
    定位优先级：id > device_name > device_code
    """
    if dev_id not in (None, "", 0):
        return "`id`=%s", [int(dev_id)]
    if dev_name:
        return "`device_name`=%s", [dev_name]
    if dev_code:
        return "`device_code`=%s", [dev_code]
    return None, None


def _fetch_one_device(cur, devices_table: str, where_sql: str, where_params: List[Any]):
    """
    按你 devices 表结构固定输出（并给前端友好别名）
    """
    cur.execute(
        f"""
        SELECT
          `id` AS id,
          `device_name` AS device_name,
          `device_code` AS code,
          `coldroom_id` AS cold_room,
          `longitude` AS longitude,
          `latitude` AS latitude,
          `location` AS location,
          `status` AS status,
          `last_report_time` AS last_seen
        FROM `{devices_table}`
        WHERE {where_sql}
        LIMIT 1
        """,
        where_params,
    )
    row = cur.fetchone()
    if row and isinstance(row.get("last_seen"), datetime):
        row["last_seen"] = row["last_seen"].strftime("%Y-%m-%d %H:%M:%S")
    return row


# ========= API =========

@require_GET
def device_names(request):
    """
    下拉框设备列表：devices.device_name
    GET /storage/api/device-names/
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT `device_name` AS device_name
                FROM `{devices_table}`
                WHERE `device_name` IS NOT NULL AND `device_name` <> ''
                ORDER BY `device_name`
                """
            )
            rows = cur.fetchall() or []

        names = [r["device_name"] for r in rows if r.get("device_name")]
        return _json_ok({"device_names": names})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@require_GET
def stats(request):
    """
    KPI：从 devices.status 统计 online/offline/alarm
    GET /storage/api/dashboard/stats/
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  COUNT(*) AS total,
                  SUM(status='online')  AS online,
                  SUM(status='offline') AS offline,
                  SUM(status='alarm')   AS alarm
                FROM `{devices_table}`
                """
            )
            row = cur.fetchone() or {}

        row["total"] = int(row.get("total") or 0)
        row["online"] = int(row.get("online") or 0)
        row["offline"] = int(row.get("offline") or 0)
        row["alarm"] = int(row.get("alarm") or 0)

        return _json_ok({"kpi": row, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@require_GET
def dashboard_devices(request):
    """
    ✅ 设备明细表：分页 + 筛选
    GET /storage/api/dashboard/devices/?page=1&page_size=10&cold_room=1&status=online&device_name=xxx&keyword=xxx&date_from=2026-01-01&date_to=2026-01-31
    说明：
    - cold_room：这里按 coldroom_id 过滤（只接受数字），因为你没有 coldroom 表
    - date_from/date_to：按 last_report_time 过滤
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    # 分页
    try:
        page = max(int(request.GET.get("page", "1")), 1)
        page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
    except Exception:
        page, page_size = 1, 10
    offset = (page - 1) * page_size

    cold_room = (request.GET.get("cold_room") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    device_name = (request.GET.get("device_name") or "").strip()
    keyword = (request.GET.get("keyword") or "").strip()
    date_from = _parse_date_ymd(request.GET.get("date_from") or "")
    date_to = _parse_date_ymd(request.GET.get("date_to") or "")

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            where = ["1=1"]
            params: List[Any] = []

            # coldroom_id 过滤（只接受数字）
            if cold_room:
                if cold_room.isdigit():
                    where.append("`coldroom_id`=%s")
                    params.append(int(cold_room))
                else:
                    # 不是数字就忽略（避免误导）
                    pass

            if status:
                where.append("`status`=%s")
                params.append(status)

            if device_name:
                where.append("`device_name`=%s")
                params.append(device_name)

            if keyword:
                like = f"%{keyword}%"
                where.append("(`device_name` LIKE %s OR `device_code` LIKE %s OR `location` LIKE %s)")
                params.extend([like, like, like])

            if date_from:
                where.append("DATE(`last_report_time`) >= %s")
                params.append(date_from.strftime("%Y-%m-%d"))
            if date_to:
                where.append("DATE(`last_report_time`) <= %s")
                params.append(date_to.strftime("%Y-%m-%d"))

            where_sql = " AND ".join(where)

            # total
            cur.execute(f"SELECT COUNT(*) AS cnt FROM `{devices_table}` WHERE {where_sql}", params)
            total = int((cur.fetchone() or {}).get("cnt", 0) or 0)

            # items（输出前端友好字段名）
            cur.execute(
                f"""
                SELECT
                  `id` AS id,
                  `device_name` AS device_name,
                  `device_code` AS code,
                  `coldroom_id` AS cold_room,
                  `longitude` AS longitude,
                  `latitude` AS latitude,
                  `location` AS location,
                  `status` AS status,
                  `last_report_time` AS last_seen
                FROM `{devices_table}`
                WHERE {where_sql}
                ORDER BY `id` DESC
                LIMIT %s OFFSET %s
                """,
                (*params, page_size, offset),
            )
            items = cur.fetchall() or []

            # KPI（全表统计）
            cur.execute(
                f"""
                SELECT
                  SUM(status='online')  AS online,
                  SUM(status='offline') AS offline,
                  SUM(status='alarm')   AS alarm
                FROM `{devices_table}`
                """
            )
            row = cur.fetchone() or {}
            kpi = {
                "online": int(row.get("online") or 0),
                "offline": int(row.get("offline") or 0),
                "alarm": int(row.get("alarm") or 0),
            }

        # 格式化时间
        for it in items:
            ls = it.get("last_seen")
            if isinstance(ls, datetime):
                it["last_seen"] = ls.strftime("%Y-%m-%d %H:%M:%S")

        return _json_ok({"items": items, "total": total, "kpi": kpi})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@require_GET
def trend(request):
    """
    趋势折线：
    - X轴：settings.SENSOR_TIME_COL（默认 collected_at）
    - Y轴：排除主键/image_path/device_name/time_col 后的数值列
    - 如果 readings 表有 device_name 列，就按 device_name 过滤
    """
    device_name = (request.GET.get("device_name") or "").strip()

    range_ = (request.GET.get("range") or "7d").strip().lower()
    days = 7 if range_ == "7d" else 30

    try:
        limit = int(request.GET.get("limit") or 800)
    except Exception:
        limit = 800
    limit = max(50, min(limit, 2000))

    table = _safe_ident(getattr(settings, "SENSOR_TABLE", "sensor_readings1"), "table")
    time_col = _safe_ident(getattr(settings, "SENSOR_TIME_COL", "collected_at"), "column")

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            cols_info, pk_cols, all_cols = _get_table_columns(cur, table)
            all_cols_set = set(all_cols)

            has_device_col = "device_name" in all_cols_set

            series_cols: List[str] = []
            for c in cols_info:
                name = c["Field"]
                typ = c.get("Type", "")
                if name in pk_cols:
                    continue
                if name in ("image_path", time_col, "device_name"):
                    continue
                if _is_numeric_mysql_type(typ):
                    series_cols.append(name)

            if not series_cols:
                return _json_ok({"x": [], "series": [], "note": "没有可绘制的数值列（已排除主键/image_path）"})

            select_list = ", ".join([f"`{time_col}` AS t"] + [f"`{_safe_ident(c,'column')}`" for c in series_cols])

            where_parts = [
                f"`{time_col}` >= (SELECT MAX(`{time_col}`) FROM `{table}`) - INTERVAL %s DAY"
            ]
            params: List[Any] = [days]

            note = None
            if device_name and has_device_col:
                where_parts.append("`device_name`=%s")
                params.append(device_name)
            elif device_name and (not has_device_col):
                note = "提示：该数据表没有 device_name 列，已忽略按设备过滤"

            where_sql = " AND ".join(where_parts)

            cur.execute(
                f"""
                SELECT {select_list}
                FROM `{table}`
                WHERE {where_sql}
                ORDER BY `{time_col}` DESC
                LIMIT %s
                """,
                (*params, limit),
            )
            rows = cur.fetchall() or []

        rows = list(reversed(rows))

        x: List[str] = []
        for r in rows:
            t = r.get("t")
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
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ========= ✅ 保存经纬度（只操作 devices 表） =========

@csrf_exempt
@require_POST
def save_device_location(request):
    """
    POST /storage/api/dashboard/device-location/
    {
      "id": 123,                     # 推荐
      "device_name": "xxx",          # 可选
      "device_code": "SN001",        # 可选
      "longitude": 113.123456,
      "latitude": 23.123456,
      "location": "详细地址/备注"     # 可选（允许 "" -> NULL）
    }
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    lng = data.get("longitude")
    lat = data.get("latitude")
    loc = (data.get("location") or "").strip()

    if lng is None or lat is None:
        return _json_err(ValueError("缺少 longitude/latitude"), status=400)

    try:
        lng_f = float(lng)
        lat_f = float(lat)
    except Exception:
        return _json_err(ValueError("longitude/latitude 必须是数字"), status=400)

    if not (-180.0 <= lng_f <= 180.0) or not (-90.0 <= lat_f <= 90.0):
        return _json_err(ValueError("longitude/latitude 超出范围"), status=400)

    where_sql, where_params = _build_device_where(dev_id, dev_name, dev_code)
    if not where_sql:
        return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            set_parts = ["`longitude`=%s", "`latitude`=%s"]
            params: List[Any] = [lng_f, lat_f]

            if _key_in(data, "location"):
                if loc == "":
                    set_parts.append("`location`=NULL")
                else:
                    set_parts.append("`location`=%s")
                    params.append(loc)

            sql = f"""
            UPDATE `{devices_table}`
            SET {", ".join(set_parts)}
            WHERE {where_sql}
            LIMIT 1
            """
            cur.execute(sql, (*params, *where_params))
            affected = cur.rowcount or 0

            if affected <= 0:
                exists = _fetch_one_device(cur, devices_table, where_sql, where_params)
                if not exists:
                    return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        return _json_ok({"updated": int(affected), "longitude": lng_f, "latitude": lat_f, "location": loc})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ========= ✅ 更新设备（只操作 devices 表） =========

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
      "coldroom_id": 1,          # 可选（数字）
      "longitude": 113.1,        # 可选（null/"" -> NULL）
      "latitude": 30.4,          # 可选
      "location": "武汉",        # 可选（"" -> NULL）
      "status": "online"         # 可选：online/offline/alarm/normal（与前端一致）
    }

    兼容前端字段：
    - cold_room_id / cold_room（只要是数字，也会当 coldroom_id 处理）
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    # 允许用 match_* 作为 WHERE（兼容旧前端）
    match_name = (data.get("match_device_name") or "").strip()
    match_code = (data.get("match_device_code") or "").strip()
    where_sql, where_params = _build_device_where(
        dev_id,
        match_name or dev_name,
        match_code or dev_code
    )
    if not where_sql:
        return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

    # 是否有更新字段
    if not any(
        k in data for k in [
            "device_name", "device_code",
            "coldroom_id", "cold_room_id", "cold_room",
            "longitude", "latitude",
            "location",
            "status",
        ]
    ):
        return _json_err(ValueError("没有提供任何可更新字段"), status=400)

    set_parts: List[str] = []
    params: List[Any] = []

    # device_name
    if _key_in(data, "device_name"):
        v = data.get("device_name")
        v = "" if v is None else str(v).strip()
        if v == "":
            set_parts.append("`device_name`=NULL")
        else:
            set_parts.append("`device_name`=%s")
            params.append(v)

    # device_code
    if _key_in(data, "device_code"):
        v = data.get("device_code")
        v = "" if v is None else str(v).strip()
        if v == "":
            set_parts.append("`device_code`=NULL")
        else:
            set_parts.append("`device_code`=%s")
            params.append(v)

    # coldroom_id（兼容 cold_room_id / cold_room）
    if _key_in(data, "coldroom_id", "cold_room_id", "cold_room"):
        raw = data.get("coldroom_id", None)
        if raw is None and "cold_room_id" in data:
            raw = data.get("cold_room_id")
        if raw is None and "cold_room" in data:
            raw = data.get("cold_room")

        cid = _to_int_or_none(raw)
        if cid is None:
            set_parts.append("`coldroom_id`=NULL")
        else:
            set_parts.append("`coldroom_id`=%s")
            params.append(cid)

    # longitude
    if _key_in(data, "longitude"):
        lng = _to_float_or_none(data.get("longitude"))
        if lng is None:
            set_parts.append("`longitude`=NULL")
        else:
            if not (-180.0 <= lng <= 180.0):
                return _json_err(ValueError("longitude 超出范围"), status=400)
            set_parts.append("`longitude`=%s")
            params.append(lng)

    # latitude
    if _key_in(data, "latitude"):
        lat = _to_float_or_none(data.get("latitude"))
        if lat is None:
            set_parts.append("`latitude`=NULL")
        else:
            if not (-90.0 <= lat <= 90.0):
                return _json_err(ValueError("latitude 超出范围"), status=400)
            set_parts.append("`latitude`=%s")
            params.append(lat)

    # location
    if _key_in(data, "location"):
        loc = data.get("location")
        loc = "" if loc is None else str(loc).strip()
        if loc == "":
            set_parts.append("`location`=NULL")
        else:
            set_parts.append("`location`=%s")
            params.append(loc)

    # status（与前端一致）
    if _key_in(data, "status"):
        st = data.get("status")
        st = "" if st is None else str(st).strip().lower()
        if st == "":
            set_parts.append("`status`=NULL")
        else:
            allow = {"online", "offline", "alarm", "normal"}
            if st not in allow:
                return _json_err(ValueError(f"status 不合法：{st}（允许 {sorted(list(allow))}）"), status=400)
            set_parts.append("`status`=%s")
            params.append(st)

    if not set_parts:
        return _json_err(RuntimeError("提供了字段但没有形成任何可更新列（请检查字段名）"), status=400)

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            sql = f"""
            UPDATE `{devices_table}`
            SET {", ".join(set_parts)}
            WHERE {where_sql}
            LIMIT 1
            """
            cur.execute(sql, (*params, *where_params))
            affected = cur.rowcount or 0

            row = _fetch_one_device(cur, devices_table, where_sql, where_params)
            if not row:
                return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        return _json_ok({"updated": int(affected), "device": row})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ========= ✅ 删除设备（只操作 devices 表） =========

@csrf_exempt
@require_POST
def delete_device(request):
    """
    POST /storage/api/dashboard/device-delete/
    { "id": 123 }  # 推荐
    或
    { "device_name": "xxx" }
    或
    { "device_code": "SN001" }
    """
    devices_table = _safe_ident(getattr(settings, "DEVICES_TABLE", "devices"), "table")

    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or "").strip()
    dev_code = (data.get("device_code") or "").strip()

    where_sql, where_params = _build_device_where(dev_id, dev_name, dev_code)
    if not where_sql:
        return _json_err(ValueError("缺少定位字段：id 或 device_name 或 device_code"), status=400)

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            # 先查一下要删的是谁（便于前端提示）
            row = _fetch_one_device(cur, devices_table, where_sql, where_params)

            cur.execute(f"DELETE FROM `{devices_table}` WHERE {where_sql} LIMIT 1", where_params)
            affected = cur.rowcount or 0

            if affected <= 0 and not row:
                return _json_err(RuntimeError("未删除：设备不存在或条件未命中"), status=404)

        return _json_ok({"deleted": int(affected), "device": row})

    except Exception as e:
        return _json_err(e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
