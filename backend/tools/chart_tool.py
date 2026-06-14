import json
import uuid
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

from langchain_core.tools import tool
from backend.config import CHART_OUTPUT_DIR


@tool
def chart_generator_tool(chart_spec: str) -> str:
    """Generate a chart from a JSON specification.

    Args:
        chart_spec: A JSON string with the following structure:
            {
                "chart_type": "bar" | "line" | "pie" | "scatter" | "heatmap",
                "title": "Chart Title",
                "x_label": "X axis label",
                "y_label": "Y axis label",
                "data": {
                    "x": [...],
                    "y": [...],
                    "labels": [...] (optional, for pie charts),
                    "series": [{"name": "...", "y": [...]}] (optional, for multi-series)
                }
            }

    Returns:
        Path to the generated chart image file, or an error message.
    """
    try:
        spec = json.loads(chart_spec)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {str(e)}"

    try:
        chart_type = spec.get("chart_type", "bar")
        title = spec.get("title", "Chart")
        x_label = spec.get("x_label", "")
        y_label = spec.get("y_label", "")
        data = spec.get("data", {})

        sns.set_theme(style="whitegrid", palette="muted")
        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == "bar":
            x = data.get("x", [])
            if "series" in data:
                import numpy as np
                n_series = len(data["series"])
                width = 0.8 / n_series
                x_pos = np.arange(len(x))
                for i, series in enumerate(data["series"]):
                    offset = (i - n_series / 2 + 0.5) * width
                    ax.bar(x_pos + offset, series["y"], width, label=series["name"])
                ax.set_xticks(x_pos)
                ax.set_xticklabels(x, rotation=45, ha="right")
                ax.legend()
            else:
                y = data.get("y", [])
                colors = sns.color_palette("muted", len(x))
                ax.bar(x, y, color=colors)
                plt.xticks(rotation=45, ha="right")

        elif chart_type == "line":
            x = data.get("x", [])
            if "series" in data:
                for series in data["series"]:
                    ax.plot(x, series["y"], marker="o", label=series["name"], linewidth=2)
                ax.legend()
            else:
                y = data.get("y", [])
                ax.plot(x, y, marker="o", linewidth=2, color=sns.color_palette("muted")[0])
            plt.xticks(rotation=45, ha="right")

        elif chart_type == "pie":
            labels = data.get("labels", data.get("x", []))
            values = data.get("y", [])
            colors = sns.color_palette("muted", len(labels))
            ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90)
            ax.axis("equal")

        elif chart_type == "scatter":
            x = data.get("x", [])
            y = data.get("y", [])
            ax.scatter(x, y, alpha=0.7, s=60, color=sns.color_palette("muted")[0])

        elif chart_type == "heatmap":
            import numpy as np
            matrix = np.array(data.get("matrix", []))
            x_labels = data.get("x", [])
            y_labels = data.get("y_labels", [])
            sns.heatmap(matrix, xticklabels=x_labels, yticklabels=y_labels,
                        annot=True, fmt=".1f", cmap="YlOrRd", ax=ax)

        else:
            return f"Unsupported chart type: {chart_type}"

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        if x_label:
            ax.set_xlabel(x_label, fontsize=11)
        if y_label:
            ax.set_ylabel(y_label, fontsize=11)

        plt.tight_layout()

        chart_id = uuid.uuid4().hex[:8]
        filename = f"chart_{chart_id}.png"
        filepath = Path(CHART_OUTPUT_DIR) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return f"Chart saved: {filepath}"

    except Exception:
        plt.close("all")
        return f"Chart generation error:\n{traceback.format_exc()}"


ChartGeneratorTool = chart_generator_tool
