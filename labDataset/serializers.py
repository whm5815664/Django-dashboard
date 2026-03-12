from rest_framework import serializers
from .models import Dataset


# 数据集
# class DatasetSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Dataset
#         fields = ["name", "description", "cover", "creator", "size", "file_count", "created_at", "updated_at"]