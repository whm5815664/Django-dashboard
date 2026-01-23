# storageSystem/urls.py
from django.urls import path
from django.views.generic import RedirectView

from storageSystem.views.pages import dashboard_page, coldroom_manage_page
from storageSystem.views.api_dashboard import stats, trend, device_names
from storageSystem.views.api_coldrooms import devices

urlpatterns = [
    # ✅ 访问 http://127.0.0.1:8000/ 自动跳到 /dashboard/
    path("", RedirectView.as_view(url="dashboard/", permanent=False), name="home"),

    path("dashboard/", dashboard_page, name="dashboard"),
    path("coldrooms/", coldroom_manage_page, name="coldrooms"),

    path("api/dashboard/stats", stats, name="api_dashboard_stats"),
    path("api/dashboard/trend", trend, name="api_dashboard_trend"),
    path("api/devices", devices, name="api_devices"),
    path("api/device-names/", device_names, name="api_device_names"),
]
