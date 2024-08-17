import streamlit as st
from pygwalker.api.streamlit import StreamlitRenderer
import pandas as pd
import sqlite3

def connect_to_database(db_file_path: str) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(db_file_path)
        return conn
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        raise

def import_data_from_db(table_name: str, conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        # Use string formatting to insert the table name, but with proper escaping
        query = f"""
        SELECT * 
        FROM "{table_name}"
        WHERE classification_name IS NOT NULL OR valid != '';
        """
        df = pd.read_sql_query(query, conn)
        if df.empty:
            raise ValueError("No data returned from SQL query")
        return df
    except sqlite3.OperationalError as e:
        st.error(f"Error executing SQL query: {e}")
        raise

@st.cache_data
def load_clean_data(db_file_path: str, db_name: str) -> pd.DataFrame:
    try:
        with connect_to_database(db_file_path) as conn:
            clean_data = import_data_from_db(db_name, conn)
        return clean_data
    except Exception as e:
        st.error(f"Error loading clean data: {e}")
        return pd.DataFrame()  # Return an empty DataFrame instead of None

def main():
    st.set_page_config(layout="wide")  # Set wide layout
    st.title("Data Explorer")

    db_file_path = "spend_intake2.db"
    table_name = "AP_Items_For_Classification"

    with st.spinner("Loading clean data..."):
        clean_data = load_clean_data(db_file_path, table_name)
        
        if clean_data.empty:
            st.error("No data loaded. Please check your database and query.")
            return

        with st.spinner("Loading data explorer..."):
            try:
                # Initialize pygwalker
                pyg_html = StreamlitRenderer(clean_data)
                pyg_html.explorer()
            except Exception as e:
                st.error(f"Error initializing PyGWalker: {e}")
                st.exception(e)

if __name__ == "__main__":
    main()