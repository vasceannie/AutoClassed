import os
import csv
import json
import argparse
import concurrent.futures
import re  # Ensure this is imported
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class EmailData(BaseModel):
    email: str
    type: str


class GetItemData(BaseModel):
    company: str
    emails: List[EmailData]
    phone_numbers: List[str]
    address: Optional[str] = None


def extract_data_from_json(data: Dict[Any, Any]) -> Dict[str, Any]:
    result = {
        "company": "",
        "emails": [],
        "phone_numbers": [],
        "address": None
    }

    def extract_recursive(obj, current_key=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                extract_recursive(value, key)
        elif isinstance(obj, list):
            for item in obj:
                extract_recursive(item, current_key)
        else:
            if current_key.lower() in ["company", "company name"]:
                result["company"] = str(obj)
            elif "email" in current_key.lower():
                result["emails"].append({"email": str(obj), "type": "unknown"})
            elif "phone" in current_key.lower():
                result["phone_numbers"].append(str(obj))
            elif "address" in current_key.lower():
                result["address"] = str(obj)

    extract_recursive(data)
    return result


def clean_and_parse_output(output: str) -> dict:
    # Try to extract JSON from the output
    json_match = re.search(r'\{.*\}', output, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            data = json.loads(json_str)
            # Ensure all required fields are present
            data.setdefault('company', 'Unknown')
            data.setdefault('emails', [])
            data.setdefault('phone_numbers', [])
            return data
        except json.JSONDecodeError:
            pass

    # If JSON extraction fails, create a minimal valid structure
    return {
        'company': 'Unknown',
        'emails': [],
        'phone_numbers': []
    }


from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate


def process_item_code(item_code: str, prompt: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18",
                     api_key=os.environ.get("OPENAI_API_KEY"))  # do not ever modify this line
    google_search = GoogleSerperAPIWrapper(api_key=os.environ.get("SERPER_API_KEY"))
    parser = PydanticOutputParser(pydantic_object=GetItemData)

    tools = [
        StructuredTool.from_function(
            name="investigate_item",
            func=google_search.run,
            description="Use Google search to find information about a point of contact for a company in question.",
        )
    ]

    system_message = SystemMessagePromptTemplate.from_template(
        "You are an AI assistant tasked with gathering information about our supplier contacts. "
        "I need the contact information for an individual that is most likely to register with Coupa's sourcing platform. "
        "Generally, this would be someone in sales or accounts receivable. This could be either a name, phone number, or email address, "
        "preferably as a JSON object. Please flag if the information you find is for an individual or a company inbox."
    )

    human_message = HumanMessagePromptTemplate.from_template(
        "Find contact information for: {item_code}\n{format_instructions}"
    )

    chat_prompt = ChatPromptTemplate.from_messages([
        system_message,
        human_message,
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_openai_functions_agent(llm, tools, chat_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        result = agent_executor.invoke({
            "item_code": item_code,
            "format_instructions": parser.get_format_instructions()
        })
        return result.get("output", "")
    except Exception as e:
        print(f"Error processing item_code {item_code}: {e}")
        return ""  # Return an empty string or handle the error appropriately


def get_items_from_csv(csv_file: str) -> list[tuple]:
    items = []
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for row in reader:
            items.append((row[0], row[1]))
    return items


def process_single_item(id, vendor, prompt, output_csv):
    try:
        print(f"Processing vendor: {vendor}")
        item_data = process_item_code(vendor, prompt)
        print(f"Information for vendor {vendor}:")
        print(item_data)

        # Parse the JSON data
        parsed_data = clean_and_parse_output(item_data)

        # Extract relevant information
        company = parsed_data.get('company', vendor)
        emails = parsed_data.get('emails', [])
        phone_numbers = parsed_data.get('phone_numbers', [])

        # Determine if it's an individual or company contact
        contact_type = 'individual' if any(e.get('type') == 'individual' for e in emails) else 'company'

        # Get the first email and phone number (if available)
        email = emails[0].get('email', 'N/A') if emails else 'N/A'
        phone = phone_numbers[0] if phone_numbers else 'N/A'

        # Write to CSV
        output_csv.writerow([
            id,
            company,
            contact_type,
            "N/A",  # contact name
            phone,
            email,
            "Google Search"  # citation
        ])

        return True
    except Exception as e:
        print(f"Error processing vendor {vendor}: {e}")
        return False


def process_items(id: str, varlookup: str, csv_file: str, prompt: str):
    items = get_items_from_csv(csv_file)

    output_file = 'output_results.csv'
    with open(output_file, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['id', 'vendor', 'real', 'contact name', 'contact phone', 'contact email', 'citation'])

        if id.lower() == 'all':
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = [
                    executor.submit(process_single_item, item_id, vendor, prompt, csv_writer)
                    for item_id, vendor in items
                ]
                successful = sum(future.result() for future in concurrent.futures.as_completed(futures))
            print(f"Successfully processed {successful} out of {len(items)} items")
        else:
            for item_id, vendor in items:
                if item_id == id:
                    process_single_item(item_id, vendor, prompt, csv_writer)
                    break
            else:
                print(f"No item found with ID: {id}")

    print(f"Results have been written to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process items based on input arguments.")
    parser.add_argument("id", help="The ID to process (or 'all' for all items)")
    parser.add_argument("varlookup", help="The variable to look up")
    parser.add_argument("csv", help="Path to the input CSV file")
    parser.add_argument("--prompt", help="The custom prompt to use for processing", default="")

    args = parser.parse_args()

    process_items(args.id, args.varlookup, args.csv, args.prompt)
