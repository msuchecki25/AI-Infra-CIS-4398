import os

from dotenv import load_dotenv
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine

load_dotenv()

connector = Connector(refresh_strategy="LAZY")

def getconn():
    return connector.connect(
        os.environ["INSTANCE_CONNECTION_NAME"],
        "psycopg",
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        db=os.environ["DB_NAME"],
        ip_type=IPTypes.PUBLIC,
    )

engine = create_engine(
    "postgresql+psycopg://",
    creator=getconn,
    pool_pre_ping=True,
)