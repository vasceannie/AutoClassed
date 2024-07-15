import pandas as pd
import os


def clean_messy_csv(file_path):
    # Read the file as a text file to manually process the lines
    with open(file_path, "r") as file:
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


def clean_and_save_to_csv(file_path):
    cleaned_data = clean_messy_csv(file_path)
    new_file_path = os.path.splitext(file_path)[0] + "_cleaned.csv"
    cleaned_data.to_csv(new_file_path, index=False)


# Usage example
file_path = "data/sample.csv"
clean_and_save_to_csv(file_path)

# Display the cleaned DataFrame
# print(cleaned_data.head())

# Print column headers as list separated by line breaks
# print("\n".join(clean_messy_csv("data/sample.csv").columns.tolist()))
