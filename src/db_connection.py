"""
db_connection.py — MS-SQL Database Connection Helper
=====================================================
Provides a reusable connection engine and helper functions
for the SupplyChainControlTower database.
"""

import os
import yaml
import pyodbc
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus


def load_config(config_path=None):
    """Load configuration from config.yaml."""
    if config_path is None:
        # Look for config.yaml in project root
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config.yaml"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_connection_string(config=None):
    """Build MS-SQL connection string from config."""
    if config is None:
        config = load_config()

    db = config["database"]
    driver = db["driver"]
    server = db["server"]
    database = db["database"]

    if db.get("trusted_connection", True):
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
        )
    else:
        username = db["username"]
        password = db["password"]
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
        )
    return conn_str


def get_engine(config=None):
    """Create SQLAlchemy engine for MS-SQL."""
    conn_str = get_connection_string(config)
    connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
    engine = create_engine(connection_url, fast_executemany=True)
    return engine


def get_pyodbc_connection(config=None):
    """Get a raw pyodbc connection (for bulk operations)."""
    conn_str = get_connection_string(config)
    return pyodbc.connect(conn_str)


def test_connection(config=None):
    """Test database connectivity and print status."""
    try:
        engine = get_engine(config)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DB_NAME() AS db_name"))
            row = result.fetchone()
            print(f"✅ Connected to MS-SQL: {row[0]}")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure SQL Server is running")
        print("   2. Check server name in config.yaml")
        print("   3. Ensure ODBC Driver 17 for SQL Server is installed")
        print("   4. Run star_schema.sql in SSMS first to create the database")
        return False


def load_dataframe_to_sql(df, table_name, engine=None, if_exists="append", schema="dbo"):
    """
    Load a pandas DataFrame into an MS-SQL table.
    
    Parameters:
        df: pandas DataFrame
        table_name: Target table name (without schema)
        engine: SQLAlchemy engine (created if None)
        if_exists: 'append', 'replace', or 'fail'
        schema: Database schema (default 'dbo')
    
    Returns:
        Number of rows loaded
    """
    if engine is None:
        engine = get_engine()
    
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=1000
    )
    print(f"   ✅ Loaded {len(df):,} rows → dbo.{table_name}")
    return len(df)


def execute_query(query, engine=None):
    """Execute a query and return results as DataFrame."""
    if engine is None:
        engine = get_engine()
    return pd.read_sql(query, engine)


def truncate_table(table_name, engine=None):
    """Truncate a table (for idempotent reloads)."""
    if engine is None:
        engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE dbo.{table_name}"))
        conn.commit()
    print(f"   🗑️  Truncated dbo.{table_name}")


# ── Quick test when run directly ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Testing MS-SQL Connection")
    print("=" * 60)
    test_connection()
