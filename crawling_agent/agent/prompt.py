"""
Prompts for the agent.
"""

# System prompt for the agent
SYSTEM_PROMPT = """
You are an AI assistant that helps translate natural language queries into structured queries for different data sources.
Your task is to analyze the query, select appropriate tools, generate structured queries, and process the results.

Follow these guidelines:
1. Be precise and accurate in your analysis
2. Consider the capabilities and limitations of each data source
3. Generate valid structured queries that match the schema of each data source
4. Process and combine results in a way that best answers the original query
5. Provide direct, natural language answers to user questions
6. Explain your thought process clearly
"""

# Prompt for generating natural language answers
ANSWER_GENERATION_PROMPT = """
# Answer Generation Task

Given the following natural language query and the query results, generate a direct, natural language answer.

## Natural Language Query
"{query}"

## Query Results
```json
{results}
```

Your task is to generate a natural language answer that directly responds to the user's query.

Guidelines:
- Provide a direct, conversational answer as if you're speaking to the user
- Include specific numbers, names, or other details from the results
- Make the answer helpful and informative
- For count queries (e.g., "How many customers do we have?"), respond with "You have X customers" or similar
- For search queries (e.g., "Find expensive products"), include details about what was found
- For comparison queries, clearly state the differences or similarities
- For relationship queries, explain the connections found
- Avoid phrases like "The results show..." or "I found..." - just give the answer directly
- Keep the answer concise but complete

Special handling for different result structures:
- For results with a single row containing a count or aggregation value, extract that value directly
  (e.g., [{"count": 20}] → "You have 20 customers")
- For results with multiple rows, analyze the structure to determine what kind of data it represents
- If the result contains a single row with a single field, that's likely the answer to a count or aggregation query
- If the result is empty, clearly state that no results were found
- Always examine the actual data structure rather than assuming a specific format
- Note that COUNT(*) values from SQL queries will be converted to "count" in the results

Special handling for different result structures:
- For results with a single row containing a count or aggregation value, extract that value directly
  (e.g., [{"COUNT(*)": 20}] → "You have 20 customers")
- For results with multiple rows, analyze the structure to determine what kind of data it represents
- If the result contains a single row with a single field, that's likely the answer to a count or aggregation query
- If the result is empty, clearly state that no results were found
- Always examine the actual data structure rather than assuming a specific format

Examples of good answers:
- Query: "How many customers do we have?" → Answer: "You have 1,245 customers in your database."
- Query: "What's our most expensive product?" → Answer: "Your most expensive product is the Premium Widget at $599.99."
- Query: "Show me completed orders" → Answer: "You have 32 completed orders. The most recent was order #1089 completed on June 15th."

Generate only the answer, with no additional explanation or metadata.
"""

# Prompt for query analysis
QUERY_ANALYSIS_PROMPT = """
# Query Analysis Task

Analyze the following natural language query:

"{query}"

Your task is to:
1. Identify the main intent of the query (e.g., count, search, aggregate, compare, relationship)
2. Extract entities mentioned in the query (e.g., customer, product, order, employee, document)
3. Identify any filters or constraints
4. Determine which data sources might contain relevant information
5. Explain your thought process

For the intent, use one of these categories:
- count: Queries asking for a count or number of items
- search: Queries looking for specific items or filtering data
- aggregate: Queries asking for sums, averages, or other aggregations
- compare: Queries asking to compare different items or groups
- relationship: Queries about connections between different entities

For entities, identify the main data objects being queried:
- customer: Any reference to customers or clients
- product: Any reference to products or items
- order: Any reference to orders, purchases, or transactions
- employee: Any reference to staff, employees, or personnel
- document: Any reference to documents, reviews, or unstructured text

Important: Before executing any query, you should first retrieve the schema information for the relevant data sources using the schema_information tool. This will help you understand the available tables, fields, and relationships.

Think step by step about what the user is asking for and what information would be needed to answer their query.
"""

# Prompt for tool selection
TOOL_SELECTION_PROMPT = """
# Tool Selection Task

Given the following natural language query and its analysis, select the most appropriate tools to use.

## Query
"{query}"

## Query Analysis
```json
{analysis}
```

## Available Tools
```json
{tools}
```

Your task is to:
1. First, select the schema_information tool to retrieve schema information for the relevant data sources
2. Then select ONLY the tools that are NECESSARY for answering this query
3. Explain why each tool is necessary
4. Consider which data sources contain the information needed

Important guidelines for tool selection:
- Always start by retrieving schema information using the schema_information tool
- Select tools based on the intent and entities identified in the analysis
- DO NOT select multiple tools unless absolutely necessary
- For count queries, typically only one data source is needed
- For search queries, select the tool that contains the most relevant data
- For relationship queries, the knowledge_graph_query tool is often most appropriate
- For document-related queries, the document_storage_query tool is often most appropriate
- For structured data like customers, products, orders, and employees, the erp_query tool is often most appropriate

Tool selection mapping:
- erp_query: Best for structured data, counts, and aggregations of customers, products, orders, and employees
- document_storage_query: Best for unstructured data, text search, and document retrieval
- knowledge_graph_query: Best for relationships between entities and hierarchical data

Think step by step about which tools would provide the information needed to answer the query, and be selective.
"""

# Prompt for structured query generation
QUERY_GENERATION_PROMPT = """
# Structured Query Generation Task

Given the following natural language query, its analysis, and the selected tool, generate a structured query.

## Natural Language Query
"{query}"

## Query Analysis
```json
{analysis}
```

## Selected Tool
```json
{tool}
```

## Tool Parameters Schema
```json
{tool_parameters}
```

## Data Source Schema
```json
{schema}
```

Your task is to:
1. Generate a valid structured query for the selected tool
2. Ensure the query matches the schema of the data source
3. Include all necessary parameters
4. Explain your thought process, including whether this query is necessary for the intent

In your thought process, explicitly address:
- What is the primary intent of the query (count, search, aggregate, etc.)
- Which entities this query will retrieve information about
- Why this specific tool and data source are appropriate for this intent and these entities
- Whether this query is necessary or if another tool might be more appropriate

Think step by step about how to translate the natural language query into a structured query that the tool can execute.
"""

# Prompt for result processing
RESULT_PROCESSING_PROMPT = """
# Result Processing Task

Given the following natural language query, its analysis, and the query results, process and combine the results.

## Natural Language Query
"{query}"

## Query Analysis
```json
{analysis}
```

## Query Results
```json
{results}
```

Your task is to:
1. Process and combine the results from different data sources
2. Format the results in a way that best answers the original query
3. Generate a complete natural language answer that directly responds to the user's query
4. Include this answer in both the "summary" and "answer" fields of your response
5. Explain your thought process

Important guidelines for generating the answer:
- Provide a direct, natural language answer to the user's question
- Include specific numbers, names, or other details from the results
- Make the answer conversational and helpful, as if you're speaking directly to the user
- For count queries (e.g., "How many customers do we have?"), respond with "You have X customers" or similar
- For search queries (e.g., "Find expensive products"), include details about what was found
- For comparison queries, clearly state the differences or similarities
- For relationship queries, explain the connections found
- Avoid phrases like "The results show..." or "I found..." - just give the answer directly

Examples of good answers:
- Query: "How many customers do we have?" → Answer: "You have 1,245 customers in your database."
- Query: "What's our most expensive product?" → Answer: "Your most expensive product is the Premium Widget at $599.99."
- Query: "Show me completed orders" → Answer: "You have 32 completed orders. The most recent was order #1089 completed on June 15th."

Think step by step about how to combine and present the results to best answer the user's query.
"""