import os
import sqlite3
from typing import Any, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.tools import Tool, StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field

from langchain_openai import ChatOpenAI

from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain.agents import AgentExecutor, create_openai_functions_agent
import concurrent.futures
from dotenv import load_dotenv
import logging

# Your GetItemData class
class GetItemData(BaseModel):
    """
    A class to represent the data of an item.

    Attributes:
        item_code (str): The unique code of the item.
        validation (bool): Whether the item is valid.
        classification_code (str | None): The UNSPSC classification code of the item.
        classification_name (str | None): The UNSPSC classification name of the item.
        website (str | None): The website related to the item.
        comments (str | None): Any additional comments about the item.
    """

    item_code: str = Field(description="The unique code of the item")
    validation: bool = Field(description="Whether the item is valid")
    classification_code: str | None = Field(
        description="The UNSPSC classification code of the item", default=None
    )
    classification_name: str | None = Field(
        description="The UNSPSC classification name of the item", default=None
    )
    website: str | None = Field(description="The website related to the item", default=None)
    comments: str | None = Field(description="Any additional comments about the item", default=None)


# Load environment variables from .env file
load_dotenv()

# Initialize the ChatOpenAI client
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

# Initialize the GoogleSerperAPIWrapper tool with additional parameters
google_search = GoogleSerperAPIWrapper(
    api_key=os.getenv("SERPER_API_KEY"),
    gl="us",  # Set the country code
    hl="en",  # Set the language
    type="search",  # Specify the search type
)

# Create the parser
parser = PydanticOutputParser(pydantic_object=GetItemData)

# Define the prompt template
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an AI assistant tasked with gathering information about items.",
        ),
        ("human", "I need information on an item with the code: {item_code}"),
        (
            "system",
            "Certainly! I'll use the available tools to search for information about the item with code {item_code}. "
            "Please provide only factual information that you can verify. If you cannot find specific information, "
            "leave the field empty or set it to None. Do not generate or guess any information. "
            "Provide the following details:\n"
            "1. Validation of whether it's a valid item (true only if you can confirm it exists)\n"
            "2. The UNSPSC classification code (if available)\n"
            "3. The UNSPSC classification name (if available)\n"
            "4. The website (if a reliable source is found)\n"
            "5. Any additional relevant comments (factual information only)\n\n"
            "Format the information as follows:\n"
            "{format_instructions}",
        ),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)


# Define the function to process the item code
def process_item_code(item_code: str) -> GetItemData:
    """
    Process the item code and return the item data.

    Args:
        item_code (str): The code of the item.

    Returns:
        GetItemData: The item data.
    """

    tools = [
        StructuredTool.from_function(
            name="investigate_item",
            func=google_search.run,
            description="Use Google search to find information about the item code.",
        )
    ]

    # Update the system message in the prompt
    updated_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant tasked with gathering information about items."),
        ("human", "I need information on an item with the code: {item_code}"),
        ("system", "Certainly! I'll use the available tools to search for information about the item with code {item_code}. "
                   "Please provide only factual information that you can verify. If you cannot find specific information, "
                   "leave the field empty or set it to None. Do not generate or guess any information. "
                   "Provide the following details:\n"
                   "1. Validation of whether it's a valid item (true only if you can confirm it exists)\n"
                   "2. The UNSPSC classification code (if available)\n"
                   "3. The UNSPSC classification name (if available)\n"
                   "4. The website (if a reliable source is found)\n"
                   "5. Any additional relevant comments (factual information only)\n\n"
                   "Format the information as follows:\n"
                   "{format_instructions}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_functions_agent(llm, tools, updated_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    result = agent_executor.invoke(
        {
            "item_code": item_code,
            "format_instructions": parser.get_format_instructions(),
        }
    )
    parsed_data = parser.parse(result["output"])
    logging.info(f"Processed item {item_code}: {parsed_data}")
    return parsed_data


def get_items_to_process(cursor, batch_size):
    """
    Retrieve items that need processing from the database.

    Args:
        cursor: The database cursor.
        batch_size (int): The number of items to retrieve.

    Returns:
        list: A list of tuples containing (id, item_code) for items to process.
    """
    query = """
    SELECT id, item_code
    FROM main.AP_Items_For_Classification
    WHERE valid IS NULL
    LIMIT ?
    """
    cursor.execute(query, (batch_size,))
    return cursor.fetchall()

def update_item_info(conn, item_id, item_data):
    """
    Update item information in the database.

    Args:
        conn: The database connection.
        item_id: The ID of the item to update (as a string).
        item_data: An instance of GetItemData containing the updated data.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE main.AP_Items_For_Classification
            SET valid = ?, classification_code = ?, classification_name = ?, 
                comments = ?, website = ?
            WHERE id = ?
            """,
            (
                item_data.validation,
                item_data.classification_code or None,
                item_data.classification_name or None,
                item_data.comments or None,
                item_data.website or None,
                item_id,  # Now passing item_id directly as a string
            ),
        )
        affected_rows = cursor.rowcount
        conn.commit()
        logging.info(f"Updated item {item_id}. Affected rows: {affected_rows}")
    except Exception as e:
        logging.error(f"Error updating item {item_id}: {str(e)}")
        conn.rollback()


def get_classified_count(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM main.AP_Items_For_Classification 
        WHERE valid IS NOT NULL AND valid != ''
        """
    )
    return cursor.fetchone()[0]


def process_single_item(id, item_code):
    """
    Process a single item by retrieving and updating its information.

    Args:
        id: The ID of the item.
        item_code: The code of the item.

    Returns:
        tuple: (bool, GetItemData) - Success status and item data
    """
    try:
        print(f"Processing item: {item_code}")

        # First attempt
        try:
            item_data = process_item_code(item_code)
        except Exception as e:
            print(f"Error on first attempt for {item_code}: {str(e)}")

            # Second attempt with modified query
            modified_item_code = item_code.split('(')[0].strip()
            print(f"Retrying with modified item code: {modified_item_code}")
            item_data = process_item_code(modified_item_code)

        return True, item_data
    except Exception as e:
        print(f"Error processing item {item_code}: {str(e)}")
        return False, None

def process_items(batch_size: int = 5, max_items: int = 5):
    conn = sqlite3.connect("spend_intake2.db", check_same_thread=False)
    cursor = conn.cursor()

    try:
        total_processed = 0
        while total_processed < max_items:
            # Retrieve items that need processing
            items = get_items_to_process(cursor, min(batch_size, max_items - total_processed))

            if not items:
                logging.info("No more items to process. Exiting.")
                break

            # Use a thread pool to process items concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = [
                    executor.submit(process_single_item, str(id), item_code)
                    for id, item_code in items
                ]

                processed = 0
                for future, (id, _) in zip(concurrent.futures.as_completed(futures), items):
                    success, item_data = future.result()
                    if success and item_data:
                        update_item_info(conn, float(id), item_data)
                    processed += 1
                    logging.info(f"Processed item {id}: {'Success' if success else 'Failed'}")

            total_processed += processed
            logging.info(f"Processed {processed} out of {len(items)} items")
            logging.info(f"Total processed: {total_processed}")

        logging.info(f"Reached maximum number of items to process ({max_items}). Exiting.")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        conn.close()

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Starting processing")
    process_items(batch_size=1000, max_items=1000)  # Process up to 5 items total
    logging.info("Processing complete")