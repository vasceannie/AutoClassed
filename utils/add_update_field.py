import sqlite3
import os


def add_timestamp_column():
    # Use an absolute path
    global conn
    db_path = os.path.abspath("../spend_intake.db")

    # Check if the database file exists
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Add a new column 'timestamp' to the 'supplier_classifications' table
        cursor.execute("ALTER TABLE supplier_classifications ADD COLUMN timestamp TEXT")

        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Operational error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()


# Run the function to add the timestamp column
add_timestamp_column()
