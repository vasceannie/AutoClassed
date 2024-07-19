import streamlit as st
import streamlit_shadcn_ui as stscn
from pandas import DataFrame
from pygwalker.api.streamlit import StreamlitRenderer
import pandas as pd
from st_pages import show_pages_from_config, add_page_title
import sqlite3


def connect_to_database(db_file_path: str) -> sqlite3.Connection:
    """
    Connects to the SQLite database.

    Args:
        db_file_path (str): The path to the SQLite database file.

    Returns:
        sqlite3.Connection: The database connection.
    """
    try:
        return sqlite3.connect(db_file_path)
    except Exception as e:
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
    try:
        df = pd.read_sql_query(f"SELECT * FROM main.{db_name}", conn)
        if df is None or df.empty:
            raise ValueError("No data returned from SQL query")
        return df
    except sqlite3.OperationalError as e:
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
    try:
        conn = connect_to_database(db_file_path)
        clean_data = import_data_from_db(db_name, conn)
        conn.close()
        return clean_data
    except Exception as e:
        st.error(f"Error loading clean data: {e}")
        return None


def main():
    """
    The main function.
    """
    st.title("Data Explorer", anchor=None, help=None)
    show_pages_from_config()

    db_file_path = "spend_intake.db"
    db_name = "spend_data_raw"

    with st.spinner("Loading clean data..."):
        clean_data = load_clean_data(db_file_path, db_name)
    if clean_data is not None:
        with st.spinner("Loading data explorer..."):
            StreamlitRenderer(clean_data).explorer()
    else:
        st.error("Error loading clean data")


if __name__ == "__main__":
    main()
