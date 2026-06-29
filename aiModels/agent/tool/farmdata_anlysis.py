import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from aiModels.agent.brain_agent import create_agent_sse_response, resolve_model_config

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PAST_DAYS = 3
FORECAST_DAYS = 16

# 采摘入库分析：已选种植地点与天气数据
HARVEST_ANALYSIS_LOCATION: Optional[Dict[str, float]] = None
HARVEST_ANALYSIS_WEATHER: Optional[Dict[str, Any]] = None

HARVEST_ANALYSIS_PROMPT_TEMPLATE = """请作为华中农业大学 AIoT 团队的柑橘采后贮藏专家，基于以下数据进行「采摘入库分析」并生成报告。

## 分析任务
结合种植地点、过去 3 天与未来 16 天天气预报，以及用户提供的种植品种、种植时间等信息，给出专业、可操作的采摘与入库建议。

## 种植地点
{location_json}

## 天气预报数据（Open-Meteo，含过去 {past_days} 天与未来 {forecast_days} 天）
{weather_json}

## 用户补充信息（品种、种植时间、成熟度、计划产量等）
{user_input}

## 输出要求
请用中文输出，结构清晰，包含：
1. **推荐采摘时间**（结合未来天气窗口，说明适宜/不宜采摘的时段及原因）
2. **推荐入库时间**（采摘后何时入库、预冷与褪绿安排）
3. **贮藏环境设置**（温度、湿度、通风等具体参数与调控要点）
4. **风险提示**（极端天气、高湿、霜冻、连续降雨等对采后品质的影响）

基于已有信息给出保守建议。"""


def weather_code_to_zh(code: Any) -> str:
    """Open-Meteo WMO 天气代码 → 中文（与 base_dashboard.html 一致）。"""
    if code is None:
        return "—"
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "—"

    mapping = {
        0: "晴",
        1: "晴",
        2: "多云",
        3: "阴",
        45: "雾",
        48: "雾凇",
        51: "小毛毛雨",
        53: "中毛毛雨",
        55: "大毛毛雨",
        56: "冻毛毛雨",
        57: "冻毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        66: "冻雨",
        67: "冻雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        77: "雪粒",
        80: "小阵雨",
        81: "阵雨",
        82: "强阵雨",
        85: "小阵雪",
        86: "阵雪",
        95: "雷阵雨",
        96: "雷阵雨伴冰雹",
        97: "强雷阵雨",
        99: "强雷阵雨伴冰雹",
    }
    if c in mapping:
        return mapping[c]
    if 51 <= c <= 55:
        return "毛毛雨"
    if 61 <= c <= 67:
        return "雨"
    if 71 <= c <= 77:
        return "雪"
    if 80 <= c <= 82:
        return "阵雨"
    if 85 <= c <= 86:
        return "阵雪"
    if 95 <= c <= 99:
        return "雷暴"
    return "未知"


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values: List[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _build_daily_summary(hourly: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按日汇总 hourly 数据，便于图表展示与 agent 提示词。"""
    times: List[str] = hourly.get("time") or []
    temps: List[Any] = hourly.get("temperature_2m") or []
    rh: List[Any] = hourly.get("relative_humidity_2m") or []
    et: List[Any] = hourly.get("evapotranspiration") or []
    clouds: List[Any] = hourly.get("cloud_cover") or []
    codes: List[Any] = hourly.get("weather_code") or []

    buckets: Dict[str, Dict[str, List[Any]]] = {}
    for i, t in enumerate(times):
        day = str(t)[:10]
        if day not in buckets:
            buckets[day] = {
                "temperature_2m": [],
                "relative_humidity_2m": [],
                "evapotranspiration": [],
                "cloud_cover": [],
                "weather_code": [],
            }
        for key, src in (
            ("temperature_2m", temps),
            ("relative_humidity_2m", rh),
            ("evapotranspiration", et),
            ("cloud_cover", clouds),
            ("weather_code", codes),
        ):
            if i < len(src):
                buckets[day][key].append(src[i])

    daily: List[Dict[str, Any]] = []
    for day in sorted(buckets.keys()):
        b = buckets[day]
        t_vals = [_safe_float(v) for v in b["temperature_2m"]]
        rh_vals = [_safe_float(v) for v in b["relative_humidity_2m"]]
        et_vals = [_safe_float(v) for v in b["evapotranspiration"]]
        cloud_vals = [_safe_float(v) for v in b["cloud_cover"]]
        code_vals = [v for v in b["weather_code"] if v is not None]

        dominant_code = None
        if code_vals:
            dominant_code = max(set(code_vals), key=lambda x: code_vals.count(x))

        t_min = min((v for v in t_vals if v is not None), default=None)
        t_max = max((v for v in t_vals if v is not None), default=None)

        daily.append(
            {
                "date": day,
                "temperature_min": round(t_min, 1) if t_min is not None else None,
                "temperature_max": round(t_max, 1) if t_max is not None else None,
                "temperature_avg": round(_avg(t_vals), 1) if _avg(t_vals) is not None else None,
                "relative_humidity_avg": round(_avg(rh_vals), 0) if _avg(rh_vals) is not None else None,
                "evapotranspiration_sum": round(sum(v for v in et_vals if v is not None), 2)
                if any(v is not None for v in et_vals)
                else None,
                "cloud_cover_avg": round(_avg(cloud_vals), 0) if _avg(cloud_vals) is not None else None,
                "weather_code_dominant": dominant_code,
                "weather_code_zh": weather_code_to_zh(dominant_code),
            }
        )
    return daily


def fetch_open_meteo_weather(
    latitude: float,
    longitude: float,
    past_days: int = PAST_DAYS,
    forecast_days: int = FORECAST_DAYS,
) -> Dict[str, Any]:
    """请求 Open-Meteo Forecast API。"""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,et0_fao_evapotranspiration,cloud_cover,weather_code",
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "auto",
    }
    resp = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def process_weather_for_display(raw: Dict[str, Any]) -> Dict[str, Any]:
    """整理 Open-Meteo 原始响应，供前端图表与 agent 使用。"""
    hourly_raw = raw.get("hourly") or {}
    times: List[str] = hourly_raw.get("time") or []
    codes: List[Any] = hourly_raw.get("weather_code") or []

    hourly = {
        "time": times,
        "temperature_2m": hourly_raw.get("temperature_2m") or [],
        "relative_humidity_2m": hourly_raw.get("relative_humidity_2m") or [],
        "evapotranspiration": hourly_raw.get("et0_fao_evapotranspiration") or [],
        "cloud_cover": hourly_raw.get("cloud_cover") or [],
        "weather_code": codes,
        "weather_code_zh": [weather_code_to_zh(c) for c in codes],
    }

    daily = _build_daily_summary(hourly)
    today_str = datetime.now().strftime("%Y-%m-%d")

    return {
        "generated_at": timezone.now().isoformat(),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "timezone": raw.get("timezone"),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "hourly": hourly,
        "daily": daily,
        "today": today_str,
    }


def reset_harvest_analysis_state() -> None:
    """重置采摘入库分析内存状态。"""
    global HARVEST_ANALYSIS_LOCATION, HARVEST_ANALYSIS_WEATHER
    HARVEST_ANALYSIS_LOCATION = None
    HARVEST_ANALYSIS_WEATHER = None


def load_harvest_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """步骤2：保存种植地点并拉取 Open-Meteo 天气。"""
    global HARVEST_ANALYSIS_LOCATION, HARVEST_ANALYSIS_WEATHER

    lat = float(latitude)
    lng = float(longitude)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise ValueError("经纬度超出有效范围")

    HARVEST_ANALYSIS_LOCATION = {"latitude": lat, "longitude": lng}
    raw = fetch_open_meteo_weather(lat, lng)
    processed = process_weather_for_display(raw)
    HARVEST_ANALYSIS_WEATHER = processed
    return processed


def is_harvest_analysis_ready() -> bool:
    """是否已完成地点选择与天气加载。"""
    return HARVEST_ANALYSIS_LOCATION is not None and HARVEST_ANALYSIS_WEATHER is not None


def get_harvest_analysis_status() -> Dict[str, Any]:
    """返回当前采摘入库分析数据就绪状态。"""
    return {
        "ready": is_harvest_analysis_ready(),
        "location": HARVEST_ANALYSIS_LOCATION,
        "weather_generated_at": (HARVEST_ANALYSIS_WEATHER or {}).get("generated_at"),
    }


def _weather_for_prompt() -> Dict[str, Any]:
    """压缩天气数据供 LLM 使用（日汇总 + 每 6 小时采样）。"""
    weather = HARVEST_ANALYSIS_WEATHER or {}
    hourly = weather.get("hourly") or {}
    times: List[str] = hourly.get("time") or []

    sampled: List[Dict[str, Any]] = []
    for i, t in enumerate(times):
        if i % 6 != 0:
            continue
        sampled.append(
            {
                "time": t,
                "temperature_2m": (hourly.get("temperature_2m") or [None])[i]
                if i < len(hourly.get("temperature_2m") or [])
                else None,
                "relative_humidity_2m": (hourly.get("relative_humidity_2m") or [None])[i]
                if i < len(hourly.get("relative_humidity_2m") or [])
                else None,
                "evapotranspiration": (hourly.get("evapotranspiration") or [None])[i]
                if i < len(hourly.get("evapotranspiration") or [])
                else None,
                "cloud_cover": (hourly.get("cloud_cover") or [None])[i]
                if i < len(hourly.get("cloud_cover") or [])
                else None,
                "weather_code_zh": (hourly.get("weather_code_zh") or ["—"])[i]
                if i < len(hourly.get("weather_code_zh") or [])
                else "—",
            }
        )

    return {
        "timezone": weather.get("timezone"),
        "past_days": weather.get("past_days"),
        "forecast_days": weather.get("forecast_days"),
        "daily_summary": weather.get("daily") or [],
        "hourly_sampled_every_6h": sampled,
    }


def build_harvest_analysis_prompt(user_input: str) -> str:
    """步骤4：汇聚地点、天气与用户输入，生成 agent 分析提示词。"""
    user_input = (user_input or "").strip()
    if not user_input:
        raise ValueError("请输入种植品种、种植时间等信息")

    if not is_harvest_analysis_ready():
        raise ValueError("请先在地图上选择种植地点并完成天气查询")

    location_json = json.dumps(HARVEST_ANALYSIS_LOCATION, ensure_ascii=False, indent=2)
    weather_json = json.dumps(_weather_for_prompt(), ensure_ascii=False, indent=2)

    return HARVEST_ANALYSIS_PROMPT_TEMPLATE.format(
        location_json=location_json,
        weather_json=weather_json,
        user_input=user_input,
        past_days=PAST_DAYS,
        forecast_days=FORECAST_DAYS,
    )


def _run_agent_with_prompt(session_id: str, prompt: str, data: Dict[str, Any]):
    model_config = resolve_model_config(data)
    return create_agent_sse_response(session_id, prompt, model_config=model_config)


# ---------------------------------------------------------------------------
# 工具：采摘入库分析
# 步骤1：重置流程，引导用户在地图选择种植地点
# 步骤2：根据经纬度拉取 Open-Meteo 天气（过去 3 天 + 未来 16 天）
# 步骤3：（前端）用户补充种植品种、种植时间等信息
# 步骤4：汇聚地点、天气与用户输入，调用 agent 生成采摘入库报告
# ---------------------------------------------------------------------------

def harvest_analysis_step1_start() -> None:
    """【采摘入库分析 · 步骤1】重置内存状态，准备选择种植地点。"""
    reset_harvest_analysis_state()


def harvest_analysis_step2_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """【采摘入库分析 · 步骤2】保存种植地点并拉取 Open-Meteo 天气预报。"""
    return load_harvest_weather(latitude, longitude)


def harvest_analysis_step4_run(user_input: str) -> str:
    """【采摘入库分析 · 步骤4】汇聚地点、天气与用户输入，生成 agent 分析提示词。"""
    return build_harvest_analysis_prompt(user_input)


@csrf_exempt
@require_POST
def agent_harvest_analysis_start_view(request):
    """【采摘入库分析 · 步骤1】HTTP 入口。"""
    try:
        harvest_analysis_step1_start()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def agent_harvest_analysis_weather_view(request):
    """【采摘入库分析 · 步骤2】HTTP 入口。"""
    try:
        data = json.loads(request.body) if request.body else {}
        lat = data.get("latitude")
        lng = data.get("longitude")
        if lat is None or lng is None:
            return JsonResponse({"success": False, "error": "缺少 latitude 或 longitude"}, status=400)

        weather = harvest_analysis_step2_weather(float(lat), float(lng))
        return JsonResponse(
            {
                "success": True,
                "location": {"latitude": float(lat), "longitude": float(lng)},
                "weather": weather,
            }
        )
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def agent_harvest_analysis_run_view(request):
    """【采摘入库分析 · 步骤4】HTTP 入口。"""
    try:
        data = json.loads(request.body) if request.body else {}
        session_id = data.get("session_id")
        user_input = (data.get("message") or data.get("user_input") or "").strip()
        if not session_id:
            return JsonResponse({"success": False, "error": "缺少 session_id"}, status=400)
        if not user_input:
            return JsonResponse({"success": False, "error": "请输入种植品种、种植时间等信息"}, status=400)

        prompt = harvest_analysis_step4_run(user_input)
        return _run_agent_with_prompt(session_id, prompt, data)
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
