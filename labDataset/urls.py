from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ----------------------
    # 后端 API 路由（可选，如果还保留接口给 JS fetch 调用）
    # ----------------------
    path("api/datasets/", views.datasets, name="api_datasets"),
    path("api/datasets/<int:pk>/", views.dataset_detail, name="api_dataset_detail"),
    path("api/tags/", views.tags, name="api_tags"),
    path("api/datasetFile/<int:pk>/", views.datasetFile, name="api_dataset_file"),
    path("api/csrf/", views.csrf, name="api_csrf"),

    # ----------------------
    # 页面路由（Django 模板渲染）
    # ----------------------
    path("", views.dataset_list_view, name="DatasetList"),             # 列表页  空路径
    path("<int:id>/detail/", views.dataset_detail_view, name="DatasetDetail"),
    # path("upload/", views.dataset_upload_view, name="DatasetUpload"),  # 上传接口
]

# 静态文件 / 媒体文件
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)








# urlpatterns = [
#     # 后端API路由(前后端数据交互)
#     # axios请求   http://127.0.0.1:8000/labDataset/api/datasets/ 
#     path("api/datasets/",views.datasets),
#     path("api/datasets/<int:pk>/", views.dataset_detail),
#     path("api/tags/", views.tags),
#     path("api/datasetFile/<int:pk>/", views.datasetFile),

#     path("api/csrf/", views.csrf),


#     # 页面路由(跳页面、前端路由、兜底返回 index.html)
#     path("", labdataset_spa),                 # 只匹配/labDataset/,访问app的根路径时,返回Vue的入口页index.html
#     # re_path(r"^(?:.*)/?$", labdataset_spa),   # /labdataset/任意子路由 刷新不404


#     # Vue 这种单页应用（SPA）里，“页面路径”是前端自己管，但在浏览器里刷新/直接输入 URL 时，请求会先到 Django 服务器。
#     # 如果 Django 不认识这个路径，就会 404，所以必须“兜底”把这些路径都返回同一个 index.html，让 Vue 接管
#     re_path(r"^(?!api/).*$", labdataset_spa),   # 匹配/labdataset/detail/7任意路径，除了api开头的前后端请求
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# # MEDIA_URL = "/media/"
# # MEDIA_ROOT = os.path.join(BASE_DIR, "media")

