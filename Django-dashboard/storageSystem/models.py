from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """抽象基类：所有表通用的创建/更新时间（仅用于 ORM 管理表）"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ========= 库房/基地表：base =========
class Base(models.Model):
    # 你截图：base_id varchar(20) 主键
    base_id = models.CharField("库房/基地编号", max_length=20, primary_key=True)
    base_name = models.CharField("库房/基地名称", max_length=20)

    # 截图里 province_name/city_name 是 varchar（长度你没给完整，我按 20）
    province_name = models.CharField("所在省份", max_length=20)
    city_name = models.CharField("城市", max_length=20)

    longitude = models.FloatField("经度")
    latitude = models.FloatField("纬度")

    base_description = models.CharField("描述", max_length=100)
    base_pic = models.CharField("图片", max_length=100)

    class Meta:
        db_table = "base"
        managed = False
        verbose_name = "库房/基地"
        verbose_name_plural = "库房/基地"

    def __str__(self) -> str:
        return f"{self.base_name}({self.base_id})"


# ========= 设备表：device =========
class Device(models.Model):
    """
    对齐真实 device 表字段：
    id(bigint), name(varchar50), device_code(varchar50), description(varchar500),
    created_at(datetime6), updated_at(datetime6), collect_interval(double)
    """
    id = models.BigAutoField(primary_key=True, db_column="id")

    name = models.CharField("名称", max_length=50, db_column="name")
    device_code = models.CharField("设备编码", max_length=50, db_column="device_code", db_index=True)

    description = models.CharField("描述", max_length=500, db_column="description", null=True, blank=True)

    created_at = models.DateTimeField("创建时间", db_column="created_at")
    updated_at = models.DateTimeField("更新时间", db_column="updated_at")

    collect_interval = models.FloatField("采集间隔", db_column="collect_interval", null=True, blank=True)

    class Meta:
        db_table = "device"
        managed = False
        verbose_name = "设备"
        verbose_name_plural = "设备"

    def __str__(self) -> str:
        return f"{self.name}({self.device_code})"

    def __str__(self) -> str:
        return f"{self.name}({self.device_code})"


# ========= 环境数据表：environment_data =========
class DeviceReading(models.Model):
    """
    对齐你截图 environment_data 表字段：
    id(bigint pk), CO2(double), temperature(double), humidity(double),
    collected_time(datetime6), updated_at(datetime6),
    device_id(bigint), pigsty_id(bigint),
    image(varchar100),
    C2H4(double), C2H5OH(double), CO(double), H2(double), O2(double), VOC(double),
    humidity_inner(double), notes(varchar512), temperature_inner(double),
    is_complete(tinyint1)
    """
    id = models.BigAutoField(primary_key=True, db_column="id")

    # 数据来源（外键）：device_id -> device.id
    device = models.ForeignKey(
        Device,
        db_column="device_id",
        to_field="id",
        on_delete=models.DO_NOTHING,
        related_name="readings",
        db_constraint=False,
    )

    # 数据来源（外键）：pigsty_id -> base.base_id
    # ⚠️ 注意：你的 pigsty_id 是 bigint，而 base_id 是 varchar(20)。
    # 这样关联只有在 base_id 实际为 "1"/"2" 这种“数字字符串”时才能匹配得上。
    # 如果 base_id 是 "HB001" 这种字符串，而 pigsty_id 存的是 1/2，那就需要改关联方式。
    pigsty = models.ForeignKey(
        Base,
        db_column="pigsty_id",
        to_field="base_id",
        on_delete=models.DO_NOTHING,
        related_name="readings",
        db_constraint=False,
    )

    # 时间字段：为了兼容你 api_dashboard.trend() 优先找 reported_at，
    # 我把字段名叫 reported_at，但映射到数据库列 collected_time
    reported_at = models.DateTimeField("采集时间", db_column="collected_time", db_index=True)
    updated_at = models.DateTimeField("更新时间", db_column="updated_at")

    # 传感器数据（double）
    co2 = models.FloatField("CO2", db_column="CO2", null=True, blank=True)
    temperature = models.FloatField("温度", db_column="temperature", null=True, blank=True)
    humidity = models.FloatField("湿度", db_column="humidity", null=True, blank=True)

    c2h4 = models.FloatField("C2H4", db_column="C2H4", null=True, blank=True)
    c2h5oh = models.FloatField("C2H5OH", db_column="C2H5OH", null=True, blank=True)
    co = models.FloatField("CO", db_column="CO", null=True, blank=True)
    h2 = models.FloatField("H2", db_column="H2", null=True, blank=True)
    o2 = models.FloatField("O2", db_column="O2", null=True, blank=True)
    voc = models.FloatField("VOC", db_column="VOC", null=True, blank=True)

    humidity_inner = models.FloatField("内部湿度", db_column="humidity_inner", null=True, blank=True)
    temperature_inner = models.FloatField("内部温度", db_column="temperature_inner", null=True, blank=True)

    # 图片列你表里叫 image；为了兼容你 views 里排除 image_path，这里字段名仍叫 image_path
    image_path = models.CharField("图片路径", max_length=100, db_column="image", null=True, blank=True)

    notes = models.CharField("备注", max_length=512, db_column="notes", null=True, blank=True)
    is_complete = models.BooleanField("是否完成", db_column="is_complete")

    class Meta:
        db_table = "environment_data"
        managed = False
        verbose_name = "环境数据"
        verbose_name_plural = "环境数据"
        indexes = [
            models.Index(fields=["device", "reported_at"]),
            models.Index(fields=["pigsty", "reported_at"]),
        ]

    def __str__(self) -> str:
        ts = self.reported_at.strftime("%Y-%m-%d %H:%M:%S") if self.reported_at else "N/A"
        return f"EnvData<{ts}>"


# ========= 告警表（Django 管理表） =========
class Alarm(TimeStampedModel):
    """
    告警（ORM管理）
    如果你不需要这个表，可以删除该模型，或在 Meta 里加 managed=False 映射已有表。
    """
    LEVEL_INFO = "info"
    LEVEL_WARN = "warning"
    LEVEL_CRIT = "critical"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "提示"),
        (LEVEL_WARN, "告警"),
        (LEVEL_CRIT, "严重"),
    ]

    # Device 是 managed=False，建议关闭数据库级 FK 约束
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="alarms",
        verbose_name="设备",
        db_constraint=False,
    )

    level = models.CharField("告警级别", max_length=16, choices=LEVEL_CHOICES, default=LEVEL_WARN, db_index=True)
    message = models.CharField("告警内容", max_length=255, blank=True, default="")
    is_active = models.BooleanField("是否未处理", default=True, db_index=True)
    occurred_at = models.DateTimeField("发生时间", db_index=True)

    class Meta:
        db_table = "alarm"
        verbose_name = "告警"
        verbose_name_plural = "告警"
        indexes = [
            models.Index(fields=["is_active", "level"]),
            models.Index(fields=["device", "occurred_at"]),
        ]

    def __str__(self) -> str:
        code = self.device.device_code if self.device else ""
        ts = self.occurred_at.strftime("%Y-%m-%d %H:%M:%S") if self.occurred_at else "N/A"
        return f"Alarm<{code}:{self.level}:{ts}>"