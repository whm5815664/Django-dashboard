"""
全国省份气象监测模块 - 基于 OpenWeatherMap API
https://openweathermap.org/

提供省份实时天气查询、全国省份温度概览（地图着色）及监控接口。
"""

import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from screen.tool.weather_api import API_KEY, BASE_URL, PROVINCE_CITIES

FORECAST_URL = "http://api.openweathermap.org/data/2.5/forecast"

# 全国省份气象全量缓存：province -> {data, forecast}
_all_provinces_cache: Dict[str, Any] = {
    "provinces": {},
    "overview": [],
    "timestamp": 0,
    "update_time": None,
}

# 风向角度转中文
_WIND_DIRS = [
    "北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南",
    "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北",
]


def _wind_direction(deg: Optional[float]) -> str:
    if deg is None:
        return "—"
    idx = int((deg + 11.25) / 22.5) % 16
    return _WIND_DIRS[idx]


def _format_weather(raw: dict, province_name: str) -> Dict[str, Any]:
    """将 OpenWeatherMap 原始响应格式化为前端结构。"""
    main = raw.get("main", {})
    weather = (raw.get("weather") or [{}])[0]
    wind = raw.get("wind", {})
    icon = weather.get("icon", "01d")
    city_info = PROVINCE_CITIES.get(province_name, {})

    return {
        "province": province_name,
        "city": city_info.get("name", ""),
        "temperature": round(main.get("temp", 0), 1),
        "feels_like": round(main.get("feels_like", 0), 1),
        "temp_min": round(main.get("temp_min", 0), 1),
        "temp_max": round(main.get("temp_max", 0), 1),
        "humidity": main.get("humidity", 0),
        "pressure": main.get("pressure", 0),
        "description": weather.get("description", ""),
        "weather_main": weather.get("main", ""),
        "icon": icon,
        "icon_url": f"https://openweathermap.org/img/wn/{icon}@2x.png",
        "wind_speed": round(wind.get("speed", 0), 1),
        "wind_deg": wind.get("deg"),
        "wind_direction": _wind_direction(wind.get("deg")),
        "visibility": raw.get("visibility", 0),
        "clouds": (raw.get("clouds") or {}).get("all", 0),
        "rainfall_1h": round(float((raw.get("rain") or {}).get("1h") or 0), 1),
        "sunrise": raw.get("sys", {}).get("sunrise"),
        "sunset": raw.get("sys", {}).get("sunset"),
        "timestamp": int(time.time()),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_province_weather(province_name: str) -> Optional[Dict[str, Any]]:
    """根据省份名称获取实时天气。"""
    city_info = PROVINCE_CITIES.get(province_name)
    if not city_info:
        return None

    url = (
        f"{BASE_URL}?lat={city_info['lat']}&lon={city_info['lon']}"
        f"&appid={API_KEY}&units=metric&lang=zh_cn"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[weather_province] API 失败 {province_name}: {response.status_code}")
            return None
        return _format_weather(response.json(), province_name)
    except Exception as exc:
        print(f"[weather_province] 请求异常 {province_name}: {exc}")
        return None


def _aggregate_forecast_slots(slot_list: List[dict]) -> Optional[Dict[str, Any]]:
    """聚合若干 3 小时预报时段。"""
    if not slot_list:
        return None
    temps = [s["main"]["temp"] for s in slot_list]
    hums = [s["main"]["humidity"] for s in slot_list]
    mid = slot_list[len(slot_list) // 2]
    weather = (mid.get("weather") or [{}])[0]
    wind = mid.get("wind", {})
    icon = weather.get("icon", "01d")
    return {
        "temp": round(sum(temps) / len(temps), 1),
        "humidity": round(sum(hums) / len(hums)),
        "description": weather.get("description", ""),
        "icon": icon,
        "icon_url": f"https://openweathermap.org/img/wn/{icon}@2x.png",
        "wind_speed": round(wind.get("speed", 0), 1),
        "wind_direction": _wind_direction(wind.get("deg")),
    }


def _calc_rainfall_24h(forecast_list: List[dict]) -> float:
    """汇总未来 24 小时预报降水量（mm）。"""
    now_ts = time.time()
    end_ts = now_ts + 24 * 3600
    total = 0.0
    for item in forecast_list:
        dt = item.get("dt", 0)
        if dt < now_ts:
            continue
        if dt > end_ts:
            break
        rain = item.get("rain") or {}
        total += float(rain.get("3h") or rain.get("1h") or 0)
    return round(total, 1)


def _build_forecasts_from_list(forecast_list: List[dict], days: int = 3) -> List[Dict[str, Any]]:
    """从预报原始列表构建按天聚合的预报结构。"""
    day_buckets: Dict[str, List[tuple]] = defaultdict(list)
    for item in forecast_list:
        dt = datetime.fromtimestamp(item["dt"])
        day_buckets[dt.strftime("%Y-%m-%d")].append((dt.hour, item))

    today = datetime.now().strftime("%Y-%m-%d")
    target_dates = sorted(d for d in day_buckets if d >= today)[:days]

    forecasts: List[Dict[str, Any]] = []
    for date_key in target_dates:
        slots = day_buckets[date_key]
        day_slots = [s for h, s in slots if 6 <= h < 18]
        night_slots = [s for h, s in slots if h < 6 or h >= 18]
        if not day_slots:
            day_slots = slots[: max(1, len(slots) // 2 + 1)]
        if not night_slots:
            night_slots = slots[len(slots) // 2 :] or slots

        day_agg = _aggregate_forecast_slots(day_slots)
        night_agg = _aggregate_forecast_slots(night_slots)

        def _slot_field(agg, field, default="—"):
            return agg.get(field, default) if agg else default

        forecasts.append({
            "date": date_key,
            "dayWeather": _slot_field(day_agg, "description"),
            "dayTemp": _slot_field(day_agg, "temp"),
            "dayHumidity": _slot_field(day_agg, "humidity"),
            "dayWindDir": _slot_field(day_agg, "wind_direction"),
            "dayWindSpeed": _slot_field(day_agg, "wind_speed"),
            "dayIconUrl": _slot_field(day_agg, "icon_url", ""),
            "nightWeather": _slot_field(night_agg, "description"),
            "nightTemp": _slot_field(night_agg, "temp"),
            "nightHumidity": _slot_field(night_agg, "humidity"),
            "nightWindDir": _slot_field(night_agg, "wind_direction"),
            "nightWindSpeed": _slot_field(night_agg, "wind_speed"),
            "nightIconUrl": _slot_field(night_agg, "icon_url", ""),
        })
    return forecasts


def fetch_province_forecast_bundle(province_name: str, days: int = 3) -> Dict[str, Any]:
    """获取省份预报及 24 小时降水量。"""
    city_info = PROVINCE_CITIES.get(province_name)
    if not city_info:
        return {"forecasts": [], "rainfall_24h": 0.0}

    url = (
        f"{FORECAST_URL}?lat={city_info['lat']}&lon={city_info['lon']}"
        f"&appid={API_KEY}&units=metric&lang=zh_cn"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[weather_province] 预报 API 失败 {province_name}: {response.status_code}")
            return {"forecasts": [], "rainfall_24h": 0.0}

        forecast_list = response.json().get("list", [])
        return {
            "forecasts": _build_forecasts_from_list(forecast_list, days),
            "rainfall_24h": _calc_rainfall_24h(forecast_list),
        }
    except Exception as exc:
        print(f"[weather_province] 预报请求异常 {province_name}: {exc}")
        return {"forecasts": [], "rainfall_24h": 0.0}


def fetch_province_forecast(province_name: str, days: int = 3) -> List[Dict[str, Any]]:
    """获取省份未来若干天预报（OpenWeatherMap 5 day / 3 hour）。"""
    return fetch_province_forecast_bundle(province_name, days)["forecasts"]


def _build_overview_item(province_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": province_name,
        "value": data["temperature"],
        "humidity": data["humidity"],
        "rainfall": data.get("rainfall_24h", 0),
        "description": data["description"],
        "icon": data["icon"],
        "icon_url": data["icon_url"],
    }


def fetch_all_provinces_weather(force_refresh: bool = False) -> Dict[str, Any]:
    """获取全部省份实时天气 + 3 天预报，并保存到模块变量。"""
    global _all_provinces_cache

    if (
        not force_refresh
        and _all_provinces_cache["provinces"]
        and _all_provinces_cache["overview"]
    ):
        return _all_provinces_cache

    provinces: Dict[str, Dict[str, Any]] = {}
    overview: List[Dict[str, Any]] = []

    for province_name in PROVINCE_CITIES:
        data = fetch_province_weather(province_name)
        if not data:
            continue
        bundle = fetch_province_forecast_bundle(province_name)
        data["rainfall_24h"] = bundle["rainfall_24h"]
        provinces[province_name] = {"data": data, "forecast": bundle["forecasts"]}
        overview.append(_build_overview_item(province_name, data))

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _all_provinces_cache = {
        "provinces": provinces,
        "overview": overview,
        "timestamp": int(time.time()),
        "update_time": update_time,
    }
    print(f"[weather_province] 已缓存 {len(provinces)} 个省份气象数据")
    return _all_provinces_cache


def fetch_all_provinces_overview(use_cache: bool = True) -> List[Dict[str, Any]]:
    """获取全部省份温度概览，供地图 visualMap 着色。"""
    cache = fetch_all_provinces_weather(force_refresh=not use_cache)
    return cache["overview"]


def get_cached_province_weather(province_name: str) -> Optional[Dict[str, Any]]:
    """从模块变量读取单省缓存。"""
    item = _all_provinces_cache.get("provinces", {}).get(province_name)
    return item if item else None


def get_province_list() -> List[str]:
    """返回支持的省份列表。"""
    return list(PROVINCE_CITIES.keys())


# ---------- Django 视图 ----------

@csrf_exempt
@require_GET
def get_province_weather_view(request):
    """GET /weather/province/?province=湖北"""
    province = request.GET.get("province", "").strip()
    if not province:
        return JsonResponse({"success": False, "error": "请提供 province 参数"}, status=400)

    refresh = request.GET.get("refresh", "") == "1"
    if not refresh:
        cached = get_cached_province_weather(province)
        if cached:
            return JsonResponse({
                "success": True,
                "data": cached["data"],
                "forecast": cached.get("forecast", []),
                "from_cache": True,
            })

    data = fetch_province_weather(province)
    if not data:
        return JsonResponse(
            {"success": False, "error": f"未找到省份「{province}」或 API 请求失败"},
            status=404,
        )
    bundle = fetch_province_forecast_bundle(province)
    data["rainfall_24h"] = bundle["rainfall_24h"]
    return JsonResponse({
        "success": True,
        "data": data,
        "forecast": bundle["forecasts"],
        "from_cache": False,
    })


@csrf_exempt
@require_GET
def get_all_provinces_weather_view(request):
    """GET /weather/provinces/  全国省份气象全量数据（含预报）"""
    refresh = request.GET.get("refresh", "") == "1"
    try:
        cache = fetch_all_provinces_weather(force_refresh=refresh)
        return JsonResponse({
            "success": True,
            "data": cache["overview"],
            "provinces": cache["provinces"],
            "provinces_list": get_province_list(),
            "count": len(cache["provinces"]),
            "update_time": cache["update_time"],
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_province_list_view(request):
    """GET /weather/province_list/  支持的省份及坐标"""
    items = [
        {"province": name, **info}
        for name, info in PROVINCE_CITIES.items()
    ]
    return JsonResponse({"success": True, "data": items})
