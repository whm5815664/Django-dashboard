from django.urls import path, re_path
from . import views

app_name = 'labDatasets'

urlpatterns = [
    # Vue 应用入口
    path('', views.lab_datasets_index, name='index'),
    
    # 捕获所有路由以支持 Vue Router 的 history 模式
    # 注意：这个路由应该放在最后，以捕获所有未匹配的路径
    re_path(r'^.*$', views.lab_datasets_catch_all, name='catch_all'),
]

