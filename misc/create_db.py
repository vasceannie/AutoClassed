import pandas as pd
import sqlite3


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
    data_lines = [
        line.strip().split("\t") for line in lines[1:] if line.strip() != ""
    ]

    # Create a DataFrame from the processed data
    cleaned_data = pd.DataFrame(data_lines, columns=header)

    # Remove any leading/trailing whitespace characters from the headers
    cleaned_data.columns = cleaned_data.columns.str.strip()

    # Optionally, remove any rows with entirely empty values
    cleaned_data.dropna(how="all", inplace=True)

    return cleaned_data


# Step 1: Read the CSV file into a DataFrame
df = clean_messy_csv('Spend_Intake_010124_063024.csv')

# Step 2: Create a new SQLite database (or connect to an existing one)
db_file_path = "spend_intake.db"
conn = sqlite3.connect(db_file_path)
cursor = conn.cursor()

# Step 3: Convert DataFrame to SQL table
table_name = "spend_data_raw"
df.to_sql(table_name, conn, if_exists="replace", index=False)

# Step 4: Commit and close the connection
conn.commit()
conn.close()

print(
    f"CSV data has been successfully imported into the database '{db_file_path}' in the table '{table_name}'."
)
