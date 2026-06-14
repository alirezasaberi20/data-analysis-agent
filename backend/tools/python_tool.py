import io
import uuid
import contextlib
import traceback
from pathlib import Path

from langchain_core.tools import tool
from backend.database.connection import get_engine
from backend.config import CHART_OUTPUT_DIR


@tool
def python_execution_tool(code: str) -> str:
    """Execute Python code for data analysis. The code has access to pandas (pd),
    numpy (np), matplotlib.pyplot (plt), seaborn (sns), and a SQLAlchemy engine
    via the `engine` variable.

    Use pd.read_sql(query, engine) to load any table.
    Use plt.savefig(save_chart()) to save plots — save_chart() returns a file path.
    Use print() to output text results.

    Args:
        code: Python code to execute.

    Returns:
        The stdout output from the code execution, or an error message.
        If charts were saved, their paths are included in the output.
    """
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    engine = get_engine()
    saved_charts = []

    def save_chart(filename: str | None = None) -> str:
        """Save the current matplotlib figure and return the file path."""
        chart_id = uuid.uuid4().hex[:8]
        fname = filename or f"chart_{chart_id}.png"
        if not fname.endswith(".png"):
            fname += ".png"
        filepath = Path(CHART_OUTPUT_DIR) / fname
        filepath.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(filepath), dpi=150, bbox_inches="tight")
        plt.close("all")
        saved_charts.append(str(filepath))
        return str(filepath)

    safe_globals = {
        "__builtins__": {
            "print": print,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "bool": bool,
            "isinstance": isinstance,
            "type": type,
            "True": True,
            "False": False,
            "None": None,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "hasattr": hasattr,
            "getattr": getattr,
        },
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "engine": engine,
        "save_chart": save_chart,
    }

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, safe_globals)
        output = stdout_capture.getvalue()

        if saved_charts:
            chart_lines = "\n".join(f"CHART_SAVED: {p}" for p in saved_charts)
            output = (output + "\n" + chart_lines).strip()

        return output if output.strip() else "Code executed successfully (no output)."
    except Exception:
        plt.close("all")
        return f"Execution Error:\n{traceback.format_exc()}"


PythonExecutionTool = python_execution_tool
