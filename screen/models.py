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
    

# 柑橘基地表 screen_basemap
class Basemap(models.Model):
    baseID = models.CharField('基地编号', max_length=10, primary_key=True) # primary_key
    baseName = models.CharField('基地名称', max_length=20)
    longitude = models.FloatField('经度')
    latitude = models.FloatField('纬度')
    province = models.CharField('省份', max_length=10)
    city = models.CharField('城市', max_length=10)
    description = models.CharField('描述', max_length=50)

    class Meta:
        db_table = 'screen_basemap'  # 确保与数据库表名一致
        verbose_name = '柑橘基地表'
        managed = False  # 禁止django自动添加id主键


# ---------------------------------------------------------
