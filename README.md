# Creating an Assistant with GPT and Custom Functions

## Introduction

Welcome to this Jupyter Notebook! In this project, we will guide you through the process of creating an intelligent
assistant using the GPT architecture. Leveraging the power of GPT, our assistant will be capable of understanding and
generating human-like text, making it a versatile tool for various applications.

### Objectives

1. **Understand GPT Architecture:** Gain insights into the working principles of GPT (Generative Pre-trained
   Transformer) and how it processes natural language.
2. **Setup and Initialization:** Learn how to set up the necessary environment and initialize the GPT model.
3. **Creating Custom Functions:** Develop custom functions to extend the assistant's capabilities, making it more
   interactive and functional.
4. **Integration and Testing:** Integrate the functions with the GPT model and test the assistant to ensure it performs
   as expected.

### What You Will Learn

- **Natural Language Processing (NLP):** Basic concepts and the significance of embeddings in understanding text.
- **Model Initialization:** How to load and initialize a pre-trained GPT model.
- **Function Creation:** Techniques to write custom functions that enhance the assistant's functionality.
- **Practical Applications:** Real-world examples and use cases where such an assistant can be beneficial.

### Prerequisites

- **Basic Python Knowledge:** Familiarity with Python programming is essential.
- **Understanding of NLP:** A basic understanding of Natural Language Processing will be helpful.
- **Jupyter Notebook:** Basic knowledge of navigating and executing code in Jupyter Notebook.

### Tools and Libraries

- **OpenAI's GPT:** We will use OpenAI's GPT model as the core of our assistant.
- **Python Libraries:** Essential libraries such as `numpy`, `pandas`, and `requests` for various functionalities.

By the end of this notebook, you will have a functional assistant powered by GPT, enhanced with custom functions
tailored to specific needs. Let's dive in and start building our intelligent assistant!

---
# Supplier Information Gathering and Update System

## Overview

This system is designed to gather and update information about supplier companies in a database. Its main purpose is to process a list of suppliers that don't have classification information and use AI and web search tools to find and add that missing data.

## Input

- A list of supplier names from a SQLite database
- Access to a SQLite database file named "spend_intake2.db"
- API keys for OpenAI and Google Serper stored in environment variables

## Output

Updated supplier information in the database, including:
- Validity of the supplier
- Classification code and name
- Website
- Additional comments

## Main Steps

1. Set up tools for AI processing and web searching using the OpenAI API and Google Serper API
2. Define a template for AI queries about supplier information
3. Create a function to process each company name using AI and search tools
4. Retrieve a list of suppliers from the database that need classification information
5. Process each supplier in parallel using multiple threads
6. Search for information, format results, and update the database for each supplier

## Key Components

### process_suppliers Function
- Gets a batch of suppliers from the database
- Uses a thread pool to process multiple suppliers concurrently

### process_single_supplier Function
- Calls process_company_name to get information
- Calls update_supplier_info to save data to the database

### process_company_name Function
- Transforms a company name string into a structured GetSupplierData object

## Error Handling and Reporting

- Ensures that failure in processing one supplier doesn't stop the entire batch
- Tracks and reports the number of successfully processed suppliers

## Summary

This system automates the process of enriching a supplier database with additional information, leveraging AI and web search capabilities to fill in missing details about each supplier.search capabilities to fill in missing details about each supplier.