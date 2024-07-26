"""
utils.py
"""

import json
import os
from typing import override

import streamlit as st
from openai import OpenAI
from openai.lib.streaming import AssistantEventHandler
from openai.types.beta.threads.runs import tool_call
from st_aggrid import AgGrid

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

    return AgGrid(
        data=df, gridOptions=grid_options, customButtons=custom_buttons, options=options
    )


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
        """,
        ),
        (
            "Find Your Assistant ID",
            """
        1. **Create or Access an Assistant**: In the OpenAI dashboard, go to the Assistants section. If you haven't created an assistant yet, create one by following the prompts.
        2. **Locate the Assistant ID**: After creating or selecting your assistant, you will see the Assistant ID in the assistant's settings or details page. Copy the Assistant ID.
        """,
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
        """,
        ),
    ]

    st.markdown(
        """
    To use the OpenAI API, you will need to obtain an API key and an Assistant ID.

    It's important to be mindful of the type of information you share. For example, if you are sharing your API key, make sure that you do not share it with anyone who is not authorized to use it.
    """
    )

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
            content=f"Please investigate: {supplier_name}. Please respond with JSON"
        )

    def stream_response(self, thread_id):
        event_handler = EventHandler()

        # Stream the run
        with self.client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            event_handler=event_handler,
        ) as stream:
            stream.until_done()

        return event_handler.responses


class EventHandler(AssistantEventHandler):
    def __init__(self):
        super().__init__()
        self.responses = []
        self.container = st.container()

    def update_container(self):
        with self.container:
            st.empty()  # Clear previous content
            for response in self.responses:
                with st.expander(f"Response {len(self.responses)}", expanded=True):
                    st.json(response)

    @override
    def on_event(self, event):
        # Retrieve events that are denoted with 'requires_action'
        # since these will have our tool_calls
        # print(f"Event received: {event.event}")
        if event.event == "thread.run.requires_action":
            # print(f"Event data: {event.data}")
            run_id = event.data.id  # Retrieve the run ID from the event data
            # print(f"Run ID: {run_id}")
            self.handle_requires_action(event.data, run_id)

    def handle_requires_action(self, data, run_id):
        tool_outputs = []
        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "get_vendor_classification":
                try:
                    arguments_str = str(tool.function.arguments)
                    tool_output = st.json(json.loads(arguments_str))
                except json.JSONDecodeError as e:
                    print(f"JSONDecodeError: {e}")
                    continue

                tool_output["tool_call_id"] = tool.id
                # filtered_tool_output = {k: v for k, v in tool_output.items() if k in ["tool_call_id", "output"]}
                # if "output" not in filtered_tool_output:
                #     filtered_tool_output["output"] = ""  # or some default value
                # print(f"Filtered tool output: {filtered_tool_output}")
                # # tool_outputs.append(filtered_tool_output)

        # print(f"Tool outputs: {tool_outputs}")
        self.submit_tool_outputs(tool_outputs, run_id)

    def submit_tool_outputs(self, tool_outputs, run_id):
        print(f"Tool outputs: {tool_outputs}")
        print(f"Run ID: {run_id}")
        print(f"Current run thread ID: {self.current_run.thread_id}")
        print(f"Current run ID: {self.current_run.id}")
        # Use the submit_tool_outputs_stream helper
        with client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=self.current_run.thread_id,
                run_id=self.current_run.id,
                tool_outputs=tool_outputs,
                event_handler=EventHandler(),
        ) as stream:
            print(f"Stream started")
            stream.until_done()
            print(f"Stream ended")

    def on_text_created(self, text):
        try:
            json_response = json.loads(text)
            self.responses.append(json_response)
        except json.JSONDecodeError:
            self.responses.append({"text": text})
        self.update_container()

    def on_text_delta(self, delta, snapshot):
        if self.responses:
            if isinstance(self.responses[-1], dict) and "text" in self.responses[-1]:
                self.responses[-1]["text"] += delta.value
            else:
                self.responses.append({"text": delta.value})
        else:
            self.responses.append({"text": delta.value})
        self.update_container()

    def on_tool_call_created(self, tool_call):
        self.update_container()

    def on_tool_call_done(self, tool_call):
        # response = {"tool_call_completed": tool_call.type}
        # if tool_call.type == "function" and tool_call.function:
        #     response["arguments"] = json.loads(tool_call.function.arguments)
        #     response["output"] = json.loads(tool_call.function.output)
        # self.responses.append(response)
        self.update_container()

    def on_run_completed(self, run):
        self.update_container()

    def on_end(self):
        self.update_container()
        return self.responses
