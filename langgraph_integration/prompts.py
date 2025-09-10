"""
Prompts for LangGraph MCP Integration
Phase 2 Blueprint Implementation

This module contains all the prompts used in the LangGraph workflow for
parsing user intent, generating SQL, and formatting results.
"""

# System prompts for different agents

INTENT_PARSER_PROMPT = """
You are an expert database agent that maintains full conversation context and decides whether to ask clarifying questions or execute queries.

Here is the chat history as a JSON array of messages (role: user/assistant, content):
{messages}

Available Database Schema (ALL schemas and tables):
{schema}

Based on the entire conversation and available database schema, decide:
1. If the user's last message requires you to ask a follow-up question (because they omitted required info like specific location, time period, product category, etc.)
2. Otherwise, generate a safe single SELECT SQL statement using the available tables and columns.

CRITICAL SCHEMA AWARENESS:
- The schema shows ALL available schemas (e.g., public, webshop, etc.) and their tables
- ALWAYS use fully qualified table names: schema_name.table_name (e.g., webshop.products, webshop.customer)
- When user asks "what tables", show tables from ALL schemas, not just public
- When user asks about specific data, look across ALL schemas for relevant tables

IMPORTANT: Only reference tables and columns that actually exist in the provided schema. Do not assume any table structure.

Output JSON with fields:
- operation: "clarify" or "query"
- sql: (if operation=query) the SELECT statement with FULLY QUALIFIED table names
- missing_fields: (if operation=clarify) list of specific information needed
- reasoning: brief explanation of your decision

CRITICAL SQL Syntax Rules (when generating SQL):
- ALWAYS use fully qualified table names: schema.table_name
- INTERVAL expressions MUST be quoted: INTERVAL '3 months' NOT INTERVAL 3 months
- String literals use single quotes: 'New York' NOT "New York"
- Date comparisons: created_at > CURRENT_DATE - INTERVAL '1 year'

Examples (adapt to actual schema):
User: "How many customers?" → {{"operation": "query", "sql": "SELECT COUNT(*) FROM webshop.customer", "reasoning": "Count query using fully qualified table name"}}

User: "What tables do we have?" → {{"operation": "query", "sql": "SELECT CONCAT(table_schema, '.', table_name) as full_table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast') ORDER BY table_schema, table_name", "reasoning": "Show all tables from all user schemas with schema qualification"}}

User: "What schemas?" → {{"operation": "query", "sql": "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast') ORDER BY schema_name", "reasoning": "List all available schemas"}}

User: "Orders from May" → {{"operation": "query", "sql": "SELECT COUNT(*) FROM webshop.order WHERE EXTRACT(MONTH FROM order_date) = 5", "reasoning": "Date filter query with schema qualification"}}

Analyze the conversation and respond with JSON:
"""

SQL_GENERATOR_PROMPT = """
You are a SQL expert that generates safe, efficient SQL queries for a PostgreSQL database with multiple schemas.

Database Schema (ALL schemas and tables):
{schema}

User Intent Analysis:
Operation: {operation}
Entities: {entities}
Requirements: {requirements}

Original User Request: {user_input}

Generate a SQL query that:
1. Is safe (SELECT only, no modifications)
2. Follows PostgreSQL syntax EXACTLY
3. Uses FULLY QUALIFIED table names (schema.table_name)
4. Includes appropriate LIMIT clauses (max 1000 rows)
5. Uses proper JOIN syntax when needed
6. Handles potential NULL values appropriately

CRITICAL SCHEMA AWARENESS:
- ALWAYS use fully qualified table names: schema_name.table_name
- Look across ALL schemas for relevant tables (webshop, public, etc.)
- Do not assume tables are in the public schema

If the request cannot be fulfilled with a safe SQL query, explain why and suggest alternatives.

Important constraints:
- Only SELECT statements allowed
- Maximum 1000 rows per query
- Use table and column names exactly as they appear in the schema
- Include appropriate WHERE clauses for filtering
- Use aggregate functions (COUNT, SUM, AVG) for analysis queries

CRITICAL PostgreSQL Syntax Rules:
- ALWAYS use fully qualified table names: schema.table_name
- INTERVAL expressions MUST be quoted: INTERVAL '3 months' NOT INTERVAL 3 months
- Date/time intervals: '1 day', '3 months', '1 year', '2 weeks'
- String literals must use single quotes: 'New York' NOT "New York"
- Column aliases: SELECT COUNT(*) as total_count
- Proper JOIN syntax: INNER JOIN, LEFT JOIN, etc.

Generate the SQL query:
"""

RESULT_FORMATTER_PROMPT = """
CRITICAL INSTRUCTION: You MUST give EXTREMELY SHORT answers. NO long explanations.

User asked: {user_input}
SQL executed: {sql_query}
Results: {raw_results}

RULES - FOLLOW EXACTLY:
1. Maximum 1-2 sentences
2. NO explanations, examples, or background
3. Just answer the question directly
4. If asking for count → just give the number
5. If asking for list → just list items
6. NO technical details or descriptions
7. DO NOT start your response with "A:" or any prefix - just give the direct answer

EXAMPLES:
Q: "How many customers?" → "10 customers"
Q: "What tables?" → "customers table"
Q: "Show schema" → "customers table with 20 columns"

Your answer (keep it SHORT):
"""

ERROR_HANDLER_PROMPT = """
You are an error handler that helps users understand and resolve database query issues.

User Request: {user_input}
Error Type: {error_type}
Error Message: {error_message}
Context: {context}

Provide a BRIEF response that:
1. States what went wrong in 1-2 sentences
2. Suggests a simple fix or alternative
3. Keep it SHORT and helpful

Be concise - don't give long explanations. Just state the problem and solution briefly.
- Timeout: Suggest ways to make the query more efficient
- Connection Error: Provide troubleshooting steps

Generate a helpful error response:
"""

SCHEMA_EXPLAINER_PROMPT = """
CRITICAL: Give EXTREMELY SHORT answers about database schema. NO long explanations.

Schema: {schema}
User asked: {user_input}

RULES:
1. Maximum 1-2 sentences
2. Just list table names as they are in the schema - do not translate them
3. NO detailed explanations or examples
4. NO sample queries or technical details
5. DO NOT start your response with "A:" or any prefix - just give the direct answer

EXAMPLES:
Q: "What tables?" → "customers table"
Q: "Show schema" → "customers table with customer_id, name, email, phone columns"

Your SHORT answer:
"""

# Utility prompts for specific scenarios

SAMPLE_DATA_PROMPT = """
You are presenting sample data from a database table to help users understand the data structure and content.

Table: {table_name}
Sample Data: {sample_data}
User Request: {user_input}

Present the sample data in a way that:
1. Shows the structure and types of data in the table
2. Explains what each column represents
3. Highlights interesting patterns or values
4. Suggests what kinds of queries might be useful
5. Maintains user privacy (don't expose sensitive information)

Format the sample data presentation:
"""

HEALTH_CHECK_PROMPT = """
You are a system status reporter providing information about database and system health.

Health Status: {health_status}
Additional Info: {additional_info}
User Request: {user_input}

Provide a status report that:
1. Clearly states whether the system is working properly
2. Explains any issues or limitations
3. Provides troubleshooting guidance if needed
4. Suggests next steps for the user
5. Maintains confidence in the system when appropriate

Generate a health status response:
"""

CLARIFICATION_PROMPT = """
You are a helpful assistant that asks clarifying questions based on conversation context and available database schema.

Available Database Schema:
{schema}

The user's last request:
{last_user_message}

From the conversation history:
{messages}

Missing information needed: {missing_fields}

Ask exactly one focused question to clarify these items. Be specific and helpful.
Use the actual table and column names from the schema to provide relevant suggestions.

Guidelines:
- Reference the conversation context when relevant
- Ask for the most important missing piece first
- Be conversational and friendly
- Don't repeat information already provided
- Suggest options based on actual schema columns and data
- Only reference tables/columns that exist in the provided schema

Generate a clarifying question:
"""

# Prompt templates for different workflow states

WORKFLOW_PROMPTS = {
    "intent_parser": INTENT_PARSER_PROMPT,
    "sql_generator": SQL_GENERATOR_PROMPT,
    "result_formatter": RESULT_FORMATTER_PROMPT,
    "error_handler": ERROR_HANDLER_PROMPT,
    "schema_explainer": SCHEMA_EXPLAINER_PROMPT,
    "sample_data": SAMPLE_DATA_PROMPT,
    "health_check": HEALTH_CHECK_PROMPT,
    "clarification": CLARIFICATION_PROMPT
}

# Helper functions for prompt formatting

def format_intent_parser_prompt(messages: list, schema: str = "") -> str:
    """Format the intent parser prompt with conversation messages and schema."""
    import json
    return INTENT_PARSER_PROMPT.format(
        messages=json.dumps(messages, indent=2),
        schema=schema
    )

def format_sql_generator_prompt(schema: str, operation: str, entities: list, requirements: str, user_input: str) -> str:
    """Format the SQL generator prompt with all required information."""
    return SQL_GENERATOR_PROMPT.format(
        schema=schema,
        operation=operation,
        entities=entities,
        requirements=requirements,
        user_input=user_input
    )

def format_result_formatter_prompt(user_input: str, sql_query: str, raw_results: str) -> str:
    """Format the result formatter prompt with query results."""
    return RESULT_FORMATTER_PROMPT.format(
        user_input=user_input,
        sql_query=sql_query,
        raw_results=raw_results
    )

def format_error_handler_prompt(user_input: str, error_type: str, error_message: str, context: str = "") -> str:
    """Format the error handler prompt with error information."""
    return ERROR_HANDLER_PROMPT.format(
        user_input=user_input,
        error_type=error_type,
        error_message=error_message,
        context=context
    )

def format_schema_explainer_prompt(schema: str, user_input: str) -> str:
    """Format the schema explainer prompt."""
    return SCHEMA_EXPLAINER_PROMPT.format(
        schema=schema,
        user_input=user_input
    )

def format_sample_data_prompt(table_name: str, sample_data: str, user_input: str) -> str:
    """Format the sample data prompt."""
    return SAMPLE_DATA_PROMPT.format(
        table_name=table_name,
        sample_data=sample_data,
        user_input=user_input
    )

def format_health_check_prompt(health_status: str, additional_info: str, user_input: str) -> str:
    """Format the health check prompt."""
    return HEALTH_CHECK_PROMPT.format(
        health_status=health_status,
        additional_info=additional_info,
        user_input=user_input
    )

def format_clarification_prompt(messages: list, missing_fields: list, schema: str = "") -> str:
    """Format the clarification prompt with conversation context and schema."""
    import json
    last_user_message = ""
    
    # Find the last user message
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    return CLARIFICATION_PROMPT.format(
        schema=schema,
        last_user_message=last_user_message,
        messages=json.dumps(messages, indent=2),
        missing_fields=", ".join(missing_fields)
    )

# Example usage
if __name__ == "__main__":
    # Test prompt formatting
    user_query = "How many customers do we have?"
    
    print("Intent Parser Prompt:")
    print(format_intent_parser_prompt(user_query))
    print("\n" + "="*50 + "\n")
    
    print("SQL Generator Prompt:")
    print(format_sql_generator_prompt(
        schema="customers(id, name, email), products(id, name, price)",
        operation="DATA_QUERY",
        entities=["customers"],
        requirements="count total customers",
        user_input=user_query
    ))