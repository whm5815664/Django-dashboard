DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",  # 数据库引擎
        "NAME": "web_database",  # 数据库名称
        "HOST": "127.0.0.1",  # 数据库地址，本机 ip 地址 127.0.0.1
        "PORT": 3306,  # 端口
        "USER": "root",  # 数据库用户名
        "PASSWORD": "",  # 数据库密码
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
    # 远程 MySQL 数据库：柑橘数据库
    "pig": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "pig",
        "HOST": "47.99.61.189",
        "PORT": 3307,
        "USER": "zb25",
        "PASSWORD": "zb123456",
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
}

数据库映射关系：
default：本地数据库
pig：环境远程监测数据库

远程数据库（pig）表名映射关系
environment_data：环境监控数据表
device：设备表

