from sqlalchemy import inspect, text
from database import engine, connector

try:
    with engine.connect() as conn:
        # Test connection
        result = conn.execute(
            text("SELECT current_database(), current_user")
        )
        print("Connected successfully:", result.fetchone())

        # List existing tables
        inspector = inspect(conn)
        print("Existing tables:", inspector.get_table_names())

finally:
    engine.dispose()
    connector.close()