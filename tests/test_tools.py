"""Tests for the tool layer."""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.sample_data import seed_database
from backend.tools.sql_tool import sql_query_tool, get_schema_tool
from backend.tools.python_tool import python_execution_tool
from backend.tools.chart_tool import chart_generator_tool


class TestSQLTool:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_valid_query(self):
        result = sql_query_tool.invoke({"query": "SELECT COUNT(*) as cnt FROM products"})
        assert "cnt" in result
        assert "10" in result

    def test_schema_tool(self):
        result = get_schema_tool.invoke({})
        assert "products" in result
        assert "sales" in result

    def test_invalid_query(self):
        result = sql_query_tool.invoke({"query": "SELECT * FROM nonexistent_table"})
        assert "Error" in result or "error" in result.lower()

    def test_write_blocked(self):
        result = sql_query_tool.invoke({"query": "DELETE FROM products WHERE id = 1"})
        assert "not allowed" in result


class TestPythonTool:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_basic_execution(self):
        result = python_execution_tool.invoke({"code": "print(2 + 2)"})
        assert "4" in result

    def test_pandas_available(self):
        result = python_execution_tool.invoke({
            "code": "df = pd.read_sql('SELECT * FROM products LIMIT 3', engine)\nprint(len(df))"
        })
        assert "3" in result

    def test_error_handling(self):
        result = python_execution_tool.invoke({"code": "raise ValueError('test error')"})
        assert "Error" in result


class TestChartTool:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_bar_chart(self):
        spec = json.dumps({
            "chart_type": "bar",
            "title": "Test Bar Chart",
            "x_label": "Category",
            "y_label": "Value",
            "data": {
                "x": ["A", "B", "C"],
                "y": [10, 20, 30]
            }
        })
        result = chart_generator_tool.invoke({"chart_spec": spec})
        assert "Chart saved:" in result

    def test_line_chart(self):
        spec = json.dumps({
            "chart_type": "line",
            "title": "Test Line Chart",
            "data": {
                "x": ["Jan", "Feb", "Mar"],
                "y": [100, 150, 120]
            }
        })
        result = chart_generator_tool.invoke({"chart_spec": spec})
        assert "Chart saved:" in result

    def test_pie_chart(self):
        spec = json.dumps({
            "chart_type": "pie",
            "title": "Test Pie",
            "data": {
                "labels": ["A", "B", "C"],
                "y": [40, 35, 25]
            }
        })
        result = chart_generator_tool.invoke({"chart_spec": spec})
        assert "Chart saved:" in result

    def test_invalid_json(self):
        result = chart_generator_tool.invoke({"chart_spec": "not json"})
        assert "Invalid JSON" in result
