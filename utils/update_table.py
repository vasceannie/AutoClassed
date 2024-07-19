import pandas as pd
import sqlite3
import os


def update_supplier_classifications(data_frame: pd.DataFrame) -> None:
    """
    Updates the 'supplier_classifications' table in the SQLite database.

    Args:
        data_frame (pd.DataFrame): The DataFrame containing the data to be inserted.

    Returns:
        None
    """
    relevant_columns = ["supplier_id", "supplier_name"]
    df_suppliers = data_frame[relevant_columns].drop_duplicates()

    db_path = os.path.join(os.path.dirname(__file__), "../data/spend_intake.db")
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        insert_sql = """
        INSERT INTO supplier_classifications (supplier_id, supplier_name)
        VALUES (?, ?)
        ON CONFLICT(supplier_id) DO UPDATE SET supplier_name=excluded.supplier_name;
        """
        data_to_insert = df_suppliers.itertuples(index=False, name=None)
        cursor.executemany(insert_sql, data_to_insert)

    print("Data has been inserted into 'supplier_classifications' table successfully.")
