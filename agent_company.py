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


# Your GetSupplierData class
class GetSupplierData(BaseModel):
    """
    A class to represent the data of a supplier.

    Attributes:
        supplier_name (str): The name of the supplier organization.
        validation (bool): Whether the supplier is a valid supplier.
        classification_code (str): The UNSPSC classification code of the supplier.
        classification_name (str): The UNSPSC classification name of the supplier.
        website (str): The website of the supplier.
        comments (str): Any additional comments about the supplier.
    """

    supplier_name: str = Field(description="The name of the supplier organization")
    validation: bool = Field(description="Whether the supplier is a valid supplier")
    classification_code: str = Field(
        description="The UNSPSC classification code of the supplier"
    )
    classification_name: str = Field(
        description="The UNSPSC classification name of the supplier"
    )
    website: str = Field(description="The website of the supplier")
    comments: str = Field(description="Any additional comments about the supplier")


# Initialize the ChatOpenAI client
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY"))

# Initialize the GoogleSerperAPIWrapper tool
google_search = GoogleSerperAPIWrapper(api_key=os.environ.get("SERPER_API_KEY"))

# Create the parser
parser = PydanticOutputParser(pydantic_object=GetSupplierData)

# Define the prompt template
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an AI assistant tasked with gathering information about supplier companies.",
        ),
        ("human", "I need information about the company: {company_name}"),
        (
            "system",
            "Certainly! I'll use the available tools to search for information about {company_name}. "
            "I'll provide the following details:\n"
            "1. Validation of whether it's a valid supplier\n"
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


# Define the function to process the company name
def process_company_name(company_name: str) -> GetSupplierData:
    """
    Process the company name and return the supplier data.

    Args:
        company_name (str): The name of the company.

    Returns:
        GetSupplierData: The supplier data.
    """

    tools = [
        StructuredTool.from_function(
            name="investigate_supplier_company",
            func=google_search.run,
            description="Use Google search to find information about the company.",
        )
    ]

    agent = create_openai_functions_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    result = agent_executor.invoke(
        {
            "company_name": company_name,
            "format_instructions": parser.get_format_instructions(),
        }
    )
    parsed_data = parser.parse(result["output"])
    return parsed_data


# Function to get suppliers without classification_code
def get_suppliers_without_classification(cursor, limit: int = 100) -> List[tuple]:
    """
    Retrieve suppliers from the database who do not have a classification code.

    Args:
        cursor: The database cursor.
        limit (int): The number of suppliers to retrieve. Default is 100.

    Returns:
        List[tuple]: A list of tuples containing supplier IDs and names.
    """
    cursor.execute(
        """
        SELECT id, supplier_name 
        FROM main.ARS_Supplier_Classification_List 
        WHERE classification_code IS NULL OR classification_code = ''
        LIMIT ?
    """,
        (limit,),
    )
    return cursor.fetchall()


# Function to update supplier information in the database
def update_supplier_info(conn, supplier_id, supplier_data):
    """
    Update supplier information in the database.

    Args:
        conn: The database connection.
        supplier_id: The ID of the supplier to update.
        supplier_data: An instance of GetSupplierData containing the updated data.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE main.ARS_Supplier_Classification_List
        SET valid = ?, classification_code = ?, classification_name = ?, 
            comments = ?, website = ?
        WHERE id = ?
    """,
        (
            supplier_data.validation,
            supplier_data.classification_code,
            supplier_data.classification_name,
            supplier_data.comments,
            supplier_data.website,
            supplier_id,
        ),
    )
    conn.commit()


# Function to process a single supplier
def process_single_supplier(supplier_id, supplier_name, conn):
    """
    Process a single supplier by retrieving and updating its information.

    Args:
        supplier_id: The ID of the supplier.
        supplier_name: The name of the supplier.
        conn: The database connection.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        print(f"Processing supplier: {supplier_name}")
        supplier_data = process_company_name(supplier_name)
        update_supplier_info(conn, supplier_id, supplier_data)
        print(f"Updated information for supplier {supplier_name}:")
        print(supplier_data)
        return True
    except Exception as e:
        print(f"Error processing supplier {supplier_name}: {e}")
        return False


# Main function to process suppliers
def process_suppliers(batch_size: int = 100):
    """
    Main function to process suppliers in batches.

    Args:
        batch_size (int): The number of suppliers to process in one batch. Default is 100.
    """
    conn = sqlite3.connect("spend_intake2.db", check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Retrieve suppliers without classification codes
        suppliers = get_suppliers_without_classification(cursor, batch_size)

        # Use a thread pool to process suppliers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [
                executor.submit(
                    process_single_supplier, supplier_id, supplier_name, conn
                )
                for supplier_id, supplier_name in suppliers
            ]

            # Count the number of successfully processed suppliers
            successful = sum(
                future.result() for future in concurrent.futures.as_completed(futures)
            )

        print(f"Successfully processed {successful} out of {len(suppliers)} suppliers")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        conn.close()


# Example usage
if __name__ == "__main__":
    process_suppliers(200)  # Process 200 suppliers at a time
