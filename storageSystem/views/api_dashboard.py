# storageSystem/views/api_dashboard.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

import traceback
import pymysql


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
    # 数据库连接配置在config/settings.py中

    host = _pick(cfg, "HOST", "host")
    user = _pick(cfg, "USER", "user", "USERNAME", "username")
    password = _pick(cfg, "PASSWORD", "password", "PASS", "pass")
    database = _pick(cfg, "NAME", "name", "DATABASE", "database", "DB", "db")
    port = int(_pick(cfg, "PORT", "port", default=3306))
    charset = _pick(cfg, "CHARSET", "charset", default="utf8mb4")
    
    # 如果 password 缺失，则设置为空字符串（表示无密码）
    if not password:
        password = ""

    # password 可以为空，所以不检查 password
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
    return JsonResponse(payload)


def _json_err(e: Exception, status: int = 500) -> JsonResponse:
    traceback.print_exc()
    payload = {"ok": False, "error": repr(e)}
    if getattr(settings, "DEBUG", False):
        payload["traceback"] = traceback.format_exc()
    return JsonResponse(payload, status=status)


# ========= 工具：挑选可画折线的数值列 =========

_NUM_PREFIX = ("int", "bigint", "smallint", "tinyint", "mediumint", "float", "double", "decimal")


def _is_numeric_mysql_type(mysql_type: str) -> bool:
    t = (mysql_type or "").lower()
    return any(t.startswith(p) for p in _NUM_PREFIX)


def _get_table_columns(cur, table: str) -> Tuple[List[dict], List[str], List[str]]:
    """
    返回：cols_info, pk_cols, all_col_names
    """
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()  # Field, Type, Null, Key, Default, Extra
    pk_cols = [c["Field"] for c in cols if c.get("Key") == "PRI"]
    all_names = [c["Field"] for c in cols]
    return cols, pk_cols, all_names


# ========= API =========

@require_GET
def device_names(request):
    """
    下拉框设备列表：只取 devices 表的 device_name
    GET /api/device-names/
    """
    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT device_name
                FROM devices
                WHERE device_name IS NOT NULL AND device_name <> ''
                ORDER BY device_name
            """)
            rows = cur.fetchall()

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
    目前可先不做；给前端占位，避免 500
    """
    return _json_ok({"kpi": {}})


@require_GET
def trend(request):
    """
    折线图数据：
- X轴：collected_at（或 settings.SENSOR_TIME_COL）
- Y轴：除主键和 image_path 外的“数值列”全部输出为 series
- 若表里没有 device_name 列，则忽略按设备过滤（但返回 note 提示）
- 时间范围按“MAX(collected_at) 往前 N 天”，避免数据旧导致空

GET /api/dashboard/trend?range=7d|30d&device_name=xxx&limit=800
    """
    device_name = (request.GET.get("device_name") or "").strip()

    range_ = (request.GET.get("range") or "7d").strip()
    days = 7 if range_ == "7d" else 30

    try:
        limit = int(request.GET.get("limit") or 800)
    except Exception:
        limit = 800
    limit = max(50, min(limit, 2000))

    table = getattr(settings, "SENSOR_TABLE", "sensor_readings1")
    time_col = getattr(settings, "SENSOR_TIME_COL", "collected_at")

    conn = None
    try:
        conn = _get_remote_conn()
        with conn.cursor() as cur:
            cols_info, pk_cols, all_cols = _get_table_columns(cur, table)

            # 1) 判断是否存在 device_name 列
            has_device_col = "device_name" in all_cols

            # 2) 选出要画的列：数值列；排除 pk、image_path、device_name、time_col
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

            select_list = ", ".join([f"`{time_col}` AS t"] + [f"`{c}`" for c in series_cols])

            # 3) 时间范围：相对“该表最新时间”往前 N 天（避免旧数据为空）
            #    注意：如果表为空，MAX 会是 NULL，这时 WHERE 条件会导致 0 行，属于正常返回空
            where_parts = [
                f"`{time_col}` >= (SELECT MAX(`{time_col}`) FROM `{table}`) - INTERVAL %s DAY"
            ]
            params: List[Any] = [days]

            # 4) 有 device_name 列且前端传了 device_name，才过滤
            note = None
            if device_name and has_device_col:
                where_parts.append("`device_name`=%s")
                params.append(device_name)
            elif device_name and (not has_device_col):
                note = "提示：该数据表没有 device_name 列，已忽略按设备过滤"

            where_sql = " AND ".join(where_parts)

            # 取最新 limit 条再反转为时间升序
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
            rows = cur.fetchall()

        rows = list(reversed(rows))

        # X 轴：格式化时间
        x: List[str] = []
        for r in rows:
            t = r.get("t")
            if isinstance(t, datetime):
                x.append(t.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                x.append(str(t) if t is not None else "")

        # series：每列一个折线
        series = []
        for col in series_cols:
            series.append({"name": col, "data": [rr.get(col) for rr in rows]})

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
