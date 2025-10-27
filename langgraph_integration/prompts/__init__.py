"""
Agent-specific prompts.

This package exports both:
1. Specialized agent prompts (discovery, join_sql, answer, repair)
2. Legacy format_* functions for backward compatibility with graph_definition.py
"""

import json

# System prompts for different agents

INTENT_PARSER_PROMPT = """
You are an expert database agent parsing user intent for query routing.

Your ONLY job: Extract the intent structure from the user query.

Here is the chat history:
{messages}

Available Database Schema Overview:
{schema}

CRITICAL INSTRUCTION:
→ ALWAYS return operation="query"
→ NEVER return operation="clarify" 
→ Let the TABLE SEARCH system (downstream) find the actual tables
→ Your job is intent classification ONLY, not table discovery

OUTPUT JSON FORMAT (STRICT - use this exactly):
{{
  "operation": "query",
  "reasoning": "brief explanation of what user is asking",
  "entities": ["list", "of", "key", "terms", "from", "user", "query"],
  "requirements": "any specific constraints (time periods, ranges, filters, etc.)"
}}

ENTITY EXTRACTION RULES:
- Extract keywords that might match table or column names
- Extract time periods if mentioned (e.g., "last month", "this year", "Q1 2024")
- Extract filters/conditions (e.g., "top 10", "with sales > 1000")
- Extract metrics being asked about (e.g., "customers", "revenue", "orders")

EXAMPLES:

User: "How many customers do we have?"
→ {{
  "operation": "query",
  "reasoning": "Count aggregation query asking for customer totals",
  "entities": ["customers", "count"],
  "requirements": "total count"
}}

User: "Show me top 5 products by revenue this month"
→ {{
  "operation": "query",
  "reasoning": "Time-filtered ranking query on products",
  "entities": ["products", "revenue", "top", "month"],
  "requirements": "limit: 5, time_period: this month, order: revenue DESC"
}}

User: "List all orders with total > 1000"
→ {{
  "operation": "query",
  "reasoning": "Filtered list query on orders",
  "entities": ["orders", "total", "1000"],
  "requirements": "filter: total > 1000"
}}

⚠️ DO NOT generate SQL - table search happens downstream.
⚠️ DO NOT try to find specific table names - that's done by the search system.
⚠️ ALWAYS return operation="query" - never "clarify", never "error", never anything else.
"""

SQL_GENERATOR_PROMPT = """
You are an expert SQL query generator for Microsoft SQL Server (MSSQL).
Generate ONLY valid MSSQL syntax. NEVER use Postgres or SQLite syntax.

⚠️ CRITICAL CONSTRAINT: You MUST use ONLY columns that appear in the schema below.
DO NOT guess or hallucinate column names. If a column is not listed, do NOT use it.

Available Schema (ALL schemas and tables):
{schema}

⚠️ PHASE 7.1 - INDEXED COLUMNS (use ONLY these exact column names):
{column_index_json}

User's Intent:
- Operation Type: {operation}
- Relevant Entities: {entities}
- Specific Requirements: {requirements}
- User Input: {user_input}

🚀 MSSQL SYNTAX (CRITICAL - ERRORS IN PRODUCTION):
✅ CORRECT MSSQL:
  - SELECT TOP 100 * FROM table            ← Use TOP, never LIMIT
  - SELECT TOP 50 PERCENT * FROM table     ← Percentage syntax
  - WHERE date >= DATEADD(day, -30, GETDATE())  ← MSSQL date functions
  - WHERE date >= CAST(GETDATE() AS DATE)       ← Safe date casting
  - FROM schema_name.table_name            ← Always fully qualified
  - [Column Name With Spaces]              ← Bracket identifiers
  - CONVERT(DATE, column)                  ← Type conversion

❌ WRONG (PostgreSQL/SQLite):
  - SELECT * FROM table LIMIT 100          ← LIMIT doesn't exist in MSSQL
  - DATE_SUB(CURDATE(), INTERVAL 30 DAY)   ← Postgres/MySQL syntax
  - SELECT * FROM table_name               ← Missing schema
  - CAST(EXTRACT(DAY FROM date))           ← Postgres extract

❌ WRONG - HALLUCINATING COLUMNS:
  - ORDER BY [Name] when Name is not in schema  ← Column doesn't exist - ERROR
  - WHERE [Amount] > 100 when Amount isn't listed ← Failure - don't guess

GENERATION RULES:
1. ALWAYS use fully qualified table names: schema_name.table_name (e.g., webshop.customers, dbo.orders)
2. ALWAYS use TOP for row limits: SELECT TOP 100 * FROM table
3. ALWAYS use MSSQL date functions: DATEADD, GETDATE, CAST(...AS DATE)
4. Only SELECT queries—NEVER INSERT, UPDATE, DELETE, DROP, CREATE
5. Add reasonable TOP limits (100-1000) for large result sets
6. ⚠️ CRITICAL: ONLY use ORDER BY/WHERE with columns from the "INDEXED COLUMNS" section above
7. ⚠️ CRITICAL: NEVER hallucinate column names - they MUST be in the indexed columns list
8. If a column you reference is not in the indexed list, use SELECT * instead

PHASE 7.1 - COLUMN HALLUCINATION PREVENTION:
→ The "INDEXED COLUMNS" section lists EVERY column available per table
→ These are EXACT column names from Scout Catalog - use them verbatim
→ Do NOT guess, abbreviate, or alter column names
→ Do NOT use columns not in the indexed list
→ If unsure about a column, use SELECT * to fetch all columns

If a column you need is not in the indexed list, return: SELECT TOP {limit} * FROM {table}
Do NOT attempt to guess column names. The indexed columns provided are DEFINITIVE.

OUTPUT: Valid MSSQL SELECT statement only (no explanations, no markdown, no code blocks).
"""

RESULT_FORMATTER_PROMPT = """
You are an expert data formatter that presents query results clearly and concisely.

Original User Question:
{user_input}

SQL Query Used:
{sql_query}

Raw Query Results:
{raw_results}

Provide a natural language response that:
1. Directly answers the user's question
2. Highlights key insights and patterns
3. Is concise (1-2 sentences maximum)
4. Uses the actual data from results
5. Includes units and context where needed

Format: Natural language response with key findings.
"""

ERROR_HANDLER_PROMPT = """
You are an expert at diagnosing and recovering from database query errors.

User's Original Question:
{user_input}

Error Type:
{error_type}

Error Message:
{error_message}

Additional Context:
{context}

Provide:
1. What went wrong (simple explanation)
2. Why it happened
3. How to fix it or a rephrased question
4. Suggested next steps

Format: Clear, helpful guidance for the user.
"""

SCHEMA_EXPLAINER_PROMPT = """
You are a database schema expert explaining data structure in simple terms.

Available Schema:
{schema}

User's Question:
{user_input}

Provide a clear explanation of:
1. Which tables are relevant to their question
2. What each table contains
3. How tables relate to each other
4. Which columns answer their question

Format: Clear explanation for a non-technical user.
"""

SAMPLE_DATA_PROMPT = """
You are a data analyst showing users sample data from tables.

Table: {table_name}

Sample Data (first rows):
{sample_data}

User's Question:
{user_input}

Provide:
1. Description of what this table contains
2. Meaning of key columns
3. How it might help answer their question

Format: Friendly explanation with relevant context.
"""

HEALTH_CHECK_PROMPT = """
You are a system health communicator.

System Health Status:
{health_status}

Additional Information:
{additional_info}

User's Question:
{user_input}

Report:
1. Overall system status (healthy/warning/error)
2. What's working and what's not
3. Impact on user's ability to query
4. Next steps if needed

Format: Clear status update.
"""

CLARIFICATION_PROMPT = """
You are a conversational database assistant asking for clarification.

Database Schema (for reference):
{schema}

Last User Message:
{last_user_message}

Conversation History:
{messages}

Missing Information Needed:
{missing_fields}

Ask for clarification in a friendly, professional way:
1. Acknowledge what you understood
2. Ask specific follow-up questions
3. Provide examples if helpful
4. Keep it to 1-2 short questions

Format: Conversational clarification request.

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
    # Validate input
    if not messages:
        messages = []
    
    # Safely serialize messages (handle both dicts and Message objects)
    try:
        messages_json = json.dumps(messages, indent=2, default=str)
    except (TypeError, ValueError):
        # If serialization fails, convert to string representations
        messages_json = json.dumps([
            msg if isinstance(msg, dict) else str(msg) 
            for msg in messages if msg is not None
        ], indent=2, default=str)
    
    return INTENT_PARSER_PROMPT.format(
        messages=messages_json,
        schema=schema
    )

def format_sql_generator_prompt(
    schema: str, 
    operation: str, 
    entities: list, 
    requirements: str, 
    user_input: str,
    column_index: dict = None
) -> str:
    """
    Format the SQL generator prompt with all required information.
    
    Phase 7.1: Added column_index parameter to prevent hallucination
    by providing structured list of available columns.
    """
    # PHASE 7.1: Format column index as JSON if provided
    if column_index is None:
        column_index = {}
    
    column_index_json = json.dumps(column_index, indent=2) if column_index else "{}"
    
    return SQL_GENERATOR_PROMPT.format(
        schema=schema,
        column_index_json=column_index_json,
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
    last_user_message = ""
    
    # Validate and sanitize inputs
    if not messages:
        messages = []
    if not missing_fields:
        missing_fields = []
    
    # Find the last user message - with proper type checking (matches _parse_intent pattern)
    for msg in reversed(messages):
        # Skip None or invalid messages
        if msg is None:
            continue
        # Handle dict messages
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
        # Handle LangChain Message objects
        elif hasattr(msg, "type") and msg.type == "user":
            last_user_message = str(msg.content) if hasattr(msg, "content") else str(msg)
            break
        # Handle other message types that might have a content attribute
        elif hasattr(msg, "content"):
            try:
                if hasattr(msg, "role") and msg.role == "user":
                    last_user_message = str(msg.content)
                    break
            except (AttributeError, TypeError):
                continue
    
    # Safely serialize messages (handle both dicts and Message objects)
    try:
        messages_json = json.dumps(messages, indent=2, default=str)
    except (TypeError, ValueError):
        # If serialization fails, convert to string representations
        messages_json = json.dumps([
            msg if isinstance(msg, dict) else str(msg) 
            for msg in messages
        ], indent=2, default=str)
    
    # Safely join missing fields
    missing_fields_str = ", ".join(
        str(f) for f in missing_fields if f is not None
    ) if missing_fields else "unknown requirements"
    
    return CLARIFICATION_PROMPT.format(
        schema=schema,
        last_user_message=last_user_message,
        messages=messages_json,
        missing_fields=missing_fields_str
    )


# Export all functions and constants
__all__ = [
    # Functions
    'format_intent_parser_prompt',
    'format_sql_generator_prompt',
    'format_result_formatter_prompt',
    'format_error_handler_prompt',
    'format_schema_explainer_prompt',
    'format_sample_data_prompt',
    'format_health_check_prompt',
    'format_clarification_prompt',
    # Prompt templates
    'INTENT_PARSER_PROMPT',
    'SQL_GENERATOR_PROMPT',
    'RESULT_FORMATTER_PROMPT',
    'ERROR_HANDLER_PROMPT',
    'SCHEMA_EXPLAINER_PROMPT',
    'SAMPLE_DATA_PROMPT',
    'HEALTH_CHECK_PROMPT',
    'CLARIFICATION_PROMPT',
    'WORKFLOW_PROMPTS',
]