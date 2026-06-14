import re
import chromadb
from chromadb.config import Settings
from backend.config import CHROMA_PERSIST_DIR
from backend.database.connection import get_engine


def _safe_id(raw: str) -> str:
    """Convert any string into a ChromaDB-safe unique ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_").lower()


class SchemaVectorStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _init_store(self):
        if self._initialized:
            return
        self._client = chromadb.Client(Settings(
            persist_directory=CHROMA_PERSIST_DIR,
            anonymized_telemetry=False,
        ))
        self._collection = self._client.get_or_create_collection(
            name="schema_context",
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = True

    def index_schema(self):
        self._init_store()

        existing = self._collection.count()
        if existing > 0:
            return

        from sqlalchemy import inspect as sa_inspect
        engine = get_engine()
        inspector = sa_inspect(engine)

        documents = []
        ids = []
        metadatas = []

        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            col_descriptions = [f"{c['name']} ({c['type']})" for c in columns]

            doc = f"Table '{table_name}' has columns: {', '.join(col_descriptions)}."
            documents.append(doc)
            ids.append(f"table_{_safe_id(table_name)}")
            metadatas.append({"table_name": table_name, "type": "schema"})

            for col in columns:
                col_name = col["name"]
                col_type = str(col["type"])
                col_doc = f"Column '{col_name}' in table '{table_name}' is of type {col_type}."
                documents.append(col_doc)
                ids.append(f"col_{_safe_id(table_name)}_{_safe_id(col_name)}")
                metadatas.append({
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": "column",
                })

        domain_docs = [
            "To explore a dataset, use df.describe(), df.info(), df.head(), and check df.dtypes.",
            "Distribution analysis uses histograms (sns.histplot), KDE plots, and box plots (sns.boxplot).",
            "Correlation analysis uses df.corr() and sns.heatmap() to visualize relationships between numeric columns.",
            "Scatter plots (sns.scatterplot) and pair plots (sns.pairplot) show relationships between variables.",
            "Categorical data is best visualized with count plots (sns.countplot) or bar charts.",
            "Q3 refers to July, August, and September. Q1 is Jan-Mar, Q2 is Apr-Jun, Q4 is Oct-Dec.",
            "For time-series data, group by date using strftime() in SQLite and plot trends over time.",
            "To compare groups, use GROUP BY in SQL or pandas groupby() with aggregation functions.",
            "Outlier detection can use IQR method, z-scores, or box plots.",
            "Feature importance and class separation can be explored with violin plots and grouped statistics.",
        ]
        for i, doc in enumerate(domain_docs):
            documents.append(doc)
            ids.append(f"domain_{i}")
            metadatas.append({"type": "domain_knowledge"})

        self._collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )

    def reindex_schema(self):
        """Drop existing collection and re-index from the current DB schema."""
        self._init_store()
        self._client.delete_collection("schema_context")
        self._collection = self._client.get_or_create_collection(
            name="schema_context",
            metadata={"hnsw:space": "cosine"},
        )
        self.index_schema()

    def query(self, question: str, n_results: int = 5) -> str:
        self._init_store()
        results = self._collection.query(
            query_texts=[question],
            n_results=n_results,
        )
        docs = results.get("documents", [[]])[0]
        return "\n".join(f"- {doc}" for doc in docs)
