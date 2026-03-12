from django.urls import path, re_path
from .views import labdataset_spa, get_datasets
from . import views

urlpatterns = [
    # API路由放在前面 GET http://127.0.0.1:8000/labdataset/api/datasets/
    # 相对当前 include 前缀的, 总路由 include 的前缀在config/urls.py 
    # re_path(r'api/get_datasets$', views.get_datasets),
    path("api/get_datasets/",views.get_datasets),

    # 页面路由
    path("", labdataset_spa),                 # /labdataset/  使其可以被访问
    re_path(r"^(?:.*)/?$", labdataset_spa),   # /labdataset/任意子路由 刷新不404
]
