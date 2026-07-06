---
name: DB
description: MySQL数据库查询操作技能。用于对本地数据库(default/web_database)和远程数据库(pig)进行查询操作。触发场景：(1)查询环境监控数据 (2)查询设备信息 (3)查询基地信息 (4)跨数据库关联查询 (5)数据统计和分析 (6)查询指定基地HB001/HB002等的环境数据
---

# DB 数据库查询

## 快速使用

```bash
# 必须设置UTF-8编码解决中文乱码
set PYTHONIOENCODING=utf-8
python scripts/db_query.py <数据库> <查询>
```

## 配置

| 数据库 | HOST | PORT | NAME | USER | PASSWORD |
|--------|------|------|------|------|----------|
| default | 127.0.0.1 | 3306 | web_database | root | (空) |
| pig | 116.62.214.146 | 3306 | pig | wyh22 | wyh123456 |

## 预设查询(直接使用)

| 模板 | 说明 | 示例 |
|------|------|------|
| query_hb001_env | HB001环境数据 | `python scripts/db_query.py pig query_hb001_env` |
| query_hb002_env | HB002环境数据 | `python scripts/db_query.py pig query_hb002_env` |
| query_all_bases | 所有基地 | `python scripts/db_query.py default query_all_bases` |
| query_devices | 所有设备 | `python scripts/db_query.py pig query_devices` |
| query_pigsty | 所有园区/基地 | `python scripts/db_query.py pig query_pigsty` |

## 直接SQL

```bash
# 查询HB001(pigsty_id=1)最新10条环境数据
python scripts/db_query.py pig "SELECT * FROM environment_data WHERE pigsty_id=1 ORDER BY collected_time DESC LIMIT 10"

# 查询本地基地表
python scripts/db_query.py default "SELECT * FROM base"
```

## 字段映射

- `base_id`: 基地编号(HB001→pigsty_id=1, HB002→pigsty_id=2)
- `pigsty_id`: 远程数据库的数字ID
- `image`: 需拼接前缀 `http://47.99.61.189:8175/media/`

## 详细表结构

见 [references/schema.md](references/schema.md)