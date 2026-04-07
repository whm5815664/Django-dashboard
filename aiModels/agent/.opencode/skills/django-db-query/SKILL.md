---
name: django-db-query
description: Django数据库查询技能，支持查询本地数据库(web_database)和远程环境监测数据库(pig)中的各表数据，并对数据进行总结分析。用于回答用户关于数据库表结构、记录统计、数据详情等问题的场景。
---

# Django 数据库查询

## 数据库配置

### 本地数据库 (default)
- 数据库: web_database
- Host: 127.0.0.1:3306
- 用户: root

### 远程数据库 (pig) - 环境监测数据库
- 数据库: pig
- Host: 47.99.61.189:3307
- 用户: zb25

## 表名映射

| 表名 | 说明 |
|------|------|
| environment_data | 环境监控数据表 |
| device | 设备表 |
| base | 基地表 |
| pig_pigsty | 柑橘基地信息表 |
| pig_farm | 公司表 |

## 字段映射

### 远程数据库 (pig)
- `pigsty_id`: 基地编号（int类型，只取数字部分）
- `device_id`: 设备编号
- `image`: 图片字段，URL为 `http://47.99.61.189:8175/media/` + image

### 本地数据库 (default)
- `base_id`: 基地编号（如HB001），对应远程数据库的pigsty_id需提取数字部分

## 快捷脚本查询

本技能提供三个脚本，可直接在命令行执行查询，无需手动编写Python代码。

脚本路径相对于技能目录: `scripts/`

### 1. db_query.py - 通用查询

```bash
# SQL直接查询
python scripts/db_query.py --db pig --sql "SELECT * FROM pig_pigsty LIMIT 10"

# 表查询（支持where、排序、限制）
python scripts/db_query.py --db pig --table environment_data --where "pigsty_id=1" --order-by "id DESC" --limit 50

# 指定列
python scripts/db_query.py --db default --table base --columns base_id,base_name

# JSON输出
python scripts/db_query.py --db pig --table device --format json
```

### 2. db_stats.py - 数据统计

```bash
# 统计多个表记录数
python scripts/db_stats.py --db pig --tables environment_data,device,pig_pigsty

# 统计字段指标（count/min/max/avg/sum）
python scripts/db_stats.py --db pig --table environment_data --stats temperature,humidity,co2

# 表结构摘要
python scripts/db_stats.py --db default --table base --summary
```

### 3. db_schema.py - 表结构查询

```bash
# 列出所有表
python scripts/db_schema.py --db pig --tables

# 查看表列信息
python scripts/db_schema.py --db pig --table environment_data --columns

# 查看表索引
python scripts/db_schema.py --db default --table base --indexes
```

### 脚本参数说明

| 参数 | 说明 |
|------|------|
| `--db` | 数据库: default 或 pig |
| `--sql` | 直接执行SQL |
| `--table` | 表名 |
| `--columns` | 查询列名(逗号分隔) |
| `--where` | WHERE条件 |
| `--order-by` | ORDER BY排序 |
| `--limit` | 限制返回条数(默认100) |
| `--format` | 输出格式: table/json/csv |

## 手动ORM查询

当脚本无法满足复杂查询需求时，可使用Django ORM:

```python
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from storageSystem.models import Base, Device, DeviceReading

# 原始SQL查询
with connections['pig'].cursor() as cursor:
    cursor.execute("SELECT * FROM environment_data WHERE pigsty_id = %s", [1])
    rows = cursor.fetchall()

# ORM查询
Base.objects.all()
DeviceReading.objects.filter(pigsty__base_id='1')[:10]
```

## 图片处理

**图片URL**: `http://47.99.61.189:8175/media/` + image字段值

用户请求图片时:
1. 下载到 `Django-dashboard/aiModels/agent/temp/{session_id}_{序号}.jpg`
2. 返回用户可点击链接: `http://47.99.61.189:8175/media/` + image

```python
import requests, os

def download_image(image_field, session_id, index):
    url = f"http://47.99.61.189:8175/media/{image_field}"
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        with open(os.path.join(temp_dir, f"{session_id}_{index}.jpg"), 'wb') as f:
            f.write(resp.content)
    return url
```

## 基地编号转换

```python
import re
def convert_base_id(base_id):
    match = re.search(r'\d+', base_id)
    return int(match.group()) if match else None
# HB001 -> 1, HB002 -> 2
```

## 数据总结规范

查询后应总结:
1. 总记录数
2. 字段含义和数据类型
3. 数据时间范围
4. 关键统计指标（平均值、最大值、最小值）
5. 图片数量和状态
