import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from PIL import Image
import torch
from torchvision import transforms
import io
import base64

from aiModels.diseaseModel.diseaseModel import disease_recognize 

# 图片预处理转换
def get_image_transforms():
    """获取图片预处理转换"""
    return transforms.Compose([
        transforms.Resize(256),     # 缩放图片，保持长宽比不变，最短边为256像素
        transforms.CenterCrop(256),  # 从图片中间切出256*256图片
        transforms.ToTensor(),       # 转换为张量
    ])

@csrf_exempt
@require_http_methods(["POST"])
def recognize_image(request):
    """图片识别处理函数，调用emotionModel.py进行情绪识别"""
    try:
        # 检查是否有文件上传
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': '没有上传图片文件'
            })
        
        # 获取上传的图片文件
        image_file = request.FILES['image']
        
        # 检查文件类型
        if not image_file.content_type.startswith('image/'):
            return JsonResponse({
                'success': False,
                'error': '上传的文件不是图片格式'
            })
        
        # 读取图片
        image_data = image_file.read()
        pil_image = Image.open(io.BytesIO(image_data))
        
        # 转换为RGB模式（处理RGBA等其他格式）
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # 保存临时图片到服务器临时目录
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        temp_path = os.path.join(temp_dir, image_file.name)
        print('临时图片保存路径：', temp_path)
        pil_image.save(temp_path)

        # 调用diseaseModel.py中的disease_recognize接口函数（已在模块顶部导入）
        
        # 进行情绪识别
        try:
            label = disease_recognize(temp_path)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'识别失败: {str(e)}'
            })

        # 删除临时图片
        if os.path.exists(temp_path):
            os.remove(temp_path)

        result = f"图片识别结果: {label}"

        return JsonResponse({
            'success': True,
            'result': result,
            'emotion_label': label,
            'image_size': {
                'width': pil_image.size[0],
                'height': pil_image.size[1]
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'处理图片时发生错误: {str(e)}'
        })

