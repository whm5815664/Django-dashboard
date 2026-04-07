#!/usr/bin/env python
"""
Django数据库统计脚本
提供表数据量统计、数值字段统计指标等

用法:
    python db_stats.py --db pig --tables environment_data,device,pig_pigsty
    python db_stats.py --db pig --table environment_data --stats pigsty_id
    python db_stats.py --db default --table base --summary
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


def get_table_counts(db, tables=None):
    from django.db import connections
    if tables is None:
        with connections[db].cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
    results = {}
    with connections[db].cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            results[table] = cursor.fetchone()[0]
    return results


def get_column_stats(db, table, column, where_clause=None):
    from django.db import connections
    where_sql = f"WHERE {column} IS NOT NULL"
    if where_clause:
        where_sql += f" AND {where_clause}"
    with connections[db].cursor() as cursor:
        cursor.execute(f"""
            SELECT 
                COUNT({column}) as count,
                MIN({column}) as min_val,
                MAX({column}) as max_val,
                AVG({column}) as avg_val,
                SUM({column}) as sum_val
            FROM {table}
            {where_sql}
        """)
        row = cursor.fetchone()
        return {
            'count': row[0],
            'min': float(row[1]) if row[1] is not None else None,
            'max': float(row[2]) if row[2] is not None else None,
            'avg': round(float(row[3]), 4) if row[3] is not None else None,
            'sum': float(row[4]) if row[4] is not None else None
        }


def get_table_summary(db, table):
    from django.db import connections
    with connections[db].cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = cursor.fetchall()
    col_info = []
    for col in columns:
        col_info.append({
            'name': col[0],
            'type': col[1],
            'null': col[2],
            'key': col[3],
            'default': col[4]
        })
    return {'table': table, 'count': count, 'columns': col_info}


def main():
    parser = argparse.ArgumentParser(description='Django数据库统计脚本')
    parser.add_argument('--db', choices=['default', 'pig'], default='default', help='数据库')
    parser.add_argument('--tables', type=str, help='统计表列表(逗号分隔)')
    parser.add_argument('--table', type=str, help='单个表名')
    parser.add_argument('--stats', type=str, help='统计字段名')
    parser.add_argument('--where', type=str, help='WHERE条件 (如: pigsty_id=1)')
    parser.add_argument('--summary', action='store_true', help='表结构摘要')
    parser.add_argument('--format', choices=['table', 'json'], default='table', help='输出格式')
    args = parser.parse_args()

    setup_django()

    try:
        if args.tables:
            tables = args.tables.split(',')
            counts = get_table_counts(args.db, tables)
            if args.format == 'json':
                print(json.dumps(counts, ensure_ascii=False, indent=2))
            else:
                print(f"{'表名':<25} {'记录数':>10}")
                print('-' * 37)
                for t, c in counts.items():
                    print(f"{t:<25} {c:>10}")
        elif args.stats and args.table:
            cols = args.stats.split(',')
            stats = {}
            for col in cols:
                stats[col] = get_column_stats(args.db, args.table, col.strip(), args.where)
            if args.format == 'json':
                print(json.dumps(stats, ensure_ascii=False, indent=2))
            else:
                print(f"表: {args.table}")
                for col, s in stats.items():
                    print(f"\n字段: {col}")
                    for k, v in s.items():
                        print(f"  {k}: {v}")
        elif args.summary and args.table:
            summary = get_table_summary(args.db, args.table)
            if args.format == 'json':
                print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"表: {summary['table']}")
                print(f"记录数: {summary['count']}")
                print(f"\n{'列名':<20} {'类型':<25} {'NULL':<6} {'键':<6} {'默认值'}")
                print('-' * 80)
                for col in summary['columns']:
                    print(f"{col['name']:<20} {col['type']:<25} {col['null']:<6} {col['key']:<6} {col['default']}")
        else:
            print("用法:")
            print("  --tables table1,table2    统计多个表记录数")
            print("  --table X --stats col1,col2  统计字段指标")
            print("  --table X --summary       表结构摘要")
    except Exception as e:
        print(f"统计错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
