# storageSystem/urls.py
from django.urls import path
from django.views.generic import RedirectView

# 页面
from storageSystem.views.pages import (
    dashboard_page,
    coldroom_manage_page,
    device_readings_page,
)

# Dashboard 相关接口
from storageSystem.views.api_dashboard import (
    stats,
    trend,
    device_names,
    dashboard_devices,
    save_device_location,
    update_device,
    delete_device,

    # 读取页接口：你已经加在 api_dashboard.py 里了
    device_readings_list,
    update_reading,
    delete_reading,
)

# 冷库相关接口
from storageSystem.views.api_coldrooms import devices

urlpatterns = [
    # 首页重定向到 dashboard
    path("", RedirectView.as_view(url="dashboard/", permanent=False), name="home"),

    # 页面
    path("dashboard/", dashboard_page, name="dashboard"),
    path("coldrooms/", coldroom_manage_page, name="coldrooms"),
    path("device/<int:device_id>/readings/", device_readings_page, name="device_readings_page"),

    # Dashboard APIs
    path("api/dashboard/stats/", stats, name="api_dashboard_stats"),
    path("api/dashboard/trend/", trend, name="api_dashboard_trend"),
    path("api/dashboard/devices/", dashboard_devices, name="api_dashboard_devices"),
    path("api/dashboard/device-location/", save_device_location, name="api_dashboard_device_location"),
    path("api/dashboard/device-update/", update_device, name="api_dashboard_device_update"),
    path("api/dashboard/device-delete/", delete_device, name="api_dashboard_device_delete"),

    # 其它 APIs
    path("api/devices/", devices, name="api_devices"),
    path("api/device-names/", device_names, name="api_device_names"),

    # 读取页 APIs
    path("api/device/<int:device_id>/readings/", device_readings_list, name="api_device_readings_list"),
    path("api/readings/<int:reading_id>/update/", update_reading, name="api_update_reading"),
    path("api/readings/<int:reading_id>/delete/", delete_reading, name="api_delete_reading"),
]