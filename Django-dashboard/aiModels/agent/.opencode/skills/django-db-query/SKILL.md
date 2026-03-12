---
name: django-db-query
description: Django数据库查询技能，支持查询本地数据库(web_database)和远程环境监测数据库(pig)中的各表数据，并对数据进行总结分析。用于回答用户关于数据库表结构、记录统计、数据详情等问题的场景。
---

# Django 数据库查询

## 数据库配置

### 本地数据库 (default)
- 数据库: web_database
- 配置: settings.py 中的 DATABASES["default"]

### 远程数据库 (pig) - 环境监测数据库
- 数据库: pig
- Host: 47.99.61.189
- Port: 3307
- 用户: zb25
- 密码: zb123456
- 配置: settings.py 中的 DATABASES["pig"]

## 表名映射

| 表名 | 说明 |
|------|------|
| environment_data | 环境监控数据表 |
| device | 设备表 |
| base | 基地表 |
| pig_pigsty | 基地信息表 |
| pig_farm | 公司表 |

## 字段映射

### 远程数据库 (pig) 字段
- `pigsty_id`: 基地编号（只取数字部分，int类型）
- `device_id`: 设备编号
- `image`: 图片字段，图片URL为 `http://47.99.61.189:8175/media/` + image

### 本地数据库 (default) 字段
- `base_id`: 基地编号，对应远程数据库的 `pigsty_id`
- 用户输入时只取数字部分（例如：输入HB001，远程数据库中对应pig_pigsty为1）

## 使用方法

### 1. 使用 Django ORM 查询

```python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 查询远程数据库
from django.db import connections
with connections['pig'].cursor() as cursor:
    cursor.execute("SELECT * FROM environment_data LIMIT 10")
    rows = cursor.fetchall()

# 查询本地数据库
from django.db import models
from storageSystem.models import Base
```

### 2. 图片处理

**图片URL**: `http://47.99.61.189:8175/media/` + image字段值

**用户请求时处理流程**:
1. 下载图片到本地 temp 文件夹: `Django-dashboard/aiModels/agent/temp`
2. 文件命名: `{session_id}_{序号}.jpg`（如 `abc123_1.jpg`）
3. 返回给用户**可直接点击的访问链接**: `http://47.99.61.189:8175/media/` + image

```python
import requests
import os

def download_image(image_field_value, session_id, index):
    base_url = "http://47.99.61.189:8175/media/"
    image_url = base_url + image_field_value
    
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"{session_id}_{index}.jpg"
    filepath = os.path.join(temp_dir, filename)
    
    response = requests.get(image_url, timeout=30)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(response.content)
    
    # 返回给用户可直接点击的链接
    return image_url
```

### 3. 基地编号转换

本地base_id与远程pigsty_id的转换：
- 本地输入: HB001 -> 远程 pigsty_id = 1
- 本地输入: HB002 -> 远程 pigsty_id = 2

```python
def convert_base_id(base_id):
    """将本地base_id转换为远程pigsty_id"""
    import re
    match = re.search(r'\d+', base_id)
    if match:
        return int(match.group())
    return None
```

## 查询示例

### 查询所有基地
```python
with connections['pig'].cursor() as cursor:
    cursor.execute("SELECT * FROM pig_pigsty")
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
```

### 按基地查询环境数据
```python
def get_environment_data_by_pigsty(pigsty_id, limit=100):
    with connections['pig'].cursor() as cursor:
        cursor.execute(
            "SELECT * FROM environment_data WHERE pigsty_id = %s ORDER BY id DESC LIMIT %s",
            [pigsty_id, limit]
        )
        return cursor.fetchall()
```

### 统计各表数据量
```python
def get_table_counts():
    tables = ['environment_data', 'device', 'base', 'pig_pigsty', 'pig_farm']
    with connections['pig'].cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count}")
```

## 数据总结

查询数据后，应对数据进行总结：
1. 总记录数
2. 各字段含义和数据类型
3. 数据时间范围（如果有时间字段）
4. 关键统计指标（平均值、最大值、最小值等）
5. 图片数量和状态
