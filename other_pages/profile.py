import sqlite3
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid
from openai import OpenAI
import os
import streamlit_shadcn_ui as ui
import time
from typing_extensions import override
from utils import initialise_session_state, render_custom_css, retrieve_messages_from_thread, EventHandler


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
db_file = "spend_intake.db"
conn = connect_to_db(db_file)
df = pd.read_sql_query("SELECT * FROM supplier_classifications", conn)
conn.close()

gridOptions = {
    "columnDefs": [
        {"field": "id", "headerName": "ID", "width": 75},
        {"field": "supplier_id", "headerName": "Supplier ID", "width": 100},
        {"field": "supplier_name", "headerName": "Supplier Name", "width": 300},
        {"field": "valid", "headerName": "Is Valid", "width": 100},
        {"field": "classification_code", "headerName": "Supplier Class Code", "width": 250},
        {"field": "classification_name", "headerName": "Supplier Classification Description",
         "width": 250},
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
# st.dataframe(df)
AgGrid(data=df, gridOptions=gridOptions, customButtons=custom_buttons, options=options)

# Get secrets
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("OPENAI_ASSISTANT_ID")

# Initialise the OpenAI client, and retrieve the assistant
client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(ASSISTANT_ID)

initialise_session_state()


def display_buttons():
    """
    Displays buttons in the sidebar.
    """
    if client:
        ui.button(
            text="Missing API Key",
            key="styled_btn_tailwind",
            className="bg-red-500 text-white",
        )
    else:
        ui.button(
            text="OpenAI API Key Loaded",
            key="styled_btn_tailwind",
            className="bg-orange-500 text-white"
        )


with st.sidebar:
    display_buttons()

if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id
    print(f"Created new thread: \t {st.session_state.thread_id}")


def create_message(supplier_name, thread_id):
    """
    Creates a message with the OpenAI API.
    """
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=f"Please respond in JSON with a confirmation of validity, UNSPSC classification code, and description "
                f"for {supplier_name}.",
    )


with st.form(key='single_supplier_lookup'):
    supplier_id = st.text_input("Supplier ID")
    submitted = st.form_submit_button("Submit")

if submitted:
    with st.spinner('Waiting for response...'):
        create_message(supplier_id, st.session_state.thread_id)

        with client.beta.threads.runs.stream(thread_id=st.session_state.thread_id,
                                             assistant_id=assistant.id,
                                             tool_choice={"type": "code_interpreter"},
                                             event_handler=EventHandler(),
                                             temperature=0) as stream:
            stream.until_done()
            st.toast("Ding! Fries are done.", icon=":fries:")

    with st.spinner("Preparing the files for download..."):
        # Retrieve the messages by the Assistant from the thread
        assistant_messages = retrieve_messages_from_thread(st.session_state.thread_id)


def create_run(thread_id):
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id="asst_uNaXtdhXVuAfgee33jtenfbg")
    return run


def wait_on_run(run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


def single_supplier_query(supplier_id):
    # Get the supplier name
    matching_suppliers = df.loc[df['supplier_id'] == supplier_id, 'supplier_name']

    if matching_suppliers.empty:
        raise ValueError("Supplier not found.")

    supplier_name = matching_suppliers.values[0]

    # Create a thread
    thread = create_thread()

    if thread is None:
        raise ValueError("Failed to create thread.")

    # Create a message
    create_message(supplier_name, thread.id)

    # Create a run
    run = create_run(thread.id)

    # Wait for the run to complete
    run = wait_on_run(run, thread)

    # Get the response
    response = client.beta.threads.messages.list(thread_id=thread.id)
    return response
