import os
import sqlite3
from typing import Any, List
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
import concurrent.futures


# Your GetItemData class
class GetItemData(BaseModel):
    """
    A class to represent the data of an item.

    Attributes:
        item_code (str): The unique code of the item.
        validation (bool): Whether the item is valid.
        classification_code (str): The UNSPSC classification code of the item.
        classification_name (str): The UNSPSC classification name of the item.
        website (str): The website related to the item.
        comments (str): Any additional comments about the item.
    """

    item_code: str = Field(description="The unique code of the item")
    validation: bool = Field(description="Whether the item is valid")
    classification_code: str = Field(
        description="The UNSPSC classification code of the item"
    )
    classification_name: str = Field(
        description="The UNSPSC classification name of the item"
    )
    website: str = Field(description="The website related to the item")
    comments: str = Field(description="Any additional comments about the item")


# Initialize the ChatOpenAI client
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY"))

# Initialize the GoogleSerperAPIWrapper tool
google_search = GoogleSerperAPIWrapper(api_key=os.environ.get("SERPER_API_KEY"))

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
            "I'll provide the following details:\n"
            "1. Validation of whether it's a valid item\n"
            "2. The UNSPSC classification code\n"
            "3. The UNSPSC classification name\n"
            "4. The website\n"
            "5. Any additional relevant comments\n\n"
            "I'll format the information as follows:\n"
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

    agent = create_openai_functions_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    result = agent_executor.invoke(
        {
            "item_code": item_code,
            "format_instructions": parser.get_format_instructions(),
        }
    )
    parsed_data = parser.parse(result["output"])
    return parsed_data


# Function to get items without classification_code
def get_items_without_classification(cursor, limit: int = 100) -> List[tuple]:
    """
    Retrieve items from the database who do not have a classification code.

    Args:
        cursor: The database cursor.
        limit (int): The number of items to retrieve. Default is 100.

    Returns:
        List[tuple]: A list of tuples containing item IDs and codes.
    """
    cursor.execute(
        """
        SELECT id, item_code 
        FROM main.item_descriptions 
        WHERE valid IS NULL OR valid = ''
        LIMIT ?
    """,
        (limit,),
    )
    return cursor.fetchall()


# Function to update item information in the database
def update_item_info(conn, item_id, item_data):
    """
    Update item information in the database.

    Args:
        conn: The database connection.
        item_id: The ID of the item to update.
        item_data: An instance of GetItemData containing the updated data.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE main.item_descriptions
        SET valid = ?, classification_code = ?, classification_name = ?, 
            comments = ?, website = ?
        WHERE id = ?
    """,
        (
            item_data.validation,
            item_data.classification_code,
            item_data.classification_name,
            item_data.comments,
            item_data.website,
            item_id,
        ),
    )
    conn.commit()


# Function to process a single item
def process_single_item(id, item_code, conn):
    """
    Process a single item by retrieving and updating its information.

    Args:
        id: The ID of the item.
        item_code: The code of the item.
        conn: The database connection.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        print(f"Processing item: {item_code}")
        item_data = process_item_code(item_code)
        update_item_info(conn, id, item_data)  # Use 'id' for updating
        print(f"Updated information for item code {item_code}:")
        print(item_data)
        return True
    except Exception as e:
        print(f"Error processing item {item_code}: {e}")
        return False


def process_items(batch_size: int = 100):
    """
    Main function to process items in batches.

    Args:
        batch_size (int): The number of items to process in one batch. Default is 100.
    """
    conn = sqlite3.connect("spend_intake2.db", check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Retrieve items without classification codes
        items = get_items_without_classification(cursor, batch_size)

        # Use a thread pool to process items concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [
                executor.submit(process_single_item, id, item_code, conn)
                for id, item_code in items
            ]

            # Count the number of successfully processed items
            successful = sum(
                future.result() for future in concurrent.futures.as_completed(futures)
            )

        print(f"Successfully processed {successful} out of {len(items)} items")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        conn.close()


# Example usage
if __name__ == "__main__":
    process_items(200)  # Process 200 items at a time
