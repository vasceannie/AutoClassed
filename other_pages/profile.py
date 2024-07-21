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
from openai.lib.streaming import AssistantEventHandler
from openai.types.beta.threads.runs import ToolCallDelta, ToolCall
from st_aggrid import AgGrid
from streamlit_extras.function_explorer import function_explorer
from typing_extensions import override
from streamlit_ace import st_ace

GRID_OPTIONS = {
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

CUSTOM_BUTTONS = [
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

OPTIONS = {
    "displayIndentGuides": False,
    "highlightIndentGuides": True,
    "wrap": "free",
    "foldStyle": "markbegin",
    "enableLiveAutocompletion": True,
}


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    @override
    def on_tool_call_delta(self, delta: ToolCallDelta, snapshot: ToolCall):
        if delta.type == "get_vendor_classification":
            if delta.get_vendor_classification is not None:
                if delta.get_vendor_classification.inputs:
                    print(delta.get_vendor_classification, end="", flush=True)
                if delta.get_vendor_classification.outputs:
                    print(f"\n\noutput >", flush=True)
                    try:
                        for output in delta.get_vendor_classification.outputs:
                            if output.type == "logs":
                                print(f"\n{output.logs}", flush=True)
                    except TypeError as e:
                        print(f"Error: {e}")
            else:
                print("Error: delta.get_vendor_classification is None")

    def submit_tool_outputs(self, tool_outputs, run_id):
        # Use the submit_tool_outputs_stream helper
        with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=self.current_run.thread_id,
            run_id=self.current_run.id,
            tool_outputs=tool_outputs,
            event_handler=EventHandler(),
        ) as stream:
            for text in stream.text_deltas:
                print(text, end="", flush=True)
            print()


def connect_to_db(db_file_path: str) -> sqlite3.Connection:
    try:
        if not os.path.exists(db_file_path):
            raise FileNotFoundError(f"Database file not found: {db_file_path}")
        if len(db_file_path) > 255:
            raise ValueError("Database file path is too long")
        return sqlite3.connect(db_file_path)
    except sqlite3.Error as e:
        st.error(f"SQLite error: {e}")
        raise
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        raise


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(ASSISTANT_ID)


def create_thread():
    return client.beta.threads.create()


def initialize_thread_id(supplier_name):
    thread = create_thread()
    st.session_state.thread_id = thread.id
    message = client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=f"Please provide validity, classification, and comments for the supplier: {supplier_name}. Respond "
        f"with json please.",
    )

    return message


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


def main(df):
    st.title("Tutorial: Optimizing Data for GPT")
    tab_data_prep, tab_query_openai = st.tabs(["Data Preparation", "Query OpenAI"])

    with tab_data_prep:
        st.header("Creating a condensed view of our working data:")
        AgGrid(
            data=df,
            gridOptions=GRID_OPTIONS,
            customButtons=CUSTOM_BUTTONS,
            options=OPTIONS,
        )

        with st.expander("View Explanation"):
            tab_import_db, tab_extract_df, tab_display_table = st.tabs(
                ["Import Database", "Extract into Dataframe", "Display Table"]
            )

            with tab_import_db:
                st.markdown(
                    "We begin by using `import sqlite3` and `import os` to define a function that will "
                    "establish a connection with our database and return a cursor object. This will be used to execute queries against the database:"
                )
                st.code(inspect.getsource(connect_to_db), language="python")

            with tab_extract_df:
                st.markdown(
                    "Now we use the `pandas` library to execute a query against the database, then store the results "
                    "in a pandas dataframe:"
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
                st.markdown(
                    "Finally, we use the `ag_grid` library to display the dataframe in a table:"
                )
                st.code(
                    """
                    AgGrid(
                        data=df, 
                        gridOptions=GRID_OPTIONS, 
                        customButtons=CUSTOM_BUTTONS, 
                        options=OPTIONS
                    )""",
                    language="python",
                )
                st.markdown(
                    "Note that AgGrid is a wrapper for another library that entails many parameters and arguments for its rendering"
                )
                st.text("GRID_OPTIONS Configuration:")
                st.json(json.dumps(GRID_OPTIONS), expanded=False)
                st.text("CUSTOM_BUTTONS Configuration:")
                st.json(json.dumps(CUSTOM_BUTTONS), expanded=False)
                st.text("OPTIONS Configuration:")
                st.json(json.dumps(OPTIONS), expanded=False)

    with tab_query_openai:
        with st.container():
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
                    "Step 3: Set Environment Variables",
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
                with st.expander("For Windows"):
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
                           ```
                        """
                    )
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Input / Request")
                supplier_id = get_supplier_id()
                if st.button("Submit"):
                    if not supplier_id:
                        st.warning("Please enter a Supplier ID")
                    else:
                        st.subheader("My Request Data")
                        st.divider()
                        if df["supplier_id"].isin([supplier_id]).any():
                            try:
                                supplier_name = get_supplier_name(supplier_id, df)
                                message = initialize_thread_id(supplier_name)
                                st.write("Supplier Name:", supplier_name)
                                st.write("Thread ID:", st.session_state.thread_id)
                                # start_supplier_processing(supplier_name, thread_id)
                            except ValueError:
                                st.error("Invalid supplier ID")
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
                        else:
                            st.error("Supplier ID not found.")

            with col2:
                with client.beta.threads.runs.stream(
                    thread_id=st.session_state.thread_id,
                    assistant_id=ASSISTANT_ID,
                    event_handler=EventHandler(),
                ) as stream:
                    stream.until_done()
    st_ace()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threads = {}
    db_file = "spend_intake.db"
    conn = connect_to_db(db_file)
    df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
    conn.close()
    main(df)
