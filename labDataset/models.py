from django.db import models

# Create your models here.


class Dataset(models.Model):
    name = models.CharField(max_length=200) # 数据集名称
    description = models.TextField(blank=True)  # 描述
    data_format = models.CharField(max_length=64, blank=True)      # 数据格式
    storage_url = models.CharField(max_length=1024, blank=True)    # 存储路径/URL描述
    cover = models.CharField(max_length=1024, blank=True) # 封面 URL 或静态资源路径
    creator = models.CharField(max_length=200)  # 创建者 to do关联用户表
    size = models.BigIntegerField(default=0)        # bytes
    file_count = models.IntegerField(default=0) # 文件数量 
    created_at = models.DateTimeField(auto_now_add=True)    # 创建时间
    updated_at = models.DateTimeField(auto_now=True)

    
    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True, db_index=True)  # 唯一约束

    def __str__(self) -> str:
        return self.name
