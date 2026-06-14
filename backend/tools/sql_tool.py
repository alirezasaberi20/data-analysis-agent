from langchain_core.tools import tool
from backend.database.connection import execute_sql, get_db_schema


@tool
def sql_query_tool(query: str) -> str:
    """Execute a SQL query against the sales database and return results.

    Args:
        query: A valid SQL SELECT query to execute against the database.

    Returns:
        Query results as a formatted string, or an error message.
    """
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
    upper = query.upper().strip()
    for kw in dangerous:
        if kw in upper and kw != "CREATE":
            return f"Error: {kw} statements are not allowed. Only SELECT queries are permitted."

    try:
        results = execute_sql(query)
        if not results:
            return "Query returned no results."

        if len(results) > 100:
            results = results[:100]
            truncated = True
        else:
            truncated = False

        header = " | ".join(results[0].keys())
        separator = "-" * len(header)
        rows = []
        for row in results:
            rows.append(" | ".join(str(v) for v in row.values()))

        output = f"{header}\n{separator}\n" + "\n".join(rows)
        if truncated:
            output += "\n... (truncated to 100 rows)"
        return output
    except Exception as e:
        return f"SQL Error: {str(e)}"


@tool
def get_schema_tool() -> str:
    """Get the database schema including all table names and column definitions.

    Returns:
        Database schema as a formatted string.
    """
    try:
        return get_db_schema()
    except Exception as e:
        return f"Error retrieving schema: {str(e)}"


SQLQueryTool = sql_query_tool
GetSchemaTool = get_schema_tool
