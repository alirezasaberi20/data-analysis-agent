"""Tests for the database layer."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.connection import get_engine, get_db_schema, execute_sql
from backend.database.sample_data import seed_database


class TestDatabase:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_engine_creation(self):
        engine = get_engine()
        assert engine is not None

    def test_schema_retrieval(self):
        schema = get_db_schema()
        assert "products" in schema
        assert "sales" in schema
        assert "regions" in schema
        assert "sales_reps" in schema
        assert "customers" in schema

    def test_execute_select(self):
        results = execute_sql("SELECT COUNT(*) as cnt FROM products")
        assert len(results) == 1
        assert results[0]["cnt"] == 10

    def test_execute_sales_query(self):
        results = execute_sql(
            "SELECT COUNT(*) as cnt FROM sales WHERE sale_date >= '2024-07-01' AND sale_date < '2024-10-01'"
        )
        assert len(results) == 1
        assert results[0]["cnt"] > 0

    def test_join_query(self):
        results = execute_sql("""
            SELECT p.name, SUM(s.total_amount) as revenue
            FROM sales s
            JOIN products p ON s.product_id = p.id
            GROUP BY p.name
            ORDER BY revenue DESC
            LIMIT 5
        """)
        assert len(results) == 5
        assert "name" in results[0]
        assert "revenue" in results[0]

    def test_dangerous_query_blocked(self):
        from backend.tools.sql_tool import sql_query_tool
        result = sql_query_tool.invoke({"query": "DROP TABLE products"})
        assert "not allowed" in result

    def test_q3_dip_exists(self):
        results = execute_sql("""
            SELECT
                CASE
                    WHEN CAST(strftime('%m', sale_date) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1'
                    WHEN CAST(strftime('%m', sale_date) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2'
                    WHEN CAST(strftime('%m', sale_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
                    ELSE 'Q4'
                END as quarter,
                SUM(total_amount) as revenue
            FROM sales
            WHERE strftime('%Y', sale_date) = '2024'
            GROUP BY quarter
            ORDER BY quarter
        """)
        q_map = {r["quarter"]: r["revenue"] for r in results}
        assert q_map["Q3"] < q_map["Q2"], "Q3 should have lower revenue than Q2 (deliberate dip)"
