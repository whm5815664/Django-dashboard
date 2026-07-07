import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'

import pymysql
pymysql.install_as_MySQLdb()

import json
import time
import re
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_db_config(db_name):
    if db_name == 'pig':
        return {
            'host': '116.62.214.146',
            'port': 3306,
            'user': 'wyh22',
            'password': 'wyh123456',
            'database': 'pig',
            'charset': 'utf8mb4',
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30
        }
    elif db_name == 'default':
        return {
            'host': '127.0.0.1',
            'port': 3306,
            'user': 'root',
            'password': '',
            'database': 'web_database',
            'charset': 'utf8mb4',
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30
        }
    else:
        raise ValueError(f"Unknown database: {db_name}")

def execute_query(db_name, query, params=None, max_retries=3):
    config = get_db_config(db_name)
    last_error = None
    
    for attempt in range(max_retries):
        try:
            connection = pymysql.connect(**config)
            try:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, params)
                    query_upper = query.strip().upper()
                    if query_upper.startswith('SELECT') or query_upper.startswith('SHOW') or query_upper.startswith('DESCRIBE'):
                        results = cursor.fetchall()
                        return results
                    else:
                        connection.commit()
                        return {'affected_rows': cursor.rowcount}
            finally:
                connection.close()
            break
        except pymysql.err.OperationalError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1)
            continue
        except Exception as e:
            last_error = e
            break
    
    raise last_error

def parse_base_id(base_id):
    match = re.match(r'^([A-Za-z]+)(\d+)$', str(base_id))
    if match:
        return int(match.group(2))
    return int(base_id)

def main():
    if len(sys.argv) < 3:
        print("用法: python db_query.py <数据库> <查询> [参数]")
        print("示例: python db_query.py pig query_hb001_env")
        print("示例: python db_query.py default query_all_bases")
        print("示例: python db_query.py pig \"SELECT * FROM environment_data WHERE pigsty_id=1 LIMIT 5\"")
        print("\n预设查询:")
        for k, v in query_templates.items():
            print(f"  {k}")
        sys.exit(1)
    
    db_name = sys.argv[1]
    query_arg = sys.argv[2]
    params = None
    
    query_templates = {
        'query_hb001_env': "SELECT e.*, p.name as pigsty_name FROM environment_data e LEFT JOIN pig_pigsty p ON e.pigsty_id = p.id WHERE e.pigsty_id = 1 ORDER BY e.collected_time DESC LIMIT 10",
        'query_hb002_env': "SELECT e.*, p.name as pigsty_name FROM environment_data e LEFT JOIN pig_pigsty p ON e.pigsty_id = p.id WHERE e.pigsty_id = 2 ORDER BY e.collected_time DESC LIMIT 10",
        'query_base_info': "SELECT * FROM base WHERE base_id = %s",
        'query_all_bases': "SELECT * FROM base",
        'query_env_by_pigsty': "SELECT e.*, p.name as pigsty_name FROM environment_data e LEFT JOIN pig_pigsty p ON e.pigsty_id = p.id WHERE e.pigsty_id = %s ORDER BY e.collected_time DESC LIMIT 10",
        'query_devices': "SELECT * FROM device",
        'query_pigsty': "SELECT * FROM pig_pigsty",
        'query_farm': "SELECT * FROM pig_farm",
    }
    
    if query_arg in query_templates:
        query = query_templates[query_arg]
        if len(sys.argv) > 3:
            params_arg = sys.argv[3]
            try:
                params = json.loads(params_arg)
            except json.JSONDecodeError:
                params = (params_arg,)
    else:
        query = query_arg
        if len(sys.argv) > 3:
            try:
                params = json.loads(sys.argv[3])
            except json.JSONDecodeError:
                params = (sys.argv[3],)
    
    try:
        results = execute_query(db_name, query, params)
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == '__main__':
    main()