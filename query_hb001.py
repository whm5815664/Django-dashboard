import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from storageSystem.models import DeviceReading

data = DeviceReading.objects.using('pig').filter(pigsty_id=1).order_by('-reported_at')[:5]

print('='*60)
print('华中农业大学柑橘智能体 - 基地 HB001 环境监测数据')
print('='*60)
for item in data:
    ts = item.reported_at.strftime('%Y-%m-%d %H:%M:%S') if item.reported_at else 'N/A'
    print(f"采集时间：{ts} | 温度：{item.temperature}°C | 湿度：{item.humidity}% | CO2: {item.co2}ppm")
print('='*60)
