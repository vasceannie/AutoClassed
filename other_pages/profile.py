import inspect
import logging
import os
import sqlite3
import threading
import time

import pandas as pd
import streamlit as st
from openai import OpenAI
from streamlit_ace import st_ace

from utils import OpenAIManager
from utils import openai_setup_instructions
from utils import summon_grid

thread = {}
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
openai_manager = OpenAIManager(client, assistant_id=ASSISTANT_ID)


def connect_to_db(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    if len(db_path) > 255:
        raise ValueError("Database file path is too long")
    return sqlite3.connect(db_path)


def create_thread() -> thread:
    return client.beta.threads.create()


def create_message(supplier_name: str, thread_id: str) -> object:
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=f"Please provide validity, classification, and comments for the supplier: {supplier_name}. Respond "
        f"with json please.",
    )
    return message


def get_supplier_id() -> str:
    return st.text_input("Enter Supplier ID")


def get_supplier_name(supplier_id: str, df: pd.DataFrame) -> str:
    return df.loc[df["supplier_id"] == supplier_id, "supplier_name"].values[0]


def start_supplier_processing(supplier_name: str, thread: thread, df: pd.DataFrame):
    threads[thread["id"]] = {"active": True, "output": None}
    thread = threading.Thread(
        target=process_supplier_result, args=(supplier_name, thread["id"], df)
    )
    thread.start()


def process_supplier_result(
    supplier_name: str, thread_id: str, df: pd.DataFrame, output: dict
):
    if "error" in output:
        st.error(f"Error: {output['error']}")
    else:
        st.success(f"Classification Completed: {output}")
        update_supplier_data(supplier_name, output, df)


def update_supplier_data(supplier_name: str, output: dict, df: pd.DataFrame):
    try:
        df.loc[df["supplier_id"] == output["supplier_id"], "classification_code"] = (
            output["classification_code"]
        )
        df.loc[df["supplier_id"] == output["supplier_id"], "classification_name"] = (
            output["classification_name"]
        )
        df.loc[df["supplier_id"] == output["supplier_id"], "valid"] = output["validity"]
        df.loc[df["supplier_id"] == output["supplier_id"], "comments"] = output[
            "comments"
        ]
    except KeyError:
        st.error(f"Supplier ID '{output['supplier_id']}' not found in the DataFrame")


def main(df):
    st.title("Tutorial: Optimizing Data for GPT")
    tab_data_prep, tab_query_openai = st.tabs(["Data Preparation", "Query OpenAI"])

    with tab_data_prep:
        with st.container():
            st.header("Creating a condensed view of our working data:")
            summon_grid(df)

            with st.expander("View Explanation"):
                tab_import_db, tab_extract_df, tab_display_table = st.tabs(
                    ["Import Database", "Extract into Dataframe", "Display Table"]
                )

                with tab_import_db:
                    st.markdown(
                        "We import `sqlite3` and `os` and define a function to establish a connection with our database and return a cursor object."
                    )
                    st.code(inspect.getsource(connect_to_db), language="python")

                with tab_extract_df:
                    st.markdown(
                        "We use `pandas` to execute a query against the database and store the results in a pandas dataframe."
                    )
                    code = """
                    import pandas as pd
    
                    db_file = "spend_intake.db"
                    conn = connect_to_db(db_file)
                    df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
                    conn.close()
                    """
                    st.code(code, language="python")

                with tab_display_table:
                    st.markdown("We use `ag_grid` to display the dataframe in a table.")
                    st.code(
                        """
                        AgGrid(data=df, gridOptions=GRID_OPTIONS, customButtons=CUSTOM_BUTTONS, options=OPTIONS)
                        """,
                        language="python",
                    )
                    st.markdown(
                        "Note that `AgGrid` is a wrapper for another library that has many parameters and arguments for its rendering."
                    )

        with tab_query_openai:
            col1, col2 = st.columns(2)
            with col1:
                with st.container(border=True):
                    st.subheader("Single Supplier Lookup")
                    supplier_id = get_supplier_id()
                    st.session_state.supplier_id = supplier_id
                    if st.button("Submit") and supplier_id:
                        if df["supplier_id"].isin([supplier_id]).any():
                            try:
                                supplier_name = get_supplier_name(supplier_id, df)
                                with st.status("Preparing for blastoff..."):
                                    st.write("Targeted Supplier Name:", supplier_name)
                                    time.sleep(2)
                                responses = openai_manager.process_supplier(
                                    supplier_name
                                )
                                st.write(f"Processed {len(responses)} responses for {supplier_name}")
                            except ValueError:
                                st.error("Invalid supplier ID")
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
                        else:
                            st.error("Supplier ID not found.")
                with col2:
                    with st.container(border=True):
                        st.markdown("### OpenAI API Key and Assistant ID Setup")
                        openai_setup_instructions(st)

            with st.expander("Under the Hood"):
                with st.container(border=True, height=500):
                    st.markdown("### Event Handler Inspector")
                    st_ace(
                        language="python",
                        theme="twilight",
                        readonly=True,
                        value=inspect.getsource(main),
                    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threads = {}
    db_file = "spend_intake.db"
    conn = connect_to_db(db_file)
    df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
    conn.close()
    main(df)
