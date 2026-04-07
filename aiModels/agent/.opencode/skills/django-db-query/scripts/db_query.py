#!/usr/bin/env python
"""
Django数据库查询脚本
支持本地数据库(default)和远程数据库(pig)的SQL查询

用法:
    python db_query.py --db default --sql "SELECT * FROM base LIMIT 10"
    python db_query.py --db pig --sql "SELECT * FROM pig_pigsty"
    python db_query.py --db pig --table environment_data --where "pigsty_id=1" --limit 50
    python db_query.py --db default --table base --columns base_id,base_name
"""
import argparse
import json
import os
import sys


def setup_django():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    django_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..', '..', '..'))
    sys.path.insert(0, django_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()


def query_sql(db, sql):
    from django.db import connections
    with connections[db].cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
    return columns, rows


def query_table(db, table, columns=None, where=None, order_by=None, limit=100):
    from django.db import connections
    col_str = ', '.join(columns) if columns else '*'
    sql = f"SELECT {col_str} FROM {table}"
    params = []
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    sql += f" LIMIT {limit}"
    with connections[db].cursor() as cursor:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
    return columns, rows


def format_output(columns, rows, fmt='table'):
    if fmt == 'json':
        data = [dict(zip(columns, row)) for row in rows]
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    elif fmt == 'csv':
        lines = [','.join(str(c) for c in columns)]
        for row in rows:
            lines.append(','.join(str(v) for v in row))
        return '\n'.join(lines)
    else:
        col_widths = [len(str(c)) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))
        header = ' | '.join(str(c).ljust(col_widths[i]) for i, c in enumerate(columns))
        separator = '-+-'.join('-' * col_widths[i] for i in range(len(columns)))
        lines = [header, separator]
        for row in rows:
            line = ' | '.join(str(val).ljust(col_widths[i]) for i, val in enumerate(row))
            lines.append(line)
        lines.append(f"\n共 {len(rows)} 条记录")
        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Django数据库查询脚本')
    parser.add_argument('--db', choices=['default', 'pig'], default='default', help='数据库')
    parser.add_argument('--sql', type=str, help='SQL查询语句')
    parser.add_argument('--table', type=str, help='表名')
    parser.add_argument('--columns', type=str, help='查询列名(逗号分隔)')
    parser.add_argument('--where', type=str, help='WHERE条件')
    parser.add_argument('--order-by', type=str, help='ORDER BY排序')
    parser.add_argument('--limit', type=int, default=100, help='限制返回条数')
    parser.add_argument('--format', choices=['table', 'json', 'csv'], default='table', help='输出格式')
    args = parser.parse_args()

    setup_django()

    try:
        if args.sql:
            columns, rows = query_sql(args.db, args.sql)
        elif args.table:
            cols = args.columns.split(',') if args.columns else None
            columns, rows = query_table(args.db, args.table, cols, args.where, args.order_by, args.limit)
        else:
            print("错误: 请指定 --sql 或 --table 参数")
            sys.exit(1)
        print(format_output(columns, rows, args.format))
    except Exception as e:
        print(f"查询错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
