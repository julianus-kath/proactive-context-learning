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
5. Explain your thought process clearly
"""

# Prompt for query analysis
QUERY_ANALYSIS_PROMPT = """
# Query Analysis Task

Analyze the following natural language query:

"{query}"

Your task is to:
1. Identify the main intent of the query
2. Extract entities mentioned in the query
3. Identify any filters or constraints
4. Determine which data sources might contain relevant information
5. Explain your thought process

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
1. Select the tools that are most appropriate for answering this query
2. Explain why each tool is necessary
3. Consider which data sources contain the information needed

Think step by step about which tools would provide the information needed to answer the query.
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
4. Explain your thought process

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
3. Provide a summary of the results
4. Explain your thought process

Think step by step about how to combine and present the results to best answer the user's query.
"""