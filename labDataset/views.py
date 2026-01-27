from django.shortcuts import render

# Create your views here.

# 返回 Vue 的入口页面
def labdataset_spa(request):
    return render(request, "labDataset/index.html")