import streamlit as st
from pandas import DataFrame
from pygwalker.api.streamlit import StreamlitRenderer
import pandas as pd
import sqlite3
import logging

logging.basicConfig(
    level=logging.ERROR,
    filename="app.log",
    filemode="a",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def connect_to_database(db_file_path: str) -> sqlite3.Connection:
    """
    Connects to the SQLite database.

    Args:
        db_file_path (str): The path to the SQLite database file.

    Returns:
        sqlite3.Connection: The database connection.
    """
    print("Connecting to database")
    try:
        conn = sqlite3.connect(db_file_path)
        print("Connected to database")
        return conn
    except Exception as e:
        print("Error connecting to database:", e)
        st.error(f"Error connecting to database: {e}")
        raise


def import_data_from_db(db_name: str, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Imports cleaned data from the database.

    Args:
        db_name (str): The name of the database.
        conn (sqlite3.Connection): The database connection.

    Returns:
        pandas.DataFrame: The cleaned data.
    """
    print("Importing data from database")
    try:
        df = pd.read_sql_query(f"SELECT * FROM main.{db_name}", conn)
        if not df.empty:
            # TODO: Add implementation
            print("Data imported successfully")
            pass
        else:
            print("No data returned from SQL query")
            raise ValueError("No data returned from SQL query")
        return df
    except sqlite3.OperationalError as e:
        print("Error executing SQL query:", e)
        st.error(f"Error executing SQL query: {e}")
        raise


@st.cache_data
def load_clean_data(db_file_path: str, db_name: str) -> DataFrame | None:
    """
    Loads cleaned data from the database.

    Args:
        db_file_path (str): The path to the SQLite database file.
        db_name (str): The name of the database.

    Returns:
        pandas.DataFrame: The cleaned data.
    """
    print("Loading clean data")
    try:
        with connect_to_database(db_file_path) as conn:
            clean_data = import_data_from_db(db_name, conn)
        print("Clean data loaded successfully")
        return clean_data
    except sqlite3.DatabaseError as e:
        print("Error connecting to database:", e)
        st.error(f"Error connecting to database: {e}")
        logging.error(f"Error connecting to database: {e}")
    except Exception as e:
        print("Error loading clean data:", e)
        st.error(f"Error loading clean data: {e}")
        return None


def main():
    """
    The main function.
    """
    print("Starting main function")
    st.title("Data Explorer", anchor=None, help=None)

    db_file_path = "spend_intake.db"
    db_name = "spend_data_raw"

    with st.spinner("Loading clean data..."):
        clean_data = load_clean_data(db_file_path, db_name)
    if clean_data is not None:
        with st.spinner("Loading data explorer..."):
            print("Loading data explorer")
            StreamlitRenderer(clean_data).explorer()
    else:
        st.error("Error loading clean data")


if __name__ == "__main__":
    print("Running main")
    main()
