from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """
    抽象基类：所有表通用的创建/更新时间（仅用于 ORM 管理表）
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# 柑橘基地表 base
class Base(models.Model):
    base_id = models.CharField('基地编号', max_length=10, primary_key=True) # primary_key
    base_name = models.CharField('基地名称', max_length=20)
    longitude = models.FloatField('经度')
    latitude = models.FloatField('纬度')
    province_name = models.CharField('省份', max_length=10)
    city_name = models.CharField('城市', max_length=10)
    base_description = models.CharField('描述', max_length=50)
    base_pic = models.CharField('描述', max_length=50)

    class Meta:
        db_table = 'base'  # 确保与数据库表名一致
        verbose_name = '柑橘基地表'
        managed = False  # 禁止django自动添加id主键


class Device(models.Model):
    """
    设备：映射现有 MySQL 表 devices（managed=False）
    """
    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    STATUS_ALARM = "alarm"

    STATUS_CHOICES = [
        (STATUS_ONLINE, "在线"),
        (STATUS_OFFLINE, "离线"),
        (STATUS_ALARM, "告警"),
    ]

    name = models.CharField("设备名称", max_length=64, db_column="device_name")
    code = models.CharField("设备编号", max_length=64, unique=True, db_column="device_code")

    # 与柑橘基地 Base 表的关联，使用 base.base_id 作为外键
    base = models.ForeignKey(
        Base,
        db_column="base_id",     # 对应数据库中的 base_id 字段
        to_field="base_id",      # 引用 Base.base_id 作为主键
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="所属基地",
    )

    location = models.CharField("位置信息", max_length=128, blank=True, default="")
    status = models.CharField("在线状态", max_length=16, choices=STATUS_CHOICES, default=STATUS_OFFLINE, db_index=True)

    # 地理位置信息
    longitude = models.DecimalField("经度", max_digits=10, decimal_places=6, null=True, blank=True, db_column="longitude")
    latitude = models.DecimalField("纬度", max_digits=10, decimal_places=6, null=True, blank=True, db_column="latitude")

    # devices.last_report_time
    last_seen = models.DateTimeField("最后上报时间", db_column="last_report_time", null=True, blank=True, db_index=True)

    # 对齐表中已有时间列
    created_at = models.DateTimeField("创建时间", db_column="created_at", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", db_column="updated_at", auto_now=True)

    class Meta:
        db_table = "devices"
        managed = False  # 映射现有表，禁止Django自动管理
        verbose_name = "设备"
        verbose_name_plural = "设备"
        indexes = [
            models.Index(fields=["base", "status"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code or ''})"


class DeviceReading(models.Model):
    """
    设备上报：映射现有 MySQL 表 sensor_readings1（managed=False）
    注意：只保留你目前确认存在的列，避免再出现 Unknown column。
    """
    id = models.BigAutoField(primary_key=True, db_column="id")

    # 如表里有 device_name 列可保留；如果没有就删掉这行
    device_name = models.CharField("设备名", max_length=64, db_column="device_name", null=True, blank=True)

    reported_at = models.DateTimeField("上报时间", db_column="collected_at", db_index=True)

    temperature = models.DecimalField("温度(℃)", max_digits=6, decimal_places=2, db_column="temperature", null=True, blank=True)
    humidity = models.DecimalField("湿度(%)", max_digits=6, decimal_places=2, db_column="humidity", null=True, blank=True)

    co2_ppm = models.IntegerField("CO2(ppm)", db_column="co2_ppm", null=True, blank=True)
    h2_ppm = models.IntegerField("H2(ppm)", db_column="h2_ppm", null=True, blank=True)
    co_ppm = models.IntegerField("CO(ppm)", db_column="co_ppm", null=True, blank=True)

    c2h5oh = models.DecimalField("C2H5OH", max_digits=10, decimal_places=3, db_column="c2h5oh", null=True, blank=True)
    voc = models.DecimalField("VOC", max_digits=10, decimal_places=3, db_column="voc", null=True, blank=True)
    o2 = models.DecimalField("O2", max_digits=10, decimal_places=3, db_column="o2", null=True, blank=True)
    c2h4 = models.DecimalField("C2H4", max_digits=10, decimal_places=3, db_column="c2h4", null=True, blank=True)

    image_path = models.CharField("图片相对路径", max_length=255, db_column="image_path", null=True, blank=True)

    class Meta:
        db_table = "sensor_readings1"
        managed = False
        verbose_name = "设备上报"
        verbose_name_plural = "设备上报"

    def __str__(self) -> str:
        ts = self.reported_at.strftime("%Y-%m-%d %H:%M:%S") if self.reported_at else "N/A"
        return f"Reading<{ts}>"


class Alarm(TimeStampedModel):
    """
    告警（ORM管理）
    """
    LEVEL_INFO = "info"
    LEVEL_WARN = "warning"
    LEVEL_CRIT = "critical"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "提示"),
        (LEVEL_WARN, "告警"),
        (LEVEL_CRIT, "严重"),
    ]

    # 注意：Device 是 managed=False，建议关闭数据库级 FK 约束
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
        code = self.device.code if self.device else ""
        ts = self.occurred_at.strftime("%Y-%m-%d %H:%M:%S") if self.occurred_at else "N/A"
        return f"Alarm<{code}:{self.level}:{ts}>"
