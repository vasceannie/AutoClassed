import os
import sqlite3
import streamlit as st
import pandas as pd


def connect_to_db(db_file_path: str) -> sqlite3.Connection:
    """
    Connects to the SQLite database.

    Args:
        db_file_path (str): The path to the SQLite database file.

    Returns:
        sqlite3.Connection: The database connection.
    """
    try:
        # Check if the file exists
        if not os.path.exists(db_file_path):
            raise FileNotFoundError(f"Database file not found: {db_file_path}")

        # Check if the path is too long
        if len(db_file_path) > 255:
            raise ValueError("Database file path is too long")

        # Attempt to connect to the database
        return sqlite3.connect(db_file_path)
    except sqlite3.Error as e:
        st.error(f"SQLite error: {e}")
        raise
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        raise

# Example usage
db_file = "data/spend_intake.db"
conn = connect_to_db(db_file)
df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
conn.close()

st.dataframe(df)
