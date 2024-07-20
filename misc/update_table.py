# import sqlite3
#
#
# def update_supplier_classifications_table():
#     """
#     Flush the supplier_classifications table and repopulate it with the supplier id and name
#     from the spend_data_raw table. The id that appear in the supplier_classifications table should be distinct.
#     """
#
#     try:
#         # Connect to the SQLite database
#         db_file_path = "../spend_intake.db"
#         conn = sqlite3.connect(db_file_path)
#         cursor = conn.cursor()
#
#         # Flush the table
#         cursor.execute("DELETE FROM supplier_classifications")
#
#         # Populate the table with distinct supplier id and name
#         insert_query = """
#             INSERT INTO supplier_classifications (supplier_id, supplier_name)
#             SELECT DISTINCT supplier_id, supplier_name
#             FROM spend_data_raw
#         """
#         cursor.execute(insert_query)
#
#         # Commit the changes and close the connection
#         conn.commit()
#         conn.close()
#
#     except sqlite3.Error as e:
#         print(f"An error occurred: {e}")
#         conn.rollback()
#
#
# update_supplier_classifications_table()
