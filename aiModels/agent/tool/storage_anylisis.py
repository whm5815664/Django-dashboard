import json
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from aiModels.agent.tool.select_data import (
    _unique_base_keys,
    get_base_env_data,
    get_base_info_data,
    load_base_env_data,
    resolve_base_pigsty_mapping,
)
from screen.models import EnvironmentData
from storageSystem.models import Device

# 贮藏环境分析：是否已完成步骤1（基地数据已加载）
STORAGE_ANALYSIS_READY: bool = False

# 远程 device 表与设备最新监控图（运行情况分析使用）
BASE_DEVICE_DATA: Optional[Dict[str, Any]] = None
BASE_DEVICE_IMAGES: Optional[Dict[str, Any]] = None

DEVICE_FIELDS = (
    "id",
    "name",
    "device_code",
    "description",
    "collect_interval",
    "created_at",
    "updated_at",
)

STORAGE_ANALYSIS_PROMPT_TEMPLATE = """请作为华中农业大学 AIoT 团队的柑橘采后贮藏专家，基于以下数据进行「贮藏环境分析」并生成报告。

## 分析任务
结合基地信息、近 3 天环境监测数据，以及用户补充的贮藏柑橘品种与需求，给出专业、可操作的贮藏环境评估与调控建议。

## 基地信息（本地 base 表）
{base_info_json}

## 近 3 天环境检测数据（远程 environment_data，按 pigsty_id 关联）
{env_data_json}

## 用户补充信息
{user_input}

## 输出要求
请用中文输出，结构清晰，包含：
1. **环境总体评价**（温湿度及主要气体指标是否适宜贮藏）
2. **主要风险点**（异常波动、超限趋势、品种相关风险）
3. **调控建议**（具体可执行的调温、调湿、通风等措施）
4. **后续监测建议**（需重点关注的指标与频率）

若数据不足，请明确指出缺失项，并基于已有信息给出保守建议。"""


def prepare_storage_analysis_data(
    base_ids: List[str],
    days: int = 3,
    recent_limit: int = 30,
) -> Dict[str, Any]:
    """步骤1：加载选中基地的 base 信息与近 N 天环境数据。"""
    global STORAGE_ANALYSIS_READY

    if not base_ids:
        raise ValueError("请先在主页或大屏勾选至少一个基地")

    result = load_base_env_data(base_ids, days=days, recent_limit=recent_limit)
    STORAGE_ANALYSIS_READY = True
    return result


def is_storage_analysis_ready() -> bool:
    """是否已完成贮藏分析所需的数据准备。"""
    return STORAGE_ANALYSIS_READY and get_base_info_data() is not None and get_base_env_data() is not None


def build_storage_analysis_prompt(user_input: str) -> str:
    """步骤3：将环境 JSON 与用户输入组合为 agent 分析提示词。"""
    user_input = (user_input or "").strip()
    if not user_input:
        raise ValueError("请输入贮藏的柑橘品种及分析需求")

    base_info = get_base_info_data()
    env_data = get_base_env_data()
    if not is_storage_analysis_ready() or not base_info or not env_data:
        raise ValueError("请先点击「贮藏环境分析」或「加载基地数据」完成基地数据加载")

    base_info_json = json.dumps(base_info, ensure_ascii=False, indent=2)
    env_data_json = json.dumps(env_data, ensure_ascii=False, indent=2)

    return STORAGE_ANALYSIS_PROMPT_TEMPLATE.format(
        base_info_json=base_info_json,
        env_data_json=env_data_json,
        user_input=user_input,
    )


def get_storage_analysis_status() -> Dict[str, Any]:
    """返回当前贮藏分析数据就绪状态。"""
    base_info = get_base_info_data()
    env_data = get_base_env_data()
    return {
        "ready": is_storage_analysis_ready(),
        "base_count": (base_info or {}).get("base_count", 0),
        "record_count": (env_data or {}).get("record_count", 0),
    }


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _serialize_value(val) for key, val in record.items()}


def build_media_proxy_url(image_path: str) -> str:
    """将 environment_data.image 转为前端可访问 URL。"""
    path = str(image_path or "").strip().lstrip("/")
    return f"/media-proxy/{path}" if path else ""


def fetch_devices_by_pigsty_id(pigsty_id: int) -> List[Dict[str, Any]]:
    """查询指定 pigsty_id 在 environment_data 中出现过的 device 记录。"""
    device_ids = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=pigsty_id)
        .values_list("device_id", flat=True)
        .distinct()
    )
    ids = [int(did) for did in device_ids if did is not None]
    if not ids:
        return []

    rows = (
        Device.objects.using("pig")
        .filter(id__in=ids)
        .values(*DEVICE_FIELDS)
        .order_by("id")
    )
    return [_serialize_record(dict(row)) for row in rows]


def fetch_latest_device_images_by_pigsty_id(
    pigsty_id: int,
    base_id: str,
    base_name: str,
) -> List[Dict[str, Any]]:
    """每个设备各取 environment_data 中最近一张监控图片。"""
    device_rows = fetch_devices_by_pigsty_id(pigsty_id)
    device_map = {int(item["id"]): item for item in device_rows if item.get("id") is not None}
    images: List[Dict[str, Any]] = []

    for device_id in device_map.keys():
        row = (
            EnvironmentData.objects.using("pig")
            .filter(pigsty_id=pigsty_id, device_id=device_id)
            .exclude(image__isnull=True)
            .exclude(image="")
            .order_by("-collected_time", "-id")
            .values("device_id", "image", "collected_time")
            .first()
        )
        if not row:
            continue
        image_path = str(row.get("image") or "").strip()
        if not image_path:
            continue

        dev = device_map.get(int(device_id), {})
        images.append(
            {
                "base_id": base_id,
                "base_name": base_name,
                "pigsty_id": pigsty_id,
                "device_id": device_id,
                "device_name": dev.get("name") or f"设备{device_id}",
                "device_code": dev.get("device_code"),
                "image_path": image_path,
                "image_url": build_media_proxy_url(image_path),
                "collected_time": _serialize_value(row.get("collected_time")),
            }
        )

    images.sort(key=lambda item: item.get("collected_time") or "", reverse=True)
    return images


def fetch_device_data_for_bases(base_ids: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """按基地汇总远程 device 表信息与各设备最新监控图。"""
    base_groups: List[Dict[str, Any]] = []
    all_images: List[Dict[str, Any]] = []
    total_devices = 0

    for raw_key in _unique_base_keys(base_ids):
        mapping = resolve_base_pigsty_mapping(raw_key)
        if not mapping:
            continue

        devices = fetch_devices_by_pigsty_id(mapping.pigsty_id)
        images = fetch_latest_device_images_by_pigsty_id(
            mapping.pigsty_id,
            mapping.base_id,
            mapping.base_name,
        )
        total_devices += len(devices)
        all_images.extend(images)
        base_groups.append(
            {
                "base_id": mapping.base_id,
                "base_name": mapping.base_name,
                "pigsty_id": mapping.pigsty_id,
                "devices": devices,
                "device_count": len(devices),
                "latest_images": images,
            }
        )

    device_data = {
        "generated_at": timezone.now().isoformat(),
        "base_count": len(base_groups),
        "device_count": total_devices,
        "bases": base_groups,
    }
    device_images = {
        "generated_at": timezone.now().isoformat(),
        "image_count": len(all_images),
        "items": all_images,
    }
    return device_data, device_images


def load_device_data(base_ids: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """加载 device 信息并写入内存 JSON 变量。"""
    global BASE_DEVICE_DATA, BASE_DEVICE_IMAGES

    device_data, device_images = fetch_device_data_for_bases(base_ids)
    BASE_DEVICE_DATA = device_data
    BASE_DEVICE_IMAGES = device_images
    return device_data, device_images


def get_device_data() -> Optional[Dict[str, Any]]:
    """获取内存中的 device 信息 JSON。"""
    return BASE_DEVICE_DATA


def get_device_images() -> Optional[Dict[str, Any]]:
    """获取内存中的设备最新监控图 JSON。"""
    return BASE_DEVICE_IMAGES
