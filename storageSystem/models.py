from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """
    抽象基类：所有表通用的创建/更新时间
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ColdRoom(TimeStampedModel):
    """
    冷库
    """
    name = models.CharField("冷库名称", max_length=64, unique=True)
    code = models.CharField("冷库编号", max_length=64, unique=True)
    address = models.CharField("地址/场地", max_length=255, blank=True, default="")
    description = models.CharField("描述", max_length=255, blank=True, default="")
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        db_table = "coldroom"
        verbose_name = "冷库"
        verbose_name_plural = "冷库"

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Device(TimeStampedModel):
    """
    设备（冷库传感器/网关/温控设备等）
    """
    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    STATUS_ALARM = "alarm"

    STATUS_CHOICES = [
        (STATUS_ONLINE, "在线"),
        (STATUS_OFFLINE, "离线"),
        (STATUS_ALARM, "告警"),
    ]

    name = models.CharField("设备名称", max_length=64)
    code = models.CharField("设备编号", max_length=64, unique=True)

    cold_room = models.ForeignKey(
        ColdRoom,
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="所属冷库",
    )

    location = models.CharField("位置信息", max_length=128, blank=True, default="")
    status = models.CharField("在线状态", max_length=16, choices=STATUS_CHOICES, default=STATUS_OFFLINE, db_index=True)

    last_seen = models.DateTimeField("最后上报时间", null=True, blank=True, db_index=True)

    # 可选：设备类型/厂商等
    device_type = models.CharField("设备类型", max_length=32, blank=True, default="")
    vendor = models.CharField("厂商", max_length=64, blank=True, default="")

    class Meta:
        db_table = "device"
        verbose_name = "设备"
        verbose_name_plural = "设备"
        indexes = [
            models.Index(fields=["cold_room", "status"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class DeviceReading(TimeStampedModel):
    """
    设备上报数据（可选但很推荐，用于 dashboard 趋势图/历史数据追溯）
    例如：温度、湿度、电量等（你后续可以按真实数据结构扩展字段）
    """
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="readings",
        verbose_name="设备",
    )

    reported_at = models.DateTimeField("上报时间", db_index=True)

    # 示例指标（按你的业务改）
    temperature = models.FloatField("温度", null=True, blank=True)
    humidity = models.FloatField("湿度", null=True, blank=True)
    battery = models.FloatField("电量", null=True, blank=True)

    class Meta:
        db_table = "device_reading"
        verbose_name = "设备上报"
        verbose_name_plural = "设备上报"
        indexes = [
            models.Index(fields=["device", "reported_at"]),
        ]

    def __str__(self) -> str:
        return f"Reading<{self.device.code}@{self.reported_at:%Y-%m-%d %H:%M:%S}>"


class Alarm(TimeStampedModel):
    """
    告警（可以来自设备上报，也可以来自规则引擎/AI 分析）
    """
    LEVEL_INFO = "info"
    LEVEL_WARN = "warning"
    LEVEL_CRIT = "critical"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "提示"),
        (LEVEL_WARN, "告警"),
        (LEVEL_CRIT, "严重"),
    ]

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="alarms",
        verbose_name="设备",
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
        return f"Alarm<{self.device.code}:{self.level}:{self.occurred_at:%Y-%m-%d %H:%M:%S}>"
