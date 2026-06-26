import copy
import json
from typing import Any, Dict, List, Optional

from aiModels.agent.tool.select_data import (
    get_base_info_data,
    get_base_env_data,
    get_recent_records,
    load_base_env_data,
)
from aiModels.agent.tool.storage_anylisis import (
    get_device_data,
    get_device_images,
    load_device_data,
)

# 运行情况分析是否已完成数据准备
RUN_ANALYSIS_READY: bool = False

# 运行情况分析使用的环境数据天数
RUN_ANALYSIS_DAYS = 3

# 页面展示与传给智能体的最近记录/图片条数
RUN_ANALYSIS_DISPLAY_LIMIT = 10

# 传给智能体的 JSON 载荷（prepare 时写入）
RUN_ANALYSIS_AGENT_PAYLOAD: Optional[Dict[str, Any]] = None

RUN_ANALYSIS_OUTPUT_REQUIREMENTS = [
    "运行情况总体判断（结合温湿度趋势与设备运行状态）",
    "环境指标趋势分析（各指标变化趋势、是否稳定、是否存在超限或异常波动）",
    "设备运行观察（在线/采集情况与数据完整性）",
    "风险与改进建议（运行调控、设备维护、监测频率）",
    "结论摘要（一句话总结当前贮藏效果等级：优/良/中/差，并说明依据）",
]


def _sanitize_device_data_for_agent(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """移除图片相关字段，不传给智能体。"""
    data = copy.deepcopy(device_data)
    for base in data.get("bases") or []:
        base.pop("latest_images", None)
    return data


def _limit_device_images(device_images: Dict[str, Any], limit: int) -> Dict[str, Any]:
    """截取最近 limit 张监控图用于页面展示。"""
    items = (device_images.get("items") or [])[:limit]
    return {
        **device_images,
        "items": items,
        "display_count": len(items),
    }


def _build_agent_payload(
    base_info: Dict[str, Any],
    env_data: Dict[str, Any],
    device_data: Dict[str, Any],
    record_limit: int = RUN_ANALYSIS_DISPLAY_LIMIT,
) -> Dict[str, Any]:
    """组装传给智能体的纯 JSON 数据（不含图片）。"""
    recent_records = get_recent_records(base_info, env_data, limit=record_limit)
    return {
        "task": "运行情况分析",
        "description": "基于基地信息、近3天环境监测数据与设备运行信息，评估贮藏库运行状态、环境变化趋势及贮藏效果。",
        "days": env_data.get("days", RUN_ANALYSIS_DAYS),
        "total_record_count": env_data.get("record_count", 0),
        "sample_record_count": len(recent_records),
        "output_requirements": RUN_ANALYSIS_OUTPUT_REQUIREMENTS,
        "base_info": base_info,
        "device_data": _sanitize_device_data_for_agent(device_data),
        "env_records": recent_records,
    }


def prepare_run_analysis_data(
    base_ids: List[str],
    days: int = RUN_ANALYSIS_DAYS,
) -> Dict[str, Any]:
    """步骤1：加载基地信息、近3天环境数据、device 信息；页面与智能体均仅用最近 N 条。"""
    global RUN_ANALYSIS_READY, RUN_ANALYSIS_AGENT_PAYLOAD

    if not base_ids:
        raise ValueError("请先在主页或大屏勾选至少一个基地")

    base_result = load_base_env_data(base_ids, days=days, recent_limit=RUN_ANALYSIS_DISPLAY_LIMIT)
    device_data, device_images = load_device_data(base_ids)
    display_records = get_recent_records(
        base_result["base_info"],
        base_result["env_data"],
        limit=RUN_ANALYSIS_DISPLAY_LIMIT,
    )
    display_images = _limit_device_images(device_images, RUN_ANALYSIS_DISPLAY_LIMIT)

    RUN_ANALYSIS_AGENT_PAYLOAD = _build_agent_payload(
        base_result["base_info"],
        base_result["env_data"],
        device_data,
    )
    RUN_ANALYSIS_READY = True

    return {
        "base_info": base_result["base_info"],
        "env_data": base_result["env_data"],
        "recent_records": display_records,
        "device_data": device_data,
        "device_images": display_images,
        "base_count": base_result["base_count"],
        "record_count": base_result["record_count"],
        "display_record_count": len(display_records),
        "device_count": device_data.get("device_count", 0),
        "image_count": device_images.get("image_count", 0),
        "display_image_count": display_images.get("display_count", 0),
        "days": base_result["days"],
        "display_limit": RUN_ANALYSIS_DISPLAY_LIMIT,
    }


def is_run_analysis_ready() -> bool:
    base_info = get_base_info_data()
    env_data = get_base_env_data()
    device_data = get_device_data()
    return (
        RUN_ANALYSIS_READY
        and RUN_ANALYSIS_AGENT_PAYLOAD is not None
        and base_info is not None
        and env_data is not None
        and device_data is not None
    )


def build_run_analysis_prompt() -> str:
    """将运行情况分析数据以纯 JSON 字符串交给智能体。"""
    if not is_run_analysis_ready() or RUN_ANALYSIS_AGENT_PAYLOAD is None:
        raise ValueError("请先点击「运行情况分析」完成数据加载")

    return json.dumps(RUN_ANALYSIS_AGENT_PAYLOAD, ensure_ascii=False)


def get_run_analysis_status() -> Dict[str, Any]:
    base_info = get_base_info_data()
    env_data = get_base_env_data()
    device_data = get_device_data()
    device_images = get_device_images()
    return {
        "ready": is_run_analysis_ready(),
        "base_count": (base_info or {}).get("base_count", 0),
        "record_count": (env_data or {}).get("record_count", 0),
        "device_count": (device_data or {}).get("device_count", 0),
        "image_count": (device_images or {}).get("image_count", 0),
        "display_limit": RUN_ANALYSIS_DISPLAY_LIMIT,
    }
