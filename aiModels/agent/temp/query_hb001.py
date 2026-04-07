import os, sys
sys.path.insert(0, 'E:/code/Django/Django-dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connections
import json

with connections['pig'].cursor() as cursor:
    cursor.execute('''
        SELECT 
            COUNT(*) as total_count,
            MIN(collected_time) as first_time,
            MAX(collected_time) as last_time,
            AVG(temperature) as avg_temp,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            AVG(humidity) as avg_humidity,
            MIN(humidity) as min_humidity,
            MAX(humidity) as max_humidity,
            AVG(CO2) as avg_co2,
            MIN(CO2) as min_co2,
            MAX(CO2) as max_co2
        FROM environment_data 
        WHERE pigsty_id = 1
    ''')
    row = cursor.fetchone()
    print(json.dumps({
        'total_count': row[0],
        'time_range': f"{row[1]} ~ {row[2]}",
        'temperature': {'avg': round(row[3], 2), 'min': row[4], 'max': row[5]},
        'humidity': {'avg': round(row[6], 2), 'min': row[7], 'max': row[8]},
        'co2': {'avg': round(row[9], 2), 'min': row[10], 'max': row[11]}
    }, ensure_ascii=False, indent=2))