import random
from datetime import date, timedelta
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, Float, Date, ForeignKey, text
)
from backend.database.connection import get_engine


def seed_database(force: bool = False):
    engine = get_engine()
    metadata = MetaData()

    if not force:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        if "products" in inspector.get_table_names():
            return

    products = Table(
        "products", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False),
        Column("category", String(50), nullable=False),
        Column("unit_price", Float, nullable=False),
    )

    regions = Table(
        "regions", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(50), nullable=False),
        Column("country", String(50), nullable=False),
    )

    sales_reps = Table(
        "sales_reps", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False),
        Column("region_id", Integer, ForeignKey("regions.id"), nullable=False),
        Column("hire_date", Date, nullable=False),
    )

    sales = Table(
        "sales", metadata,
        Column("id", Integer, primary_key=True),
        Column("product_id", Integer, ForeignKey("products.id"), nullable=False),
        Column("sales_rep_id", Integer, ForeignKey("sales_reps.id"), nullable=False),
        Column("region_id", Integer, ForeignKey("regions.id"), nullable=False),
        Column("sale_date", Date, nullable=False),
        Column("quantity", Integer, nullable=False),
        Column("total_amount", Float, nullable=False),
        Column("discount_pct", Float, default=0.0),
    )

    customers = Table(
        "customers", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False),
        Column("email", String(100)),
        Column("region_id", Integer, ForeignKey("regions.id"), nullable=False),
        Column("signup_date", Date, nullable=False),
    )

    metadata.drop_all(engine)
    metadata.create_all(engine)

    random.seed(42)

    product_data = [
        {"id": 1, "name": "Widget Pro", "category": "Electronics", "unit_price": 49.99},
        {"id": 2, "name": "Widget Lite", "category": "Electronics", "unit_price": 29.99},
        {"id": 3, "name": "Data Cable", "category": "Accessories", "unit_price": 9.99},
        {"id": 4, "name": "Smart Sensor", "category": "Electronics", "unit_price": 79.99},
        {"id": 5, "name": "Power Bank", "category": "Accessories", "unit_price": 39.99},
        {"id": 6, "name": "Cloud License", "category": "Software", "unit_price": 199.99},
        {"id": 7, "name": "Analytics Suite", "category": "Software", "unit_price": 299.99},
        {"id": 8, "name": "IoT Gateway", "category": "Electronics", "unit_price": 149.99},
        {"id": 9, "name": "USB Hub", "category": "Accessories", "unit_price": 19.99},
        {"id": 10, "name": "Security Module", "category": "Software", "unit_price": 99.99},
    ]

    region_data = [
        {"id": 1, "name": "North America", "country": "USA"},
        {"id": 2, "name": "Europe", "country": "Germany"},
        {"id": 3, "name": "Asia Pacific", "country": "Japan"},
        {"id": 4, "name": "Latin America", "country": "Brazil"},
        {"id": 5, "name": "Middle East", "country": "UAE"},
    ]

    rep_names = [
        "Alice Johnson", "Bob Smith", "Carlos Rivera", "Diana Chen",
        "Erik Muller", "Fatima Al-Rashid", "George Tanaka",
        "Hannah Lee", "Ivan Petrov", "Julia Santos",
    ]
    rep_data = []
    for i, name in enumerate(rep_names, 1):
        rep_data.append({
            "id": i,
            "name": name,
            "region_id": (i % 5) + 1,
            "hire_date": date(2021, 1, 1) + timedelta(days=random.randint(0, 365)),
        })

    customer_names = [
        "Acme Corp", "Globex Inc", "Initech", "Umbrella Corp", "Soylent Corp",
        "Stark Industries", "Wayne Enterprises", "Cyberdyne Systems",
        "Oscorp", "LexCorp", "Wonka Industries", "Aperture Science",
        "Tyrell Corp", "Massive Dynamic", "Dharma Initiative",
    ]
    customer_data = []
    for i, name in enumerate(customer_names, 1):
        customer_data.append({
            "id": i,
            "name": name,
            "email": f"contact@{name.lower().replace(' ', '')}.com",
            "region_id": (i % 5) + 1,
            "signup_date": date(2022, 1, 1) + timedelta(days=random.randint(0, 365)),
        })

    # Generate 2 years of sales: 2023–2024, with a deliberate Q3 2024 dip
    sales_data = []
    sale_id = 1
    start_date = date(2023, 1, 1)
    end_date = date(2024, 12, 31)

    current = start_date
    while current <= end_date:
        daily_sales = random.randint(3, 12)

        # Simulate Q3 2024 drop (July–Sept 2024)
        if current.year == 2024 and current.month in (7, 8, 9):
            daily_sales = random.randint(1, 5)
            discount_boost = random.uniform(0.10, 0.25)
        else:
            discount_boost = 0.0

        for _ in range(daily_sales):
            prod = random.choice(product_data)
            rep = random.choice(rep_data)
            qty = random.randint(1, 20)
            discount = round(random.uniform(0, 0.15) + discount_boost, 2)
            total = round(prod["unit_price"] * qty * (1 - discount), 2)

            sales_data.append({
                "id": sale_id,
                "product_id": prod["id"],
                "sales_rep_id": rep["id"],
                "region_id": rep["region_id"],
                "sale_date": current,
                "quantity": qty,
                "total_amount": total,
                "discount_pct": discount,
            })
            sale_id += 1

        current += timedelta(days=1)

    with engine.begin() as conn:
        conn.execute(products.insert(), product_data)
        conn.execute(regions.insert(), region_data)
        conn.execute(sales_reps.insert(), rep_data)
        conn.execute(customers.insert(), customer_data)

        batch_size = 500
        for i in range(0, len(sales_data), batch_size):
            conn.execute(sales.insert(), sales_data[i : i + batch_size])

    print(f"Seeded database with {len(sales_data)} sales records across 2 years.")
