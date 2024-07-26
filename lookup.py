import os
from typing import Any
from langchain.prompts import PromptTemplate
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.utils.function_calling import convert_pydantic_to_openai_function
from langchain_openai import ChatOpenAI
from typing_extensions import Self


# Define the Pydantic class for structured JSON output
class GetSupplierData(BaseModel):
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

    @classmethod
    def model_validate_json(cls, json_data: Any, strict: bool = True, context: Any = None) -> 'GetSupplierData':
        return cls.parse_raw(json_data)


# Initialize the ChatOpenAI client
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY"))

# Initialize the GoogleSerperAPIWrapper tool
google_search = GoogleSerperAPIWrapper(api_key=os.environ.get("SERPER_API_KEY"))

# Define the prompt template
query_template = """
Given the company name "{company_name}", perform a web search to gather the following information:
1. Validation of whether the supplier is a valid supplier
2. The UNSPSC classification code of the supplier
3. The UNSPSC classification name of the supplier
4. The website of the supplier
5. Any additional comments about the supplier

Provide the information in the following JSON format:
{{
    "supplier_name": "{company_name}",
    "validation": true/false,
    "classification_code": "UNSPSC Code",
    "classification_name": "UNSPSC Name",
    "website": "Website URL",
    "comments": "Additional comments"
}}
"""


# Define the function to process the company name
def process_company_name(company_name: str):
    # Create the prompt
    prompt = PromptTemplate(template=query_template, input_variables=["company_name"])
    llm.with_structured_output(GetSupplierData)
    tools = [
        {
            "name": "GoogleSearch",
            "description": "Critical resource for investigating a company",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The name of the company to search for"
                    }
                },
                "required": ["company_name"]
            }
        }
    ]

    # Initialize the LLMChain
    llm.bind_tools(tools)
    llm.bind(functions=[convert_to_openai_function(GetSupplierData)])
    chain = prompt | llm
    # Run the chain with the provided company name
    response = chain.invoke({"company_name": company_name})
    json_response = response.content if hasattr(response, "content") else response
    # Parse the response into the Query class
    query_data = GetSupplierData.model_validate_json(json_response)

    return query_data


# Example usage
if __name__ == "__main__":
    org_name = "RHEEM SALES COMPANY INC"
    result = process_company_name(org_name)
    print(result.model_dump_json(indent=4))
