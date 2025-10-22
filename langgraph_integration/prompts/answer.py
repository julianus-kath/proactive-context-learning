"""
Answer Agent Prompts - for formatting results and explanations.
"""

RESULT_FORMATTER_PROMPT = """You are formatting database query results as a short, user-friendly answer.

**CRITICAL RULE: Keep it to 1-2 sentences ONLY. No lengthy explanations.**

**User Query:**
{user_input}

**Query Executed:**
{sql_query}

**Results:**
{results_json}

**Formatting Rules:**
1. Direct answer ONLY (no prefix like "Answer:" or "A:")
2. Use natural numbers (not scientific notation)
3. If multiple rows, summarize briefly (e.g., "Top 5 customers are...")
4. If 0 rows: "No records found matching your criteria."
5. Include unit if relevant (e.g., "2,450 units", "$15,320", "12 customers")
6. Avoid technical jargon

**Examples:**
Q: "How many customers?"
✅ "10 customers are in the database."
❌ "The query returned a result set containing customer information..."

Q: "Show top 3 products by sales"
✅ "Top 3 are: Widget A ($5k), Widget B ($4.2k), Gadget X ($3.1k)."
❌ "The products ranked by sales volume in descending order are..."

**Generate answer (1-2 sentences max):**
"""

SCHEMA_EXPLAINER_PROMPT = """You are explaining database schema to a user in simple terms.

**CRITICAL RULE: 1-2 sentences. List table names only. NO technical details.**

**Schema:**
{schema_snippet}

**User's Question:**
{user_input}

**Examples:**
Q: "What tables are in the database?"
✅ "The main tables are customers, orders, and products."
❌ "The database contains a denormalized star schema with the following dimension tables..."

Q: "Is there an orders table?"
✅ "Yes, there's an orders table with customer and product references."
❌ "The orders table contains order-level granularity with foreign key relationships..."

**Generate explanation (1-2 sentences max):**
"""

CLARIFICATION_PROMPT = """You are asking ONE focused clarification question to help resolve ambiguity.

**Context:**
User: {user_input}
Available schema: {schema_snippet}
Conversation history: {messages}

**Your job:** Ask EXACTLY ONE question that uses actual table/column names from the schema.

**Clarification Rules:**
1. Ask one question only (no multiple questions)
2. Use real column/table names (reference schema_snippet)
3. Suggest options if relevant (e.g., "Do you mean column A, B, or C?")
4. Keep it short and natural
5. Avoid yes/no questions (ask "which?" instead)

**Example:**
Schema has: customers (name, email), orders (order_date, total)
User: "Show me the top orders"
Question: "Do you want the top orders by total amount or by date?"

**Generate ONE clarification question:**
"""

ERROR_RESPONSE_PROMPT = """You are explaining a query error to the user in helpful, simple terms.

**Error Details:**
- Type: {error_type}
- Message: {error_message}
- Context: {context}

**User's Original Query:**
{user_input}

**Response Rules:**
1. State the problem in 1 sentence (non-technical)
2. Suggest ONE simple next step
3. Keep it SHORT and actionable

**Examples:**
Error: "Table not found"
❌ "Schema mismatch detected in metadata catalog."
✅ "That table doesn't exist. Available tables are: customers, orders, products."

Error: "Query timeout"
❌ "The query exceeded the 30-second execution time limit."
✅ "The query took too long. Try filtering by a specific date range."

**Generate user-friendly error response (2 sentences max):**
"""

HEALTH_CHECK_RESPONSE = """You are reporting system health to the user.

**Health Status:**
{health_status}

**Output Format:**
- 1 sentence on overall status (working/not working)
- 1 sentence on details (# tables, # views, DB connected Y/N)

**Examples:**
✅ Good: "System is working. Database has 150 tables and 45 views."
❌ Bad: "The MCP server is running with a catalog age of 45 seconds and 98% cache hit rate..."

**Generate health response (2 sentences max):**
"""