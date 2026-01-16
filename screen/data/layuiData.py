from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from ..models import *



@require_GET
def get_layui_base_data(request):
    try:
        # 1. 获取分页参数
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))

        # 2. 查询数据库
        queryset = Basemap.objects.all().values(
            'baseID', 'baseName', 'longitude', 'latitude',
            'province', 'city', 'description'
        )

        # 3. 分页处理
        paginator = Paginator(queryset, limit)
        current_page = paginator.page(page)

        # 4. 构造符合Layui规范的响应数据
        response_data = {
            "code": 200,  # 必须为200表示成功
            "msg": "success",  # 提示信息
            "count": paginator.count,  # 总数据量
            "data": list(current_page)  # 当前页数据
        }

    except Exception as e:
        # 错误处理
        response_data = {
            "code": 500,
            "msg": f"服务器错误: {str(e)}",
            "count": 0,
            "data": []
        }

    return JsonResponse(response_data, safe=False)


# @csrf_exempt
# # 基地管理页面的deepseek接口
# def get_deepseek_answer(request):
#     openai.api_key = "sk-XpGRkZBoRiOD3FTk4e71Be7791C74069B9CdFd925731F954"
#     openai.base_url = "https://spark-api-open.xf-yun.com/v2/"
#     openai.default_headers = {"x-foo": "true"}
#
#     # 得到post的文本
#     if request.method == "POST":
#         user_input = request.POST.get("user_input", "")
#         print('user_input:', user_input)
#
#     try:
#         completion = openai.chat.completions.create(
#             model="gpt-3.5-turbo-1106",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": user_input,
#                 },
#             ],
#         )
#         answer = completion.model_dump_json()
#     except openai.APIConnectionError as e:
#         return JsonResponse({"error": "API 连接失败，请稍后再试。"}, status=500)
#     except openai.InternalServerError as e:
#         return JsonResponse({"error": "服务器内部错误，请稍后再试。"}, status=500)
#
#     return JsonResponse({"answer": answer})



