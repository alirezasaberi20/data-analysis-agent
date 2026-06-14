import io
import uuid
import contextlib
import traceback
import warnings
import math
from pathlib import Path
from collections import Counter, defaultdict

from langchain_core.tools import tool
from backend.database.connection import get_engine
from backend.config import CHART_OUTPUT_DIR

# Modules the sandbox is allowed to import
_ALLOWED_MODULES = {
    "warnings": warnings,
    "math": math,
    "collections": __import__("collections"),
    "Counter": Counter,
    "defaultdict": defaultdict,
    "re": __import__("re"),
    "datetime": __import__("datetime"),
    "itertools": __import__("itertools"),
    "functools": __import__("functools"),
    "statistics": __import__("statistics"),
    "json": __import__("json"),
    "textwrap": __import__("textwrap"),
    "scipy": None,  # lazy-loaded below
    "scipy.stats": None,
    "sklearn": None,
    "sklearn.preprocessing": None,
}

# Lazy-load optional modules
try:
    import scipy
    import scipy.stats
    _ALLOWED_MODULES["scipy"] = scipy
    _ALLOWED_MODULES["scipy.stats"] = scipy.stats
except ImportError:
    pass

try:
    import sklearn
    import sklearn.preprocessing
    _ALLOWED_MODULES["sklearn"] = sklearn
    _ALLOWED_MODULES["sklearn.preprocessing"] = sklearn.preprocessing
except ImportError:
    pass


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Restricted import that only allows pre-approved modules."""
    if name in _ALLOWED_MODULES and _ALLOWED_MODULES[name] is not None:
        return _ALLOWED_MODULES[name]
    # Handle "from X import Y"
    for allowed_name, mod in _ALLOWED_MODULES.items():
        if name == allowed_name and mod is not None:
            return mod
    raise ImportError(
        f"Module '{name}' is not available. "
        f"Pre-loaded: pd, np, plt, sns, warnings, math, collections, re, datetime, itertools, json"
    )


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
    import tabulate as _tabulate_mod

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
            "__import__": _safe_import,
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
            "IndexError": IndexError,
            "RuntimeError": RuntimeError,
            "StopIteration": StopIteration,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "any": any,
            "all": all,
            "reversed": reversed,
            "repr": repr,
            "format": format,
            "chr": chr,
            "ord": ord,
            "divmod": divmod,
            "pow": pow,
        },
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "engine": engine,
        "save_chart": save_chart,
        "warnings": warnings,
        "math": math,
        "Counter": Counter,
        "defaultdict": defaultdict,
    }

    # Suppress common matplotlib/seaborn warnings that clutter output
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, safe_globals)
        output = stdout_capture.getvalue()
    except Exception:
        plt.close("all")
        partial_output = stdout_capture.getvalue()
        error_msg = f"Execution Error:\n{traceback.format_exc()}"
        parts = []
        if partial_output.strip():
            parts.append(partial_output.strip())
        if saved_charts:
            parts.append("\n".join(f"CHART_SAVED: {p}" for p in saved_charts))
        parts.append(error_msg)
        return "\n".join(parts)
    finally:
        warnings.resetwarnings()

    if saved_charts:
        chart_lines = "\n".join(f"CHART_SAVED: {p}" for p in saved_charts)
        output = (output + "\n" + chart_lines).strip()

    return output if output.strip() else "Code executed successfully (no output)."


PythonExecutionTool = python_execution_tool
