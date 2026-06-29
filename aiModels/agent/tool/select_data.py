import json
import re
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from screen.models import Base, EnvironmentData

# 内存 JSON：本地 base 表信息
BASE_INFO_DATA: Optional[Dict[str, Any]] = None
# 内存 JSON：远程 environment_data 环境信息
BASE_ENV_DATA: Optional[Dict[str, Any]] = None

ENV_VALUE_FIELDS = (
    "temperature",
    "humidity",
    "CO2",
    "VOC",
    "H2",
    "C2H4",
    "C2H5OH",
    "device_id",
    "collected_time",
)

BASE_INFO_FIELDS = (
    "base_id",
    "base_name",
    "longitude",
    "latitude",
    "province_name",
    "city_name",
    "base_description",
)


@dataclass(frozen=True)
class BasePigstyMapping:
    """本地 base 表记录与远程 pigsty_id 的对应关系。"""

    base_id: str
    pigsty_id: int
    base_name: str
    info: Dict[str, Any]


def extract_pigsty_id_from_base_id(base_id: str) -> Optional[int]:
    """从本地 base_id 字符串提取数字部分，作为远程 pigsty_id。"""
    match = re.search(r"(\d+)", str(base_id or ""))
    return int(match.group(1)) if match else None


def map_base_id_to_pigsty_id(base_id: str) -> Optional[int]:
    """本地 base_id → 远程 pigsty_id（优先走本地 base 表索引）。"""
    mapping = resolve_base_pigsty_mapping(base_id)
    if mapping:
        return mapping.pigsty_id
    return extract_pigsty_id_from_base_id(base_id)


def map_pigsty_id_to_base_id(pigsty_id: int) -> Optional[str]:
    """远程 pigsty_id → 本地 base_id。"""
    mapping = get_base_pigsty_mapper().get_by_pigsty_id(pigsty_id)
    return mapping.base_id if mapping else None


class BasePigstyMapper:
    """本地 base 表 base_id 与远程 environment_data.pigsty_id 的双向映射。"""

    def __init__(self) -> None:
        self._by_base_id: Dict[str, BasePigstyMapping] = {}
        self._by_pigsty_id: Dict[int, BasePigstyMapping] = {}
        self._load()

    def _load(self) -> None:
        for row in Base.objects.values(*BASE_INFO_FIELDS):
            base_id = str(row.get("base_id") or "").strip()
            if not base_id:
                continue

            pigsty_id = extract_pigsty_id_from_base_id(base_id)
            if pigsty_id is None:
                continue

            info = {field: row.get(field) for field in BASE_INFO_FIELDS}
            mapping = BasePigstyMapping(
                base_id=base_id,
                pigsty_id=pigsty_id,
                base_name=str(row.get("base_name") or base_id),
                info=info,
            )
            self._by_base_id[base_id] = mapping
            self._by_pigsty_id[pigsty_id] = mapping

    def get_by_base_id(self, base_id: str) -> Optional[BasePigstyMapping]:
        return self._by_base_id.get(str(base_id or "").strip())

    def get_by_pigsty_id(self, pigsty_id: int) -> Optional[BasePigstyMapping]:
        return self._by_pigsty_id.get(int(pigsty_id))

    def resolve(self, key: str) -> Optional[BasePigstyMapping]:
        """支持本地 base_id（如 HB001）或 pigsty_id 数字字符串（如 1）。"""
        normalized = str(key or "").strip()
        if not normalized:
            return None

        by_base = self.get_by_base_id(normalized)
        if by_base:
            return by_base

        if normalized.isdigit():
            return self.get_by_pigsty_id(int(normalized))

        pigsty_id = extract_pigsty_id_from_base_id(normalized)
        if pigsty_id is not None:
            return self.get_by_pigsty_id(pigsty_id)

        return None


@lru_cache(maxsize=1)
def get_base_pigsty_mapper() -> BasePigstyMapper:
    return BasePigstyMapper()


def resolve_base_pigsty_mapping(key: str) -> Optional[BasePigstyMapping]:
    """解析任意基地标识，返回本地 base 与远程 pigsty_id 的完整映射。"""
    return get_base_pigsty_mapper().resolve(key)


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _serialize_value(val) for key, val in record.items()}


def _unique_base_keys(base_ids: List[str]) -> List[str]:
    unique_keys: List[str] = []
    seen = set()
    for base_id in base_ids:
        key = str(base_id or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_keys.append(key)
    return unique_keys


def _build_base_info_item(mapping: Optional[BasePigstyMapping], raw_key: str) -> Dict[str, Any]:
    """构建单条本地 base 信息（不含环境数据）。"""
    item: Dict[str, Any] = {
        "base_id": mapping.base_id if mapping else raw_key,
        "base_name": mapping.base_name if mapping else raw_key,
        "pigsty_id": mapping.pigsty_id if mapping else map_base_id_to_pigsty_id(raw_key),
    }

    if mapping:
        for field in BASE_INFO_FIELDS:
            if field in ("base_id", "base_name"):
                continue
            value = mapping.info.get(field)
            if value is not None:
                item[field] = _serialize_value(value)
    elif item.get("pigsty_id") is None:
        item["error"] = "base_id 无法映射到 pigsty_id"

    return item


def _query_env_records(pigsty_id: int, cutoff) -> List[Dict[str, Any]]:
    rows = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=pigsty_id, collected_time__gte=cutoff)
        .order_by("collected_time", "id")
        .values(*ENV_VALUE_FIELDS)
    )
    return [_serialize_record(dict(row)) for row in rows]


def fetch_base_info(base_ids: List[str]) -> Dict[str, Any]:
    """查询并组装本地 base 表信息 JSON。"""
    mapper = get_base_pigsty_mapper()
    items: List[Dict[str, Any]] = []

    for raw_key in _unique_base_keys(base_ids):
        mapping = mapper.resolve(raw_key)
        items.append(_build_base_info_item(mapping, raw_key))

    return {
        "generated_at": timezone.now().isoformat(),
        "base_count": len(items),
        "bases": items,
    }


def fetch_env_data(base_ids: List[str], days: int = 3) -> Dict[str, Any]:
    """查询并组装远程 environment_data 环境信息 JSON。"""
    mapper = get_base_pigsty_mapper()
    cutoff = timezone.now() - timedelta(days=days)
    groups: List[Dict[str, Any]] = []
    total_records = 0

    for raw_key in _unique_base_keys(base_ids):
        mapping = mapper.resolve(raw_key)
        base_id = mapping.base_id if mapping else raw_key
        pigsty_id = mapping.pigsty_id if mapping else map_base_id_to_pigsty_id(raw_key)

        group: Dict[str, Any] = {
            "base_id": base_id,
            "pigsty_id": pigsty_id,
            "records": [],
        }

        if pigsty_id is None:
            group["error"] = "base_id 无法映射到 pigsty_id"
            groups.append(group)
            continue

        records = _query_env_records(int(pigsty_id), cutoff)
        group["records"] = records
        group["record_count"] = len(records)
        total_records += len(records)
        groups.append(group)

    return {
        "generated_at": timezone.now().isoformat(),
        "days": days,
        "base_count": len(groups),
        "record_count": total_records,
        "bases": groups,
    }


def get_recent_records(
    base_info: Dict[str, Any],
    env_data: Dict[str, Any],
    limit: Optional[int] = 30,
) -> List[Dict[str, Any]]:
    """合并 base 名称与环境记录，返回最近 N 条用于展示；limit 为 None 时返回全部。"""
    name_map = {
        str(item.get("base_id")): item.get("base_name")
        for item in (base_info.get("bases") or [])
        if item.get("base_id")
    }

    all_records: List[Dict[str, Any]] = []
    for group in env_data.get("bases") or []:
        base_id = group.get("base_id")
        pigsty_id = group.get("pigsty_id")
        base_name = name_map.get(str(base_id), base_id)
        for rec in group.get("records") or []:
            all_records.append(
                {
                    "base_id": base_id,
                    "base_name": base_name,
                    "pigsty_id": pigsty_id,
                    **rec,
                }
            )

    all_records.sort(key=lambda item: item.get("collected_time") or "", reverse=True)
    if limit is None:
        return all_records
    return all_records[:limit]


def get_base_info_data() -> Optional[Dict[str, Any]]:
    """获取内存中的本地 base 信息 JSON。"""
    return BASE_INFO_DATA


def get_base_env_data() -> Optional[Dict[str, Any]]:
    """获取内存中的远程环境信息 JSON。"""
    return BASE_ENV_DATA


def load_base_env_data(
    base_ids: List[str],
    days: int = 3,
    recent_limit: int = 30,
) -> Dict[str, Any]:
    """加载基地数据：base 信息与 environment 信息分别写入两个内存 JSON 变量。"""
    global BASE_INFO_DATA, BASE_ENV_DATA

    base_info = fetch_base_info(base_ids)
    env_data = fetch_env_data(base_ids, days=days)
    recent_records = get_recent_records(base_info, env_data, limit=recent_limit)

    BASE_INFO_DATA = base_info
    BASE_ENV_DATA = env_data

    return {
        "base_info": base_info,
        "env_data": env_data,
        "recent_records": recent_records,
        "base_count": base_info.get("base_count", 0),
        "record_count": env_data.get("record_count", 0),
        "days": days,
    }


# ---------------------------------------------------------------------------
# 公共 HTTP 辅助（各工具视图共用）
# ---------------------------------------------------------------------------

def parse_agent_request_json(request) -> Dict[str, Any]:
    return json.loads(request.body) if request.body else {}


def parse_agent_base_ids(
    data: Dict[str, Any], empty_error: str
) -> Tuple[Optional[List[str]], Optional[JsonResponse]]:
    base_ids = data.get("base_ids") or []
    if not isinstance(base_ids, list):
        return None, JsonResponse({"success": False, "error": "base_ids 格式无效"}, status=400)
    base_ids = [str(item).strip() for item in base_ids if str(item).strip()]
    if not base_ids:
        return None, JsonResponse({"success": False, "error": empty_error}, status=400)
    return base_ids, None


def parse_agent_days(data: Dict[str, Any], default: int = 3, max_days: int = 30) -> int:
    days = int(data.get("days") or default)
    return max(1, min(days, max_days))


# ---------------------------------------------------------------------------
# 工具：加载基地数据
# 步骤1（唯一）：根据勾选基地编号加载 base 信息与近 N 天环境数据
# ---------------------------------------------------------------------------

def load_base_data_step(
    base_ids: List[str],
    days: int = 3,
    recent_limit: int = 30,
) -> Dict[str, Any]:
    """【加载基地数据 · 步骤1】查询并缓存基地信息与近 N 天环境记录。"""
    return load_base_env_data(base_ids, days=days, recent_limit=recent_limit)


@csrf_exempt
@require_POST
def agent_load_base_data_view(request):
    """【加载基地数据 · 步骤1】HTTP 入口。"""
    try:
        data = parse_agent_request_json(request)
        base_ids, err = parse_agent_base_ids(data, "请先在总览矩阵中勾选至少一个基地")
        if err:
            return err

        result = load_base_data_step(base_ids, days=parse_agent_days(data), recent_limit=30)
        return JsonResponse(
            {
                "success": True,
                "base_info": result["base_info"],
                "env_data": result["env_data"],
                "recent_records": result["recent_records"],
                "base_count": result["base_count"],
                "record_count": result["record_count"],
                "days": result["days"],
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
