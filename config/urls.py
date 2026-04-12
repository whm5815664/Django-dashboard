"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView

from config.media_proxy import remote_media_proxy

# 处理浏览器开发工具自动请求的路径（Chrome/Edge等）
def chrome_devtools_handler(request):
    """处理 /.well-known/appspecific/com.chrome.devtools.json 请求"""
    return JsonResponse({})

urlpatterns = [
    path("", RedirectView.as_view(url="/screen/base_map/湖北省/"), name="home"),
    
    path("admin/", admin.site.urls),
    path("media-proxy/<path:subpath>", remote_media_proxy, name="remote_media_proxy"),
    
    path('screen/', include('screen.urls')),
    path('aiModels/', include('aiModels.urls')),
    path("storage/", include("storageSystem.urls")),
    path("labdataset/", include("labDataset.urls")),  # 注意：URL路径使用小写，应用名称使用驼峰命名
    # 处理浏览器开发工具的自动请求，避免404错误
    path(".well-known/appspecific/com.chrome.devtools.json", chrome_devtools_handler),
]

# 添加媒体文件的URL路由（仅在开发环境中）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

