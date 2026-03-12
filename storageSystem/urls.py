# storageSystem/urls.py
from django.urls import path
from django.views.generic import RedirectView

from storageSystem.views.pages import dashboard_page, coldroom_manage_page
from storageSystem.views.api_dashboard import (
    stats,
    trend,
    device_names,
    dashboard_devices,
    save_device_location,

    # ✅ 新增：编辑/删除（你需要在 api_dashboard.py 里实现这两个 view）
    update_device,      # POST
    delete_device,      # POST
)
from storageSystem.views.api_coldrooms import devices

urlpatterns = [
    # 首页重定向到 dashboard
    path("", RedirectView.as_view(url="dashboard/", permanent=False), name="home"),

    # 页面
    path("dashboard/", dashboard_page, name="dashboard"),
    path("coldrooms/", coldroom_manage_page, name="coldrooms"),

    # Dashboard APIs（✅ 统一末尾 /）
    path("api/dashboard/stats/", stats, name="api_dashboard_stats"),
    path("api/dashboard/trend/", trend, name="api_dashboard_trend"),
    path("api/dashboard/devices/", dashboard_devices, name="api_dashboard_devices"),

    # ✅ 地图选点：保存经纬度到 devices 表
    path("api/dashboard/device-location/", save_device_location, name="api_dashboard_device_location"),

    # ✅ 新增：表格编辑/删除（用于“修改/删除并写回数据库”）
    path("api/dashboard/device-update/", update_device, name="api_dashboard_device_update"),
    path("api/dashboard/device-delete/", delete_device, name="api_dashboard_device_delete"),

    # 其它 APIs
    path("api/devices/", devices, name="api_devices"),
    path("api/device-names/", device_names, name="api_device_names"),
]
