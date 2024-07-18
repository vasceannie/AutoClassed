import streamlit as st
import streamlit_shadcn_ui as sui
from pygwalker.api.streamlit import StreamlitRenderer
import numpy as np
import pandas as pd

st.title("RiseNow Intelligent Data Inspector")


@st.cache_data
def clean_messy_csv(file_path):
    """
    Reads a CSV file with tab-separated values, cleans it, and returns a pandas DataFrame.

    Parameters:
    file_path (str): The path to the CSV file.

    Returns:
    pd.DataFrame: Cleaned data as a pandas DataFrame.
    """
    # Read the file as a text file to manually process the lines
    with open(
        file_path, "r", encoding="utf-8"
    ) as file:  # Added encoding to handle potential UnicodeDecodeErrors
        lines = file.readlines()

    # Split the header and data lines
    header = lines[0].strip().split("\t")
    data_lines = [line.strip().split("\t") for line in lines[1:]]

    # Create a DataFrame from the processed data
    cleaned_data = pd.DataFrame(data_lines, columns=header)

    # Remove any leading/trailing whitespace characters from the headers
    cleaned_data.columns = cleaned_data.columns.str.strip()

    # Optionally, remove any rows with entirely empty values
    cleaned_data.dropna(how="all", inplace=True)

    return cleaned_data


# Now, let's use the function and display the first few rows of the cleaned DataFrame
clean_data = clean_messy_csv("data/Spend_Intake_010124_063024.csv")
pyg_app = StreamlitRenderer(clean_data)
pyg_app.explorer()
