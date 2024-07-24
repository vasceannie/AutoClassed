"""
utils.py
"""
import logging
import os
import re
import sqlite3
import time
from typing import Tuple, override
from openai.lib.streaming import AssistantEventHandler
import streamlit as st
from openai import OpenAI
from st_aggrid import AgGrid
from openai.types.beta.threads.runs import ToolCall
import pandas as pd

# Get secrets
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Config
LAST_UPDATE_DATE = "2024-04-08"

# Initialise the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def render_custom_css() -> None:
    """
    Applies custom CSS
    """
    st.html(
        """
            <style>
                #MainMenu {visibility: hidden}
                #header {visibility: hidden}
                #footer {visibility: hidden}
                .block-container {
                    padding-top: 3rem;
                    padding-bottom: 2rem;
                    padding-left: 3rem;
                    padding-right: 3rem;
                    }
            </style>
            """
    )


def initialise_session_state():
    """
    Initialise session state variables
    """
    if "file" not in st.session_state:
        st.session_state.file = None

    if "assistant_text" not in st.session_state:
        st.session_state.assistant_text = [""]

    for session_state_var in ["file_uploaded", "read_terms"]:
        if session_state_var not in st.session_state:
            st.session_state[session_state_var] = False

    for session_state_var in ["code_input", "code_output"]:
        if session_state_var not in st.session_state:
            st.session_state[session_state_var] = []


def summon_grid(df):
    column_defs = [
        {"field": "id", "headerName": "ID", "width": 75},
        {"field": "supplier_id", "headerName": "Supplier ID", "width": 100},
        {"field": "supplier_name", "headerName": "Supplier Name", "width": 300},
        {"field": "valid", "headerName": "Is Valid", "width": 100},
        {"field": "classification_code", "headerName": "Supplier Class Code", "width": 250},
        {"field": "classification_name", "headerName": "Supplier Classification Description", "width": 250},
        {"field": "comments", "headerName": "Comments", "width": 300},
    ]

    grid_options = {
        "columnDefs": column_defs,
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

    return AgGrid(data=df, gridOptions=grid_options, customButtons=custom_buttons, options=options)


def openai_setup_instructions(st):
    """
    Display instructions on how to set up OpenAI API and Assistant ID.

    Args:
        st (Streamlit): Streamlit object for displaying instructions.
    """
    steps = [
        (
            "Obtain Your OpenAI API Key",
            """
        1. **Sign Up or Log In**: Visit the [OpenAI website](https://www.openai.com) and sign up for an account or log in if you already have one.
        2. **Access the API Key**: After logging in, navigate to the API section of your account. Here, you will find the option to create a new API key.
        3. **Create a New API Key**: Click on the "Create new secret key" button. Copy the generated API key.
        """
        ),
        (
            "Find Your Assistant ID",
            """
        1. **Create or Access an Assistant**: In the OpenAI dashboard, go to the Assistants section. If you haven't created an assistant yet, create one by following the prompts.
        2. **Locate the Assistant ID**: After creating or selecting your assistant, you will see the Assistant ID in the assistant's settings or details page. Copy the Assistant ID.
        """
        ),
        (
            "Set Environment Variables",
            """
        1. **Open System Properties**: Right-click on `This PC` or `My Computer` on your desktop or in File Explorer. Select `Properties`.
        2. **Advanced System Settings**: Click on `Advanced system settings` on the left.
        3. **Environment Variables**: In the System Properties window, click the `Environment Variables` button.
        4. **New Environment Variable**: Under `User variables` or `System variables`, click `New` for each variable:
           - **Variable name**: `OPENAI_API_KEY`
           - **Variable value**: Your API key (e.g., `sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)
           - **Variable name**: `ASSISTANT_ID`
           - **Variable value**: Your Assistant ID (e.g., `assist-XXXXXXXXXXXXXXXXXXXXXXXX`)
        """
        ),
    ]

    st.markdown("""
    To use the OpenAI API, you will need to obtain an API key and an Assistant ID.

    It's important to be mindful of the type of information you share. For example, if you are sharing your API key, make sure that you do not share it with anyone who is not authorized to use it.
    """)

    for step_name, step_description in steps:
        with st.expander(step_name):
            st.markdown(step_description)


class OpenAIManager:
    def __init__(self, client, assistant_id):
        self.client = client
        self.assistant_id = assistant_id

    def process_supplier(self, supplier_name):
        active_thread = self.create_thread()
        self.create_message(supplier_name, thread_id=active_thread.id)
        return self.stream_response(active_thread.id)

    def create_thread(self):
        thread = self.client.beta.threads.create()
        st.session_state.thread_id = thread.id
        return thread

    def create_message(self, supplier_name, thread_id):
        return self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=f"Please provide validity, classification, and comments for the supplier: {supplier_name}. Respond with json please."
        )

    def stream_response(self, thread_id):
        with self.client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=self.assistant_id,
                event_handler=EventHandler()
        ) as stream:
            stream.until_done()
            return stream.on_end()


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        response = {
            "event": "text_created",
            "data": {
                "text": text
            }
        }
        st.session_state.assistant_text = (
                st.session_state.get("assistant_text", "") + json.dumps(response)
        )
        st.write(st.session_state.assistant_text, unsafe_allow_html=True)

    def on_text_delta(self, delta, snapshot):
        response = {
            "event": "text_delta",
            "data": {
                "delta": delta.value,
                "snapshot": snapshot
            }
        }
        st.session_state.assistant_text = (
                st.session_state.get("assistant_text", "") + json.dumps(response)
        )
        st.empty()

    def on_tool_call_created(self, tool_call):
        response = {
            "event": "tool_call_created",
            "data": {
                "type": tool_call.type
            }
        }
        st.write(json.dumps(response), unsafe_allow_html=True)

    def on_tool_call_done(self, tool_call: ToolCall):
        try:
            response = {
                "event": "tool_call_done",
                "data": {
                    "type": tool_call.type
                }
            }

            if tool_call.type == "function":
                response["data"]["function"] = {
                    "name": tool_call.function.name if tool_call.function and tool_call.function.name else None,
                    "arguments": tool_call.function.arguments if tool_call.function and tool_call.function.arguments else None,
                    "output": tool_call.function.output if tool_call.function and tool_call.function.output else None
                }

            if tool_call.type == "get_vendor_classification":
                if hasattr(tool_call, "vendor_classification") and tool_call.vendor_classification:
                    response["data"]["vendor_classification"] = {
                        "classification_code": tool_call.vendor_classification.classification_code,
                        "classification_name": tool_call.vendor_classification.classification_name
                    }

            st.write(json.dumps(response), unsafe_allow_html=True)

            # Existing functionality
            self.check_last_message(tool_call)
            st.success("Response generated and displayed successfully.")
            new_data = self.prepare_new_data(tool_call)
            self.insert_data_into_db(new_data)

        except Exception as e:
            error_response = {
                "event": "error",
                "data": {
                    "message": str(e)
                }
            }
            st.error(json.dumps(error_response))
            logging.error(json.dumps(error_response))

            stream.until_done()
            return stream.on_end()


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        st.session_state.assistant_text = (
                st.session_state.get("assistant_text", "") + text
        )
        st.write(st.session_state.assistant_text, unsafe_allow_html=True)

    def on_text_delta(self, delta, snapshot):
        st.session_state.assistant_text = (
                st.session_state.get("assistant_text", "") + delta.value
        )
        st.empty()

    def on_tool_call_created(self, tool_call):
        st.write(f"assistant > {tool_call.type}", unsafe_allow_html=True)

    def on_tool_call_done(self, tool_call: ToolCall):
        try:
            if tool_call.type == "function":
                self.display_tool_call_info(tool_call)

            self.check_last_message(tool_call)

            st.success("Response generated and displayed successfully.")
            new_data = self.prepare_new_data(tool_call)
            self.insert_data_into_db(new_data)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            logging.error(f"An error occurred: {str(e)}")

    def display_tool_call_info(self, tool_call: ToolCall):
        if tool_call.function and tool_call.function.name:
            st.markdown(f"\n{tool_call.function.name}\n")
        if tool_call.function and tool_call.function.arguments:
            st.json(tool_call.function.arguments)
        if tool_call.function and tool_call.function.output:
            st.json(tool_call.function.output)
            if tool_call.type == "get_vendor_classification":
                if hasattr(tool_call, "vendor_classification") and tool_call.vendor_classification:
                    st.write(
                        f"get_vendor_classification: {tool_call.vendor_classification.classification_code} - "
                        f"{tool_call.vendor_classification.classification_name}",
                    )
                else:
                    st.write("get_vendor_classification: None")

    def check_last_message(self, tool_call: ToolCall):
        messages = client.beta.threads.messages.list(st.session_state.thread_id)
        last_message_id = messages.data[-1].id if messages.data else None

        if last_message_id == tool_call.id:
            st.write(
                "This is the last message in the thread.", unsafe_allow_html=True
            )
        else:
            st.write(
                "This is not the last message in the thread.",
                unsafe_allow_html=True,
            )

    def prepare_new_data(self, tool_call: ToolCall):
        return {
            "classification_code": {
                tool_call.get_vendor_classification.classification_code
            },
            "classification_name": {
                tool_call.get_vendor_classification.classification_name
            },
            "validity": {tool_call.get_vendor_classification.validity},
            "comments": {tool_call.get_vendor_classification.comments},
        }

    def submit_tool_outputs(self, tool_outputs, run_id):
        max_retries = 5
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                with client.beta.threads.runs.submit_tool_outputs_stream(
                        thread_id=self.current_run.thread_id,
                        run_id=self.current_run.id,
                        tool_outputs=tool_outputs,
                        event_handler=self,
                ) as stream:
                    for _ in stream.text_deltas:
                        pass
                break  # If successful, break out of the retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    st.error(
                        f"Failed to submit tool outputs after {max_retries} attempts. Error: {str(e)}"
                    )
                    logging.error(
                        f"Failed to submit tool outputs after {max_retries} attempts. Error: {str(e)}"
                    )

    def on_run_completed(self, run):
        st.empty()

    @override
    def on_end(self):
        st.empty()

    def update_supplier_data_in_db(self, supplier_id: str, new_data: dict, df: pd.DataFrame, db_path: str):
        """
        Updates supplier data in both DataFrame and SQLite database.

        Args:
        supplier_id (str): The supplier ID to update.
        new_data (dict): The new data to insert, e.g., {'classification_name': 'New Classification'}.
        df (pd.DataFrame): The pandas DataFrame to update.
        db_path (str): The path to the SQLite database file.
        """
        df_index = df.index[df["supplier_id"] == supplier_id]
        df.loc[df_index, list(new_data.keys())] = list(new_data.values())

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            update_query = (
                    "UPDATE supplier_classifications SET "
                    + ", ".join([f"{k} = ?" for k in new_data.keys()])
                    + " WHERE supplier_id = ?"
            )
            cursor.execute(update_query, list(new_data.values()) + [supplier_id])

    def insert_data_into_db(self, new_data, df):
        db_path = "spend_intake.db"
        supplier_id = st.session_state.supplier_id
        try:
            self.update_supplier_data_in_db(supplier_id, new_data, df, db_path)
        except Exception as e:
            print(f"An error occurred: {e}")
            logging.error(f"An error occurred: {e}")
