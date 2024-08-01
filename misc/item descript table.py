# import pandas as pd
# from sqlalchemy import create_engine
# import re
#
# # Assuming you have already established a database connection
# engine = create_engine('sqlite:///../spend_intake2.db')
# # Read the spend_data_raw table
# spend_data_raw = pd.read_sql_table('spend_data_raw', engine)
#
#
# # Function to normalize item codes
# def normalize_item_code(code):
#     # Remove any non-alphanumeric characters and convert to uppercase
#     return re.sub(r'[^A-Za-z0-9]', '', str(code)).upper()
#
#
# # Normalize item codes
# spend_data_raw['normalized_item_code'] = spend_data_raw['item_code']
#
# # Get unique normalized item codes and their descriptions
# unique_items = spend_data_raw[['normalized_item_code', 'item_description']].drop_duplicates()
#
# # Rename columns to match the item_description table
# unique_items.columns = ['item_code', 'normalized_description']
#
# # Insert the unique items into the item_description table
# unique_items.to_sql('item_descriptions', engine, if_exists='append', index=False)
#
# print(f"Inserted {len(unique_items)} unique items into the item_description table.")