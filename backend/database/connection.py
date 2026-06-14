import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from backend.config import DATABASE_URL

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        _engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def get_db_schema() -> str:
    engine = get_engine()
    inspector = inspect(engine)
    schema_parts = []

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_defs = []
        for col in columns:
            col_defs.append(f"  {col['name']} {col['type']}")
        schema_parts.append(
            f"TABLE: {table_name}\n" + "\n".join(col_defs)
        )

    return "\n\n".join(schema_parts)


def get_table_info() -> list[dict]:
    """Return a list of tables with their column count and row count."""
    engine = get_engine()
    inspector = inspect(engine)
    tables = []
    with engine.connect() as conn:
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
            tables.append({
                "name": table_name,
                "columns": len(columns),
                "rows": row_count,
                "column_names": [c["name"] for c in columns],
            })
    return tables


def _sanitize_table_name(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if not name or name[0].isdigit():
        name = "t_" + name
    return name


def load_dataframe_to_db(df: pd.DataFrame, table_name: str, if_exists: str = "replace") -> dict:
    """Load a pandas DataFrame into the database as a new table."""
    engine = get_engine()
    table_name = _sanitize_table_name(table_name)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    return {
        "table_name": table_name,
        "rows": len(df),
        "columns": list(df.columns),
    }


def load_sql_file_to_db(sql_content: str) -> list[str]:
    """Execute raw SQL statements (CREATE TABLE, INSERT, etc.) and return created table names."""
    engine = get_engine()
    inspector = inspect(engine)
    tables_before = set(inspector.get_table_names())

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    inspector = inspect(engine)
    tables_after = set(inspector.get_table_names())
    new_tables = list(tables_after - tables_before)
    return new_tables


def drop_table(table_name: str) -> bool:
    """Drop a table from the database. Returns True if dropped."""
    engine = get_engine()
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
    return True


def execute_sql(query: str) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query))
        if result.returns_rows:
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows
        conn.commit()
        return [{"status": "Query executed successfully", "rows_affected": result.rowcount}]
