"""Individual agent nodes for the analysis workflow."""

import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from backend.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.tools.sql_tool import sql_query_tool, get_schema_tool
from backend.tools.python_tool import python_execution_tool
from backend.tools.chart_tool import chart_generator_tool
from backend.vector_store.store import SchemaVectorStore
from backend.database.connection import get_table_info


def _get_llm(temperature: float = 0.0):
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
    )


def _extract_user_question(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _detect_target_tables(question: str) -> list[str]:
    """Detect which database tables the user is likely asking about."""
    tables = get_table_info()
    question_lower = question.lower()

    BUILTIN_TABLES = {"products", "regions", "sales_reps", "sales", "customers"}
    user_tables = [t for t in tables if t["name"] not in BUILTIN_TABLES]
    builtin_tables = [t for t in tables if t["name"] in BUILTIN_TABLES]

    matched = []
    for t in tables:
        name = t["name"].lower()
        # Match table name or close variants in the question
        if name in question_lower:
            matched.append(t["name"])
        # Also match without underscores (e.g. "iris" matches "iris")
        clean_name = name.replace("_", " ")
        if clean_name in question_lower:
            matched.append(t["name"])

    if matched:
        return list(set(matched))

    # If user says generic things like "the dataset", "my data", "uploaded data"
    # and there are user-uploaded tables, prefer those
    generic_cues = ["dataset", "my data", "uploaded", "the data", "this data",
                    "the file", "my file", "imported", "csv", "excel"]
    if any(cue in question_lower for cue in generic_cues) and user_tables:
        return [t["name"] for t in user_tables]

    return [t["name"] for t in tables]


def _build_table_summary() -> str:
    """Build a concise summary of all tables for the LLM."""
    tables = get_table_info()
    BUILTIN = {"products", "regions", "sales_reps", "sales", "customers"}
    lines = []
    for t in tables:
        label = "(built-in sample)" if t["name"] in BUILTIN else "(user-uploaded)"
        cols = ", ".join(t["column_names"])
        lines.append(f"  - {t['name']} {label}: {t['rows']} rows, columns: [{cols}]")
    return "\n".join(lines)


# ---- Planner Node ----

def planner_node(state: dict) -> dict:
    """Analyze the user question and create an execution plan."""
    messages = state["messages"]
    user_question = _extract_user_question(messages)

    vector_store = SchemaVectorStore()
    context = vector_store.query(user_question)
    schema = get_schema_tool.invoke({})
    table_summary = _build_table_summary()
    target_tables = _detect_target_tables(user_question)

    llm = _get_llm()
    plan_prompt = SystemMessage(content=f"""You are a data analysis planner. Given a user's question, create a
step-by-step analysis plan. You have access to a SQL database with multiple tables.

AVAILABLE TABLES:
{table_summary}

TARGET TABLE(S) for this question: {', '.join(target_tables)}

FULL DATABASE SCHEMA:
{schema}

RELEVANT CONTEXT:
{context}

IMPORTANT RULES:
- Focus ONLY on the target table(s) listed above. Do NOT query unrelated tables.
- If the user asks to "visualize the dataset", "show distributions", "describe the data",
  etc., plan to use Python (pandas + matplotlib/seaborn) for exploration.
- For exploratory requests, plan steps like: load data, compute statistics, generate
  distribution plots, correlation heatmaps, scatter plots, etc.
- For specific analytical questions, plan SQL queries + Python analysis + charts.
- The Python tool has matplotlib (plt), seaborn (sns), pandas (pd), numpy (np),
  and a save_chart() function to save plots.

Create a concise plan with numbered steps. Each step should specify what to do.
Output ONLY the plan, no preamble.""")

    response = llm.invoke([plan_prompt, HumanMessage(content=user_question)])

    return {
        "messages": messages + [AIMessage(content=f"**Analysis Plan:**\n{response.content}")],
        "plan": response.content,
        "schema": schema,
        "context": context,
        "target_tables": target_tables,
    }


# ---- SQL Agent Node ----

def sql_agent_node(state: dict) -> dict:
    """Generate and execute SQL queries based on the plan."""
    messages = state["messages"]
    plan = state.get("plan", "")
    schema = state.get("schema", "")
    target_tables = state.get("target_tables", [])
    user_question = _extract_user_question(messages)

    llm = _get_llm()
    tools = [sql_query_tool]
    llm_with_tools = llm.bind_tools(tools)

    sql_prompt = SystemMessage(content=f"""You are a SQL expert. Based on the analysis plan, write and execute SQL queries
to gather the needed data. Use the sql_query_tool to execute queries.

TARGET TABLE(S): {', '.join(target_tables)}
IMPORTANT: Only query the target tables. Do NOT query unrelated tables.

DATABASE SCHEMA:
{schema}

ANALYSIS PLAN:
{plan}

Write precise SQL queries. Use JOINs, GROUP BY, aggregations as needed.
For SQLite date filtering, use strftime().
Execute each query using the tool.""")

    conversation = [sql_prompt, HumanMessage(content=user_question)]
    response = llm_with_tools.invoke(conversation)

    new_messages = list(messages) + [response]

    sql_results = []
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = sql_query_tool.invoke(tool_call["args"])
            sql_results.append(result)
            tool_msg = ToolMessage(
                content=result,
                tool_call_id=tool_call["id"],
            )
            new_messages.append(tool_msg)

        followup_messages = [sql_prompt, response]
        for i, tool_call in enumerate(response.tool_calls):
            followup_messages.append(ToolMessage(
                content=sql_results[i],
                tool_call_id=tool_call["id"],
            ))
        followup_messages.append(
            HumanMessage(content="Summarize the SQL query results. Format key data points clearly.")
        )
        followup = llm.invoke(followup_messages)
        new_messages.append(followup)

    return {
        "messages": new_messages,
        "sql_results": sql_results,
    }


# ---- Python Analysis Node ----

def python_agent_node(state: dict) -> dict:
    """Run Python analysis on the data — works with or without prior SQL results."""
    messages = state["messages"]
    sql_results = state.get("sql_results", [])
    plan = state.get("plan", "")
    target_tables = state.get("target_tables", [])

    llm = _get_llm()
    tools = [python_execution_tool]
    llm_with_tools = llm.bind_tools(tools)

    sql_data_summary = "\n---\n".join(sql_results[:5]) if sql_results else "No SQL results yet."
    tables_str = ", ".join(target_tables) if target_tables else "all tables"

    python_prompt = SystemMessage(content=f"""You are a Python data analyst. Write and execute Python code to analyze the data.

You have access to:
- pandas as `pd`, numpy as `np`, matplotlib.pyplot as `plt`, seaborn as `sns`
- A SQLAlchemy `engine` — load data with: df = pd.read_sql("SELECT * FROM table_name", engine)
- A `save_chart()` function — after creating a plot, call save_chart() to save it

TARGET TABLE(S): {tables_str}
Load data from these tables using pd.read_sql().

SQL RESULTS (if any):
{sql_data_summary}

ANALYSIS PLAN:
{plan}

IMPORTANT GUIDELINES:
- ALWAYS load data from the target tables using pd.read_sql().
- After loading, ALWAYS separate numeric and categorical columns:
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    categorical_cols = df.select_dtypes(exclude='number').columns.tolist()
- For "visualize the dataset" or "show distributions":
  * Use df.describe() and print statistics
  * Create histograms/distribution plots for numeric columns ONLY
  * Create count plots for categorical columns
- For correlation analysis:
  * ALWAYS use df[numeric_cols].corr() — NEVER use df.corr() on the full DataFrame
  * Use sns.heatmap(df[numeric_cols].corr(), annot=True, cmap='coolwarm')
- For scatter plots: use sns.scatterplot with hue= for categorical grouping
- Print all findings with print()
- Create clear, well-labeled charts with titles
- Use plt.figure(figsize=(10, 6)) before each new chart
- Call save_chart() after EACH plot to save it (do NOT call plt.show())

Example pattern for saving a chart:
    plt.figure(figsize=(10, 6))
    sns.histplot(df['column'], kde=True)
    plt.title('Distribution of Column')
    save_chart()
""")

    user_question = _extract_user_question(messages)
    response = llm_with_tools.invoke([python_prompt, HumanMessage(content=user_question)])

    new_messages = list(messages) + [response]
    analysis_output = ""
    python_chart_paths = []

    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = python_execution_tool.invoke(tool_call["args"])
            analysis_output += result + "\n"

            for line in result.split("\n"):
                if line.startswith("CHART_SAVED: "):
                    python_chart_paths.append(line.replace("CHART_SAVED: ", "").strip())

            tool_msg = ToolMessage(
                content=result,
                tool_call_id=tool_call["id"],
            )
            new_messages.append(tool_msg)

    return {
        "messages": new_messages,
        "analysis_results": analysis_output,
        "python_chart_paths": python_chart_paths,
    }


# ---- Chart Agent Node ----

def chart_agent_node(state: dict) -> dict:
    """Generate additional charts if needed (skips if Python already made enough)."""
    messages = state["messages"]
    sql_results = state.get("sql_results", [])
    analysis_results = state.get("analysis_results", "")
    plan = state.get("plan", "")
    python_chart_paths = state.get("python_chart_paths", [])
    target_tables = state.get("target_tables", [])

    # If Python agent already generated charts, skip the JSON chart tool
    if python_chart_paths:
        return {
            "messages": messages,
            "chart_paths": python_chart_paths,
        }

    llm = _get_llm()
    tools = [chart_generator_tool]
    llm_with_tools = llm.bind_tools(tools)

    chart_prompt = SystemMessage(content=f"""You are a data visualization expert. Based on the analysis results,
create appropriate charts using the chart_generator_tool.

The tool accepts a JSON string with this structure:
{{
    "chart_type": "bar" | "line" | "pie" | "scatter" | "heatmap",
    "title": "Chart Title",
    "x_label": "X Label",
    "y_label": "Y Label",
    "data": {{
        "x": [...],
        "y": [...]
    }}
}}

For multi-series: use "series": [{{"name": "...", "y": [...]}}]

TARGET TABLE(S): {', '.join(target_tables)}

ANALYSIS RESULTS:
{analysis_results}

SQL DATA:
{chr(10).join(sql_results[:3])}

PLAN: {plan}

Create 1-3 relevant charts using real data from the results.""")

    user_question = _extract_user_question(messages)
    response = llm_with_tools.invoke([chart_prompt, HumanMessage(content=user_question)])

    new_messages = list(messages) + [response]
    chart_paths = []

    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = chart_generator_tool.invoke(tool_call["args"])
            if "Chart saved:" in result:
                path = result.replace("Chart saved: ", "").strip()
                chart_paths.append(path)
            tool_msg = ToolMessage(
                content=result,
                tool_call_id=tool_call["id"],
            )
            new_messages.append(tool_msg)

    return {
        "messages": new_messages,
        "chart_paths": chart_paths,
    }


# ---- Insight Agent Node ----

def insight_agent_node(state: dict) -> dict:
    """Synthesize all findings into a comprehensive insight report."""
    messages = state["messages"]
    sql_results = state.get("sql_results", [])
    analysis_results = state.get("analysis_results", "")
    chart_paths = state.get("chart_paths", [])
    plan = state.get("plan", "")
    target_tables = state.get("target_tables", [])

    llm = _get_llm(temperature=0.3)

    charts_info = "\n".join(f"- Chart: {p}" for p in chart_paths) if chart_paths else "No charts generated."

    insight_prompt = SystemMessage(content=f"""You are a senior data analyst. Synthesize all the analysis results
into a clear, comprehensive report.

TARGET TABLE(S): {', '.join(target_tables)}

ANALYSIS PLAN:
{plan}

SQL RESULTS:
{chr(10).join(sql_results[:5]) if sql_results else 'No SQL results.'}

PYTHON ANALYSIS OUTPUT:
{analysis_results if analysis_results else 'No Python analysis output.'}

GENERATED CHARTS:
{charts_info}

Write a comprehensive response that:
1. Directly answers the user's original question
2. Highlights key findings with specific numbers
3. Identifies patterns, distributions, or trends
4. Provides observations and recommendations where relevant
5. Mentions the generated charts

FORMATTING RULES:
- Use proper markdown formatting throughout.
- For ANY tabular data (correlation matrices, comparisons, statistics), use markdown tables:
  | Column A | Column B | Column C |
  |----------|----------|----------|
  | value    | value    | value    |
- NEVER output raw pipe-separated text or plain text tables. Always use proper markdown table syntax.
- Use headers, bold, bullet points for readability.
- Keep the report concise but thorough.""")

    user_question = _extract_user_question(messages)

    response = llm.invoke([
        insight_prompt,
        HumanMessage(content=f"Original question: {user_question}\n\nProvide the final analysis report."),
    ])

    return {
        "messages": messages + [AIMessage(content=response.content)],
        "final_report": response.content,
    }
