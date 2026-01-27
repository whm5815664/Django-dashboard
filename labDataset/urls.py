from django.urls import path, re_path
from .views import labdataset_spa

urlpatterns = [
    path("", labdataset_spa),                 # /labdataset/  使其可以被访问
    re_path(r"^(?:.*)/?$", labdataset_spa),   # /labdataset/任意子路由 刷新不404
]
