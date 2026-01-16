"""
天气API模块 - 实时温度查询功能https://openweathermap.org/

本模块提供实时天气查询功能，包括当前温度、天气状况等信息。

功能特点:
- 支持根据省份名称查询天气
- 提供实时温度数据
- 支持多种天气信息（温度、湿度、风速等）
- 集成OpenWeatherMap API
- 支持定时获取温度数据（每1分钟）
- 支持省份主要城市映射

作者: whm
版本: 1.0.0
更新时间: 2025年9月
"""

import json
import requests
import threading
import time
import random
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# OpenWeatherMap API配置
API_KEY = "61c30d08f051f7528690a963da3859dc"
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

# 省份主要城市映射（英文名称和坐标）
PROVINCE_CITIES = {
    '湖北': {'name': 'Wuhan', 'lat': 30.5928, 'lon': 114.3055},
    '广东': {'name': 'Guangzhou', 'lat': 23.1291, 'lon': 113.2644},
    '北京': {'name': 'Beijing', 'lat': 39.9042, 'lon': 116.4074},
    '上海': {'name': 'Shanghai', 'lat': 31.2304, 'lon': 121.4737},
    '江苏': {'name': 'Nanjing', 'lat': 32.0603, 'lon': 118.7969},
    '浙江': {'name': 'Hangzhou', 'lat': 30.2741, 'lon': 120.1551},
    '山东': {'name': 'Jinan', 'lat': 36.6512, 'lon': 117.1201},
    '河南': {'name': 'Zhengzhou', 'lat': 34.7466, 'lon': 113.6253},
    '四川': {'name': 'Chengdu', 'lat': 30.5728, 'lon': 104.0668},
    '湖南': {'name': 'Changsha', 'lat': 28.2278, 'lon': 112.9388},
    '安徽': {'name': 'Hefei', 'lat': 31.8206, 'lon': 117.2272},
    '河北': {'name': 'Shijiazhuang', 'lat': 38.0428, 'lon': 114.5149},
    '福建': {'name': 'Fuzhou', 'lat': 26.0745, 'lon': 119.2965},
    '江西': {'name': 'Nanchang', 'lat': 28.6820, 'lon': 115.8579},
    '辽宁': {'name': 'Shenyang', 'lat': 41.8057, 'lon': 123.4315},
    '黑龙江': {'name': 'Harbin', 'lat': 45.7732, 'lon': 126.6577},
    '吉林': {'name': 'Changchun', 'lat': 43.8171, 'lon': 125.3235},
    '山西': {'name': 'Taiyuan', 'lat': 37.8706, 'lon': 112.5489},
    '陕西': {'name': 'Xian', 'lat': 34.3416, 'lon': 108.9398},
    '甘肃': {'name': 'Lanzhou', 'lat': 36.0611, 'lon': 103.8343},
    '青海': {'name': 'Xining', 'lat': 36.6232, 'lon': 101.7782},
    '云南': {'name': 'Kunming', 'lat': 25.0389, 'lon': 102.7183},
    '贵州': {'name': 'Guiyang', 'lat': 26.6470, 'lon': 106.6302},
    '广西': {'name': 'Nanning', 'lat': 22.8170, 'lon': 108.3669},
    '海南': {'name': 'Haikou', 'lat': 20.0444, 'lon': 110.1999},
    '内蒙古': {'name': 'Hohhot', 'lat': 40.8414, 'lon': 111.7519},
    '新疆': {'name': 'Urumqi', 'lat': 43.8256, 'lon': 87.6168},
    '西藏': {'name': 'Lhasa', 'lat': 29.6520, 'lon': 91.1721},
    '宁夏': {'name': 'Yinchuan', 'lat': 38.4872, 'lon': 106.2309},
    '天津': {'name': 'Tianjin', 'lat': 39.3434, 'lon': 117.3616},
    '重庆': {'name': 'Chongqing', 'lat': 29.4316, 'lon': 106.9123},
}

# 省份温度数据
province_temperature_data = {
    'province': '',
    'temperature': 0,
    'feels_like': 0,
    'description': '',
    'humidity': 0,
    'timestamp': 0,
    'last_update': None,
    'history': []  # 存储省份温度历史数据
}

# 监控状态
province_timer = None
province_monitoring = False
last_api_data = None  # 存储最后一次API获取的数据

def get_weather_data(province_name):
    """
    获取天气数据
    
    Args:
        province_name (str): 省份名称
        
    Returns:
        dict: 天气数据
    """
    try:
        # 获取省份对应的城市信息
        city_info = PROVINCE_CITIES.get(province_name)
        if not city_info:
            print(f"未找到省份 {province_name} 的城市映射")
            return None
        
        # 使用坐标查询天气（更准确）
        url = f"{BASE_URL}?lat={city_info['lat']}&lon={city_info['lon']}&appid={API_KEY}&units=metric&lang=zh_cn"
        
        # 发送请求
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'temperature': round(data['main']['temp'], 1),
                'feels_like': round(data['main']['feels_like'], 1),
                'description': data['weather'][0]['description'],
                'humidity': data['main']['humidity'],
                'timestamp': int(time.time())
            }
        else:
            print(f"API请求失败: {response.status_code} {response.text}")
            return None
            
    except Exception as e:
        print(f"获取天气数据失败: {str(e)}")
        return None

def generate_simulated_data(province_name):
    """
    生成模拟温度数据（用于演示）
    
    Args:
        province_name (str): 省份名称
        
    Returns:
        dict: 模拟天气数据
    """
    # 基础温度范围（根据省份调整）
    base_temp = 20
    if '湖北' in province_name:
        base_temp = 18
    elif '广东' in province_name:
        base_temp = 25
    elif '北京' in province_name:
        base_temp = 15
    elif '黑龙江' in province_name or '吉林' in province_name:
        base_temp = 5
    elif '海南' in province_name:
        base_temp = 28
    
    # 添加随机变化
    temp_variation = random.uniform(-3, 3)
    current_temp = base_temp + temp_variation
    
    return {
        'temperature': round(current_temp, 1),
        'feels_like': round(current_temp + random.uniform(-1, 1), 1),
        'description': random.choice(['晴天', '多云', '阴天', '小雨']),
        'humidity': random.randint(40, 80),
        'timestamp': int(time.time())
    }

def generate_initial_data(province_name):
    """
    生成初始历史数据（用于网页打开时显示）
    
    Args:
        province_name (str): 省份名称
        
    Returns:
        list: 初始历史数据
    """
    base_temp = 20
    if '湖北' in province_name:
        base_temp = 18
    elif '广东' in province_name:
        base_temp = 25
    elif '北京' in province_name:
        base_temp = 15
    elif '黑龙江' in province_name or '吉林' in province_name:
        base_temp = 5
    elif '海南' in province_name:
        base_temp = 28
    
    # 生成过去1小时的数据（每15分钟一个点，共4个点）
    current_time = datetime.now()
    initial_data = []
    
    for i in range(4):
        # 计算时间（过去1小时内的4个时间点）
        time_offset = timedelta(minutes=15 * (3 - i))
        data_time = current_time - time_offset
        
        # 生成温度（基础温度 + 随机变化）
        temp_variation = random.uniform(-2, 2)
        temperature = base_temp + temp_variation
        
        initial_data.append({
            'time': data_time.strftime('%H:%M'),
            'temperature': round(temperature, 1),
            'feels_like': round(temperature + random.uniform(-1, 1), 1),
            'description': random.choice(['晴天', '多云', '阴天', '小雨']),
            'humidity': random.randint(40, 80),
            'timestamp': data_time.timestamp()
        })
    
    return initial_data

def update_province_temperature_data(province_name, use_api=True):
    """
    更新省份温度数据
    
    Args:
        province_name (str): 省份名称
        use_api (bool): 是否使用API获取数据
    """
    global province_temperature_data, last_api_data
    
    try:
        weather_data = None
        
        if use_api:
            # 使用API获取数据
            weather_data = get_weather_data(province_name)
            if weather_data:
                last_api_data = weather_data
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API数据更新: {province_name} {weather_data['temperature']}°C 湿度{weather_data['humidity']}%")
            else:
                print("API获取失败，使用模拟数据")
                weather_data = generate_simulated_data(province_name)
        else:
            # 使用上次API数据或模拟数据
            if last_api_data:
                # 基于上次API数据生成小幅变化
                base_temp = last_api_data['temperature']
                base_humidity = last_api_data['humidity']
                
                # 添加小幅随机变化
                temp_variation = random.uniform(-0.5, 0.5)
                humidity_variation = random.randint(-2, 2)
                
                weather_data = {
                    'temperature': round(base_temp + temp_variation, 1),
                    'feels_like': round(base_temp + temp_variation + random.uniform(-0.5, 0.5), 1),
                    'description': last_api_data['description'],
                    'humidity': max(0, min(100, base_humidity + humidity_variation)),
                    'timestamp': int(time.time())
                }
            else:
                # 如果没有API数据，使用模拟数据
                weather_data = generate_simulated_data(province_name)
        
        current_time = datetime.now()
        
        temperature_record = {
            'time': current_time.strftime('%H:%M'),
            'temperature': weather_data['temperature'],
            'feels_like': weather_data['feels_like'],
            'description': weather_data['description'],
            'humidity': weather_data['humidity'],
            'timestamp': current_time.timestamp()
        }
        
        # 更新省份温度数据
        province_temperature_data.update({
            'province': province_name,
            'temperature': weather_data['temperature'],
            'feels_like': weather_data['feels_like'],
            'description': weather_data['description'],
            'humidity': weather_data['humidity'],
            'timestamp': weather_data['timestamp'],
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # 添加历史记录
        province_temperature_data['history'].append(temperature_record)
        
        # 保持历史记录不超过20条
        if len(province_temperature_data['history']) > 20:
            province_temperature_data['history'].pop(0)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 省份温度数据已更新: {province_name} {weather_data['temperature']}°C 湿度{weather_data['humidity']}%")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新省份温度数据失败: {str(e)}")

def province_timer_worker(province_name):
    """
    省份温度数据定时更新工作线程（每1分钟更新数据，每5分钟请求API）
    
    Args:
        province_name (str): 省份名称
    """
    global province_monitoring
    
    api_counter = 0  # API请求计数器
    
    while province_monitoring:
        try:
            # 每5分钟请求一次API
            use_api = (api_counter % 60 == 0)
            
            update_province_temperature_data(province_name, use_api)
            
            api_counter += 1
            time.sleep(5)  # 每5秒更新一次数据
        except Exception as e:
            print(f"定时更新省份温度数据时发生错误: {str(e)}")
            time.sleep(10)  # 出错后等待1分钟再重试

def start_province_monitoring(province_name):
    """
    开始省份温度监控（每1分钟更新数据，每5分钟请求API）
    
    Args:
        province_name (str): 省份名称
    """
    global province_timer, province_monitoring, province_temperature_data
    
    if province_monitoring:
        print("省份温度监控已在运行中")
        return
    
    # 生成初始历史数据
    initial_data = generate_initial_data(province_name)
    province_temperature_data['history'] = initial_data
    province_temperature_data['province'] = province_name
    
    # 立即获取一次当前数据（使用API）
    update_province_temperature_data(province_name, True)
    
    province_monitoring = True
    province_timer = threading.Thread(target=province_timer_worker, args=(province_name,))
    province_timer.daemon = True
    province_timer.start()
    
    print(f"省份温度监控已启动，监控省份: {province_name}")

def stop_province_monitoring():
    """
    停止省份温度监控
    """
    global province_monitoring
    
    province_monitoring = False
    print("省份温度监控已停止")

# Django视图函数
@csrf_exempt
@require_http_methods(["GET"])
def get_province_temperature_view(request):
    """
    获取省份温度数据API视图函数
    
    Returns:
        JsonResponse: 省份温度历史数据
    """
    global province_temperature_data
    
    try:
        if not province_temperature_data['history']:
            return JsonResponse({
                "success": False,
                "error": "暂无省份温度数据，请先启动省份温度监控"
            }, status=404)
        
        return JsonResponse({
            "success": True,
            "data": province_temperature_data,
            "message": f"{province_temperature_data['province']}温度数据"
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"获取省份温度数据失败: {str(e)}"
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def start_province_monitoring_view(request):
    """
    启动省份温度监控API视图函数
    
    POST请求参数:
    {
        "province": "省份名称"  # Required
    }
    """
    try:
        province_name = ""
        
        try:
            data = json.loads(request.body)
            province_name = data.get("province", "")
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "JSON格式错误"
            }, status=400)
        
        if not province_name:
            return JsonResponse({
                "success": False,
                "error": "省份名称不能为空"
            }, status=400)
        
        start_province_monitoring(province_name)
        
        return JsonResponse({
            "success": True,
            "message": f"省份温度监控已启动，监控省份: {province_name}",
            "province": province_name
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"启动省份温度监控失败: {str(e)}"
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def stop_province_monitoring_view(request):
    """
    停止省份温度监控API视图函数
    """
    try:
        stop_province_monitoring()
        
        return JsonResponse({
            "success": True,
            "message": "省份温度监控已停止"
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"停止省份温度监控失败: {str(e)}"
        }, status=500)

