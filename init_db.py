from pathlib import Path
from database import engine, connector

sql_folder = Path(__file__).parent / "rawberry-db" / "init"

try:
    with engine.begin() as conn:
        for filename in ["01_extensions.sql", "02_schema.sql"]:
            sql = (sql_folder / filename).read_text()

            conn.exec_driver_sql(sql)
            print(f"Executed {filename}")

    print("Database initialized successfully!")

finally:
    engine.dispose()
    connector.close()