from django.db import models

# 数据库中表类

# Create your models here.
# 当年地区柑橘产量表 screen_Citrus
class Citrus(models.Model):
    area = models.CharField('地区', max_length=50, unique=True)
    value = models.FloatField('产量')

# 全国柑橘年度总产量表 screen_Citrus_production_history
class Citrus_production_history(models.Model):
    year = models.IntegerField('年份')
    production_volume = models.IntegerField('年产量')

# 地区总产量表 screen_Citrus_production_history_area
class Citrus_production_history_area(models.Model):
    date = models.DateField('日期')
    production_volume = models.FloatField('产量')
    area = models.CharField('地区', max_length=50)
    
    class Meta:
        db_table = 'screen_Citrus_production_history_area'
        verbose_name = '地区每日总产量表'
        managed = False
        

# 地区每月品种总产量表 screen_citrusvariety_production_history_area
class Citrus_variety_production_history_area(models.Model):
    date = models.DateField('日期')
    variety = models.CharField('品种', max_length=50)
    production_volume = models.FloatField('产量')
    area = models.CharField('地区', max_length=50)

    class Meta:
        db_table = 'screen_citrusvariety_production_history_area'
        verbose_name = '地区每月品种总产量表'
        managed = False
    

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




# ------------远程数据库---------------------------------------------

# 远程数据库 pig 中的环境数据表 environment_data
class EnvironmentData(models.Model):
    id = models.AutoField(primary_key=True)
    CO2 = models.FloatField('二氧化碳浓度')
    temperature = models.FloatField('温度')
    humidity = models.FloatField('湿度')
    collected_time = models.DateTimeField('采集时间')
    device_id = models.IntegerField('设备ID')
    pigsty_id = models.IntegerField('库房ID')
    C2H4 = models.FloatField('乙烯浓度')
    C2H5OH = models.FloatField('乙醇浓度')
    VOC = models.FloatField('VOC浓度')
    H2 = models.FloatField('氢气浓度')
    image = models.CharField('图片路径', max_length=255)
    

    class Meta:
        db_table = 'environment_data'  # 远程库 中的表名
        managed = False  # 不由 Django 迁移管理
