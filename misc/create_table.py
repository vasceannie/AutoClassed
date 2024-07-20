# import sqlite3
#
# # Connect to the SQLite database
# db_file_path = 'spend_intake.db'
# conn = sqlite3.connect(db_file_path)
# cursor = conn.cursor()
#
# # SQL command to create the new table
# create_table_sql = """
# CREATE TABLE IF NOT EXISTS supplier_classifications (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     supplier_id INTEGER,
#     valid BOOLEAN,
#     classification_code TEXT,
#     classification_name TEXT,
#     comments TEXT,
#     FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
# );
# """
#
# # Execute the SQL command
# cursor.execute(create_table_sql)
#
# # Commit the changes and close the connection
# conn.commit()
# conn.close()
#
# print("Table 'supplier_classifications' has been created successfully.")
