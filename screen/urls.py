from django.urls import path
from django.views.generic.base import RedirectView

from . import views

# 数字大屏数据读取
from .data import screenData

# 基地数据读取
from .data import baseData


# 摄像头功能
from .tool import video

# 添加天气API路由
from .tool import weather_api

urlpatterns = [
    # 视图主页
    path('', views.index, name='index'),
    path('province_map/<str:province_name>/', views.province_map, name='province_map'),  # 跳转到echart地图
    path('base_map/<str:province_name>/', views.base_map, name='base_map'),  # 跳转到省份高德地图

    # 基地主页
    path('baseIndex', views.baseIndex, name='baseIndex'),

    # 功能-摄像头
    path('video_feed', video.video_feed, name='video1_feed'),  # 摄像头

    # 功能-数据库-数据大屏相关
    path('citrus_data', screenData.get_citrus_data, name='citrus_data'),  # 查询柑橘产量
    path('get_citrus_data_max', screenData.get_citrus_data_max, name='get_citrus_data_max'),  # 得到前5产区
    path('get_citrus_production_history', screenData.get_citrus_production_history, name='get_citrus_production_history'),  # 得到全国柑橘历史产量

    # 功能-数据库-基地相关
    path('get_base_by_province', baseData.get_base_by_province, name='get_base_by_province'),  # 得到对应省份的所有基地信息
    path('get_base_info', baseData.get_base_by_baseID, name='get_base_info'),  # 得到对应基地全部信息
    path('get_citrus_production_by_province', baseData.get_citrus_production_by_province, name='get_citrus_production_by_province'),  # 得到指定省份的柑橘产量历史数据
    path('get_variety_production_last_months', baseData.get_variety_production_last_months, name='get_variety_production_last_months'),  # 指定省份最近月份的品种产量
    
    # 功能-数据库-baseIndex页面相关（基地管理）
    path('add_base', baseData.add_base, name='add_base'),  # 添加基地
    path('delete_base', baseData.delete_base, name='delete_base'),  # 删除基地
    path('edit_base', baseData.edit_base, name='edit_base'),  # 修改基地
    path('generate_base_id', baseData.generate_base_id, name='generate_base_id'),  # 自动生成基地编号
    path('get_base', baseData.get_base, name='get_base'),  # 得到基地管理页面数据
    

    # 天气API路由 
    path('weather/province_temperature/', weather_api.get_province_temperature_view, name='get_province_temperature'),
    path('weather/start_province_monitoring/', weather_api.start_province_monitoring_view, name='start_province_monitoring'),
    path('weather/stop_province_monitoring/', weather_api.stop_province_monitoring_view, name='stop_province_monitoring'),

    # 外部网页接入测试
    path('test', RedirectView.as_view(url='https://www.deepseek.com')),
]