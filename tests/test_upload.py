"""Tests for the file upload functionality."""

import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.connection import (
    get_table_info, load_dataframe_to_db, load_sql_file_to_db,
    drop_table, _sanitize_table_name,
)
from backend.database.sample_data import seed_database


class TestSanitizeTableName:
    def test_basic(self):
        assert _sanitize_table_name("my_data.csv") == "my_data"

    def test_spaces_and_special(self):
        assert _sanitize_table_name("My Data (2024).xlsx") == "my_data_2024"

    def test_starts_with_digit(self):
        assert _sanitize_table_name("2024_sales.csv") == "t_2024_sales"

    def test_empty(self):
        result = _sanitize_table_name(".csv")
        assert result.startswith("t_") or len(result) > 0


class TestLoadDataframe:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_load_csv_data(self):
        df = pd.DataFrame({
            "city": ["New York", "London", "Tokyo"],
            "population": [8_336_817, 8_982_000, 13_960_000],
        })
        result = load_dataframe_to_db(df, "test_cities")
        assert result["table_name"] == "test_cities"
        assert result["rows"] == 3

    def test_load_replaces_existing(self):
        df1 = pd.DataFrame({"x": [1, 2]})
        load_dataframe_to_db(df1, "test_replace")
        df2 = pd.DataFrame({"x": [10, 20, 30]})
        result = load_dataframe_to_db(df2, "test_replace")
        assert result["rows"] == 3

    def test_table_appears_in_info(self):
        df = pd.DataFrame({"col_a": [1], "col_b": ["hello"]})
        load_dataframe_to_db(df, "test_info_check")
        tables = get_table_info()
        names = [t["name"] for t in tables]
        assert "test_info_check" in names


class TestLoadSQL:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_create_and_insert(self):
        drop_table("test_sql_tbl")
        sql = """
        CREATE TABLE test_sql_tbl (id INTEGER PRIMARY KEY, val TEXT);
        INSERT INTO test_sql_tbl VALUES (1, 'hello');
        INSERT INTO test_sql_tbl VALUES (2, 'world');
        """
        new_tables = load_sql_file_to_db(sql)
        assert "test_sql_tbl" in new_tables


class TestDropTable:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_drop_existing(self):
        df = pd.DataFrame({"a": [1]})
        load_dataframe_to_db(df, "to_drop")
        assert drop_table("to_drop") is True

    def test_drop_nonexistent(self):
        assert drop_table("nonexistent_xyz") is False


class TestGetTableInfo:
    @classmethod
    def setup_class(cls):
        seed_database()

    def test_has_sample_tables(self):
        tables = get_table_info()
        names = [t["name"] for t in tables]
        assert "products" in names
        assert "sales" in names

    def test_table_structure(self):
        tables = get_table_info()
        products = next(t for t in tables if t["name"] == "products")
        assert products["rows"] == 10
        assert "name" in products["column_names"]


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_list_tables_endpoint(client):
    async with client as ac:
        response = await ac.get("/api/tables")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert len(data["tables"]) > 0


@pytest.mark.asyncio
async def test_upload_csv(client):
    csv_content = "name,age,score\nAlice,30,95\nBob,25,88\nCharlie,35,72\n"
    async with client as ac:
        response = await ac.post(
            "/api/upload",
            files={"file": ("test_upload.csv", csv_content.encode(), "text/csv")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "test_upload" in data["message"]
    assert "tables" in data


@pytest.mark.asyncio
async def test_upload_unsupported_type(client):
    async with client as ac:
        response = await ac.post(
            "/api/upload",
            files={"file": ("photo.jpg", b"fake", "image/jpeg")},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_table_endpoint(client):
    csv_content = "x,y\n1,2\n3,4\n"
    async with client as ac:
        await ac.post(
            "/api/upload",
            files={"file": ("to_delete_api.csv", csv_content.encode(), "text/csv")},
        )
        response = await ac.delete("/api/tables/to_delete_api")
    assert response.status_code == 200
