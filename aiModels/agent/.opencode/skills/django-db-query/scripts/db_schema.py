#!/usr/bin/env python
"""
Django数据库表结构查询脚本
查询表结构、列信息、索引等

用法:
    python db_schema.py --db pig --tables
    python db_schema.py --db pig --table environment_data
    python db_schema.py --db default --table base --indexes
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


def list_tables(db):
    from django.db import connections
    with connections[db].cursor() as cursor:
        cursor.execute("SHOW TABLES")
        return [row[0] for row in cursor.fetchall()]


def get_table_columns(db, table):
    from django.db import connections
    with connections[db].cursor() as cursor:
        cursor.execute(f"SHOW FULL COLUMNS FROM {table}")
        columns = cursor.fetchall()
    return [
        {
            'field': col[0],
            'type': col[1],
            'collation': col[2],
            'null': col[3],
            'key': col[4],
            'default': col[5],
            'extra': col[6],
            'privileges': col[7],
            'comment': col[8] if len(col) > 8 else ''
        }
        for col in columns
    ]


def get_table_indexes(db, table):
    from django.db import connections
    with connections[db].cursor() as cursor:
        cursor.execute(f"SHOW INDEX FROM {table}")
        indexes = cursor.fetchall()
    result = {}
    for idx in indexes:
        name = idx[2]
        if name not in result:
            result[name] = {
                'name': name,
                'unique': not bool(idx[1]),
                'columns': [],
                'cardinality': idx[6]
            }
        result[name]['columns'].append(idx[4])
    return list(result.values())


def main():
    parser = argparse.ArgumentParser(description='Django数据库表结构查询脚本')
    parser.add_argument('--db', choices=['default', 'pig'], default='default', help='数据库')
    parser.add_argument('--tables', action='store_true', help='列出所有表')
    parser.add_argument('--table', type=str, help='表名')
    parser.add_argument('--columns', action='store_true', help='显示列信息')
    parser.add_argument('--indexes', action='store_true', help='显示索引信息')
    parser.add_argument('--format', choices=['table', 'json'], default='table', help='输出格式')
    args = parser.parse_args()

    setup_django()

    try:
        if args.tables:
            tables = list_tables(args.db)
            if args.format == 'json':
                print(json.dumps(tables, ensure_ascii=False, indent=2))
            else:
                print(f"数据库 {args.db} 中的表:")
                for i, t in enumerate(tables, 1):
                    print(f"  {i}. {t}")
                print(f"\n共 {len(tables)} 个表")
        elif args.table:
            if args.columns or not args.indexes:
                columns = get_table_columns(args.db, args.table)
                if args.format == 'json':
                    print(json.dumps(columns, ensure_ascii=False, indent=2))
                else:
                    print(f"表: {args.table}")
                    print(f"\n{'字段':<20} {'类型':<25} {'NULL':<6} {'键':<6} {'默认值':<15} {'注释'}")
                    print('-' * 90)
                    for col in columns:
                        print(f"{col['field']:<20} {col['type']:<25} {col['null']:<6} {col['key']:<6} {str(col['default']):<15} {col['comment']}")
            if args.indexes:
                indexes = get_table_indexes(args.db, args.table)
                if args.format == 'json':
                    print(json.dumps(indexes, ensure_ascii=False, indent=2))
                else:
                    print(f"\n索引:")
                    for idx in indexes:
                        cols = ', '.join(idx['columns'])
                        unique_str = 'UNIQUE' if idx['unique'] else 'INDEX'
                        print(f"  {unique_str}: {idx['name']} ({cols})")
        else:
            print("用法:")
            print("  --tables              列出所有表")
            print("  --table X [--columns] 显示表列信息")
            print("  --table X --indexes   显示表索引")
    except Exception as e:
        print(f"查询错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
