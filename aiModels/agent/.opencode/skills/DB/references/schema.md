# 数据库表结构参考

## 表结构详情

### 本地数据库 (default) - web_database

#### base 表 (基地表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| base_id | varchar(20) | 基地编号，主键 (如 HB001) |
| base_name | varchar(20) | 基地名称 |
| longitude | float | 经度 |
| latitude | float | 纬度 |
| province_name | varchar(20) | 省份 |
| city_name | varchar(20) | 城市 |
| base_description | varchar(100) | 描述 |
| base_pic | varchar(100) | 图片 |

---

### 远程数据库 (pig)

#### environment_data 表 (环境监控数据表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | bigint | 主键 |
| CO2 | double | 二氧化碳浓度 |
| temperature | double | 温度 |
| humidity | double | 湿度 |
| collected_time | datetime | 采集时间 |
| device_id | bigint | 设备ID (对应 device.id) |
| pigsty_id | bigint | 库房ID (对应 base.base_id 的数字部分) |
| C2H4 | double | 乙烯浓度 |
| C2H5OH | double | 乙醇浓度 |
| CO | double | 一氧化碳浓度 |
| H2 | double | 氢气浓度 |
| O2 | double | 氧气浓度 |
| VOC | double | VOC浓度 |
| humidity_inner | double | 内部湿度 |
| temperature_inner | double | 内部温度 |
| image | varchar(100) | 图片路径 (需拼接前缀) |
| notes | varchar(512) | 备注 |
| is_complete | tinyint | 是否完整 |

**图片URL前缀**: `http://47.99.61.189:8175/media/`

#### device 表 (设备表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | bigint | 主键 |
| name | varchar(50) | 设备名称 |
| device_code | varchar(50) | 设备编码 |
| description | varchar(500) | 描述 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| collect_interval | double | 采集间隔 |

#### pig_pigsty 表 (柑橘基地信息表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | bigint | 主键 |
| pigsty_id | bigint | 基地编号 (数字) |
| pigsty_name | varchar(50) | 基地名称 |
| farm_id | bigint | 农场ID (对应 pig_farm.id) |
| area | double | 面积 |
| ... | ... | ... |

#### pig_farm 表 (公司表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | bigint | 主键 |
| farm_name | varchar(50) | 公司/农场名称 |
| ... | ... | ... |

---

## 关联查询示例

### 基地与环境数据关联查询

由于 base.base_id 是字符串(如 "HB001")，而 environment_data.pigsty_id 是数字(如 1)，需要进行转换：

```sql
-- 查询基地对应的最新环境数据
SELECT 
    b.base_id,
    b.base_name,
    e.temperature,
    e.humidity,
    e.CO2,
    e.collected_time
FROM base b
LEFT JOIN (
    SELECT pigsty_id, temperature, humidity, CO2, collected_time
    FROM environment_data
    ORDER BY collected_time DESC
    LIMIT 1
) e ON CAST(e.pigsty_id AS CHAR) = b.base_id
WHERE b.base_id = 'HB001';
```

### 设备与环境数据关联查询

```sql
-- 查询设备及其最新读数
SELECT 
    d.name,
    d.device_code,
    e.temperature,
    e.humidity,
    e.collected_time
FROM device d
LEFT JOIN environment_data e ON d.id = e.device_id
WHERE d.device_code = 'DEVICE001';
```

### 跨库关联查询 (通过应用层合并)

由于两个数据库无法直接JOIN，需分别查询后合并：

1. 从 remote (pig) 查询环境数据
2. 从 local (default) 查询基地信息
3. 在应用层通过 pigsty_id 与 base_id 的映射关系合并