import inspect
import json
import logging
import os
import sqlite3
import threading
import time
import pandas as pd
import streamlit as st
from openai import OpenAI
from st_aggrid import AgGrid

gridOptions = {
    "columnDefs": [
        {"field": "id", "headerName": "ID", "width": 75},
        {"field": "supplier_id", "headerName": "Supplier ID", "width": 100},
        {"field": "supplier_name", "headerName": "Supplier Name", "width": 300},
        {"field": "valid", "headerName": "Is Valid", "width": 100},
        {
            "field": "classification_code",
            "headerName": "Supplier Class Code",
            "width": 250,
        },
        {
            "field": "classification_name",
            "headerName": "Supplier Classification Description",
            "width": 250,
        },
        {"field": "comments", "headerName": "Comments", "width": 300},
    ],
    "enableRangeSelection": True,
    "pagination": True,
    "statusBar": {
        "statusPanels": [
            {"statusPanel": "agTotalAndFilteredRowCountComponent"},
            {"statusPanel": "agTotalRowCountComponent"},
            {"statusPanel": "agFilteredRowCountComponent"},
            {"statusPanel": "agSelectedRowCountComponent"},
            {"statusPanel": "agAggregationComponent"},
        ]
    },
    "sideBar": {
        "toolPanels": [
            {
                "id": "columns",
                "labelDefault": "Columns",
                "labelKey": "columns",
                "iconKey": "columns",
                "toolPanel": "agColumnsToolPanel",
                "minWidth": 225,
                "maxWidth": 225,
                "width": 225,
            },
            {
                "id": "filters",
                "labelDefault": "Filters",
                "labelKey": "filters",
                "iconKey": "filter",
                "toolPanel": "agFiltersToolPanel",
                "minWidth": 180,
                "maxWidth": 400,
                "width": 250,
            },
        ],
        "position": "left",
        "defaultToolPanel": "filters",
    },
    "defaultColDef": {"sortable": True, "filter": True},
}
custom_buttons = [
    {
        "name": "Save",
        "feather": "Save",
        "hasText": True,
        "commands": ["save-state", ["response", "saved"]],
        "response": "saved",
        "style": {"bottom": "calc(50% - 4.25rem)", "right": "0.4rem"},
    },
    {
        "name": "Run",
        "feather": "Play",
        "primary": True,
        "hasText": True,
        "showWithIcon": True,
        "commands": ["submit"],
        "style": {"bottom": "0.44rem", "right": "0.4rem"},
    },
    {
        "name": "Command",
        "feather": "Terminal",
        "primary": True,
        "hasText": True,
        "commands": ["openCommandPallete"],
        "style": {"bottom": "3.5rem", "right": "0.4rem"},
    },
]
options = {
    "displayIndentGuides": False,
    "highlightIndentGuides": True,
    "wrap": "free",
    "foldStyle": "markbegin",
    "enableLiveAutocompletion": True,
}


def connect_to_db(db_file_path: str) -> sqlite3.Connection:
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


# Get secrets
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")

# Initialise the OpenAI client, and retrieve the assistant
client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(ASSISTANT_ID)


def create_thread():
    return client.beta.threads.create()


def initialize_thread_id():
    if "thread_id" not in st.session_state:
        thread = create_thread()
        st.session_state.thread_id = thread.id


def get_supplier_id():
    return st.text_input("Enter Supplier ID")


def get_supplier_name(supplier_id, df):
    return df.loc[df["supplier_id"] == supplier_id, "supplier_name"].values[0]


def start_supplier_processing(supplier_name, thread_id):
    threads[thread_id] = {"active": True, "output": None}
    thread = threading.Thread(
        target=process_supplier_result, args=(supplier_name, thread_id, df)
    )
    thread.start()
    threads[thread_id]["thread"] = thread


def process_supplier_result(thread_id, output, df):
    if "error" in output:
        st.error(f"Error: {output['error']}")
    else:
        st.success(f"Classification Completed: {output}")
        update_supplier_data(output, df)


def update_supplier_data(output, df):
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
        st.error("Supplier ID not found in the DataFrame")


code = """
               import pandas as pd


    db_file = "spend_intake.db"
    conn = connect_to_db(db_file)
    df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
    conn.close()
                """


def main(threads, df):
    initialize_thread_id()
    st.title("Tutorial: Optimizing Data for GPT", anchor=None, help=None)
    taba, tabb = st.tabs(["Data Preparation", "Query OpenAI"])
    with taba:
        st.header("Creating a condensed view of our working data:")
        AgGrid(
            data=df,
            gridOptions=gridOptions,
            customButtons=custom_buttons,
            options=options,
        )
        with st.expander("View Explanation"):
            with st.container():
                tab1, tab2, tab3 = st.tabs(
                    ["Import Database", "Extract into Dataframe", "Display Table"]
                )
                with tab1:
                    st.markdown(
                        "We begin by using `import sqlite3` and `import os` to define a function that will "
                        "establish a connection with our database and return a cursor object. This will be used to execute queries against the database:"
                    )
                    function_code = inspect.getsource(connect_to_db)
                    st.code(function_code, language="python")
                with tab2:
                    st.markdown(
                        "Now we use the `pandas` library to execute a query against the database, then store the results "
                        "in a pandas dataframe:"
                    )
                    st.code(code, language="python")
                with tab3:
                    st.markdown(
                        "Finally, we use the `ag_grid` library to display the dataframe in a table:"
                    )
                    st.code(
                        """AgGrid(
            data=df, gridOptions=gridOptions, customButtons=custom_buttons, options=options
        )""",
                        language="python",
                    )
                    st.markdown(
                        "Note that AgGrid is a wrapper for another library that entails many parameters and arguments for its rendering"
                    )
                    st.text("gridOptions Configuration:")
                    st.json(json.dumps(gridOptions), expanded=False)
                    st.text("CustomButtons Configuration:")
                    st.json(json.dumps(custom_buttons), expanded=False)
                    st.text("Options Configuration:")
                    st.json(json.dumps(gridOptions), expanded=False)
    with tabb:
        with st.container(border=True):
            st.markdown(
                """
            ### Introduction: Setting Up OpenAI API Key and Assistant ID
    
            To use the OpenAI API in your application, you need to obtain an API key and an Assistant ID. This guide will walk you through the process of obtaining these credentials and setting them up as environment variables in your system.
            """
            )
            step1, step2, step3 = st.tabs(
                [
                    "Step 1: Obtain Your OpenAI API Key",
                    "Step 2: Find Your Assistant ID",
                    "Step 3: Set Environment " "Variables",
                ]
            )
            with step1:
                st.markdown(
                    """
                #### Step 1: Obtain Your OpenAI API Key
                1. **Sign Up or Log In**: Visit the [OpenAI website](https://www.openai.com) and sign up for an account or log in if you already have one.
                2. **Access the API Key**: After logging in, navigate to the API section of your account. Here, you will find the option to create a new API key.
                3. **Create a New API Key**: Click on the "Create new secret key" button. Copy the generated API key and store it securely.
                """
                )
            with step2:
                st.markdown(
                    """
                #### Step 2: Find Your Assistant ID
                1. **Create or Access an Assistant**: In the OpenAI dashboard, go to the Assistants section. If you haven't created an assistant yet, create one by following the prompts.
                2. **Locate the Assistant ID**: After creating or selecting your assistant, you will see the Assistant ID in the assistant's settings or details page. Copy the Assistant ID.
                """
                )
            with step3:
                st.markdown(
                    """
                #### Step 3: Set Environment Variables
                To securely store your OpenAI API key and Assistant ID, set them as environment variables in your operating system. This will allow your application to access these credentials without hardcoding them into your scripts.
                """
                )
                with st.expander("For Windows", expanded=False):
                    st.markdown(
                        """
                1. **Open System Properties**: Right-click on `This PC` or `My Computer` on your desktop or in File Explorer. Select `Properties`.
                2. **Advanced System Settings**: Click on `Advanced system settings` on the left.
                3. **Environment Variables**: In the System Properties window, click the `Environment Variables` button.
                4. **New Environment Variable**: Under `User variables` or `System variables`, click `New` and add the following variables:
                   - **Variable name**: `OPENAI_API_KEY`
                   - **Variable value**: Your API key (e.g., `sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)
                   - **Variable name**: `ASSISTANT_ID`
                   - **Variable value**: Your Assistant ID (e.g., `assist-XXXXXXXXXXXXXXXXXXXXXXXX`)
                    """
                    )
                with st.expander("For macOS and Linux"):
                    st.markdown(
                        """
                1. **Open Terminal**: Launch the terminal application.
                2. **Edit Profile**: Open your profile file in a text editor. Depending on your shell, this file could be `~/.bashrc`, `~/.bash_profile`, `~/.zshrc`, or another file.
                3. **Add Environment Variables**: Add the following lines to your profile file:
                   ```sh
                   export OPENAI_API_KEY="sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
                   export ASSISTANT_ID="assist-XXXXXXXXXXXXXXXXXXXXXXXX"
                   ```"""
                    )
        supplier_id = get_supplier_id()
        if st.button("Submit"):
            with st.container(border=True):
                if not supplier_id:
                    st.warning("Please enter a Supplier ID")
                else:
                    st.subheader("What's Happening?")
                    st.divider()
                    thread_id = st.session_state.thread_id
                    if thread_id not in threads or not threads[thread_id]["active"]:
                        if df["supplier_id"].isin([supplier_id]).any():
                            try:
                                supplier_name = get_supplier_name(supplier_id, df)
                                start_supplier_processing(supplier_name, thread_id)
                            except ValueError:
                                st.error("Invalid supplier ID")
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
                        else:
                            st.error("Supplier ID not found.")

            if st.session_state.thread_id:
                thread_id = st.session_state.thread_id
                if thread_id in threads:
                    with st.spinner("Processing..."):
                        while threads[thread_id]["active"]:
                            time.sleep(0.1)
                        output = threads[thread_id]["output"]
                        process_supplier_result(thread_id, output, df)
                        st.write(df)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threads = {}  # Dictionary to manage threads
    db_file = "spend_intake.db"
    conn = connect_to_db(db_file)
    df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
    conn.close()
    main(threads, df)
