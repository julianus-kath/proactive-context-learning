"""
Advanced chatbot interface for the MCP infrastructure using OpenAI Agents.
"""
# Simple in-memory cache for query results
query_cache = {}
import asyncio
import json
import logging
import os
import sys
import time
from flask import Flask, render_template, request, jsonify
import nest_asyncio
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('chatbot_interface')

from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector

# Apply nest_asyncio to allow nested event loops (needed for Flask + asyncio)
nest_asyncio.apply()

app = Flask(__name__)

# Store the connectors and OpenAI client as global variables
erp_connector = None
doc_connector = None
kg_connector = None
openai_client = None

# Initialize the connectors and OpenAI client
async def initialize_connectors():
    global erp_connector, doc_connector, kg_connector, openai_client
    
    print("Initializing connectors...")
    
    # Create the connectors
    erp_connector = MCPERPConnector()
    doc_connector = MCPDocumentStorageConnector()
    kg_connector = MCPKnowledgeGraphConnector()
    
    # Initialize OpenAI client if API key is available
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        openai_client = OpenAI(api_key=api_key)
        print("OpenAI client initialized.")
    else:
        print("WARNING: OPENAI_API_KEY not found in environment variables. OpenAI features will be disabled.")
    
    print("Connectors initialized.")

# Run the initialization
asyncio.run(initialize_connectors())

@app.route('/')
def index():
    """Render the chat interface."""
    return render_template('chat.html')

@app.route('/api/status')
def status():
    """Check if the servers are running."""
    logger.info("Checking server status")
    
    # Create an event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Try to connect to each server
        erp_status = "Unknown"
        doc_status = "Unknown"
        kg_status = "Unknown"
        
        try:
            logger.info("Checking ERP server")
            async def check_erp():
                try:
                    async with MCPERPConnector() as connector:
                        await connector.list_tools()
                        return "Running"
                except Exception as e:
                    logger.error(f"ERP server error: {str(e)}")
                    return f"Error: {str(e)}"
            
            erp_status = loop.run_until_complete(check_erp())
        except Exception as e:
            erp_status = f"Error: {str(e)}"
        
        try:
            logger.info("Checking Document Storage server")
            async def check_doc():
                try:
                    async with MCPDocumentStorageConnector() as connector:
                        await connector.list_tools()
                        return "Running"
                except Exception as e:
                    logger.error(f"Document Storage server error: {str(e)}")
                    return f"Error: {str(e)}"
            
            doc_status = loop.run_until_complete(check_doc())
        except Exception as e:
            doc_status = f"Error: {str(e)}"
        
        try:
            logger.info("Checking Knowledge Graph server")
            async def check_kg():
                try:
                    async with MCPKnowledgeGraphConnector() as connector:
                        await connector.list_tools()
                        return "Running"
                except Exception as e:
                    logger.error(f"Knowledge Graph server error: {str(e)}")
                    return f"Error: {str(e)}"
            
            kg_status = loop.run_until_complete(check_kg())
        except Exception as e:
            kg_status = f"Error: {str(e)}"
        
        return jsonify({
            'erp_server': erp_status,
            'document_storage_server': doc_status,
            'knowledge_graph_server': kg_status
        })
    
    finally:
        loop.close()

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return a response."""
    user_message = request.json.get('message', '')
    
    logger.info(f"Received message: {user_message}")
    
    if not user_message:
        logger.warning("Empty message received")
        return jsonify({'response': 'Please enter a message.'})
    
    # Process the user message and generate a response
    logger.info("Processing message...")
    response = process_message(user_message)
    logger.info(f"Response generated: {response[:100]}..." if len(response) > 100 else f"Response generated: {response}")
    
    return jsonify({'response': response})

def process_message(message):
    """
    Process a user message and generate a response.
    
    This implementation uses OpenAI Agents to understand natural language queries
    and map them to the appropriate connector methods. If OpenAI is not available,
    it falls back to a keyword-based approach.
    """
    logger.info(f"Processing message: {message}")
    
    # Check for special commands
    if message.lower() == "clear cache":
        query_cache.clear()
        logger.info("Cache cleared successfully")
        return "Cache cleared successfully. This should help with getting fresh data."
    
    # Create an event loop for async operations
    logger.info("Creating event loop for async operations")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Check if we have an OpenAI client
        if openai_client:
            return process_with_openai(message)
        else:
            # Fall back to keyword-based processing
            logger.info("OpenAI client not available, falling back to keyword-based processing")
            return process_with_keywords(message.lower())
    
    finally:
        loop.close()

def process_with_openai(message):
    """
    Process a message using OpenAI Agents.
    
    This function uses OpenAI to understand the user's intent and generate
    appropriate SQL queries or other actions.
    """
    logger.info("Processing with OpenAI")
    
    # Check for special commands first
    if 'check status' in message.lower():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(check_server_status())
        finally:
            loop.close()
    
    # Check for help command
    if message.lower().strip() == 'help':
        return get_help_message()
    
    # Define the available tools for OpenAI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_database",
                "description": "Query the ERP database using SQL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL query to execute"
                        }
                    },
                    "required": ["sql_query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_database_schema",
                "description": "Get the schema of the ERP database or a specific table",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "The name of the table to get the schema for. If not provided, list all tables."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_document_storage",
                "description": "Query the document storage",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection_name": {
                            "type": "string",
                            "description": "The name of the collection to query"
                        },
                        "query": {
                            "type": "object",
                            "description": "The query to execute"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "The maximum number of documents to return"
                        }
                    },
                    "required": ["collection_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_knowledge_graph",
                "description": "Query the knowledge graph",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["node_types", "relationship_types", "nodes", "relationships"],
                            "description": "The type of query to execute"
                        },
                        "node_type": {
                            "type": "string",
                            "description": "The type of node to query (required if query_type is 'nodes')"
                        },
                        "relationship_type": {
                            "type": "string",
                            "description": "The type of relationship to query (required if query_type is 'relationships')"
                        }
                    },
                    "required": ["query_type"]
                }
            }
        }
    ]
    
    # Create the system message
    system_message = """You are an AI assistant that helps users query databases and knowledge graphs.
        
You have access to the following data sources:
1. ERP Database - Contains business data like customers, orders, products, etc.
   - Use SQL queries to access this data
   - First check available tables with get_database_schema()
   - Then query specific tables with SQL via query_database()

2. Document Storage - Contains unstructured documents
   - Use query_document_storage() to search for documents
   - First check available collections
   - Then search within specific collections

3. Knowledge Graph - Contains relationships between entities
   - Use query_knowledge_graph() to explore the graph
   - Check node_types and relationship_types first
   - Then query specific nodes and relationships

When a user asks a question, you MUST follow these steps and explicitly show each step in your response:

Step 1: Analyze the user's question and determine which data source(s) are needed.
Step 2: Explain your reasoning for choosing these data sources.
Step 3: For each data source:
   a. First explore the schema/structure (tables, collections, node types)
   b. Formulate the appropriate query (SQL for ERP, etc.)
   c. Execute the query using the provided tools
Step 4: If needed, combine results from multiple data sources
Step 5: Present the final results in a clear, human-readable format

For complex questions that require multiple data sources:
1. Break down the question into sub-questions
2. Query each data source separately
3. Combine the results to answer the original question

If you receive an error message indicating that a server is not running, inform the user that they need to start the appropriate MCP server:
- For ERP Database: "The MCP ERP server needs to be running at http://localhost:8001"
- For Document Storage: "The MCP Document Storage server needs to be running at http://localhost:8002"
- For Knowledge Graph: "The MCP Knowledge Graph server needs to be running at http://localhost:8003"

For example, if a user asks "How many customers do we have?", your response should look like:

"To answer your question about how many customers we have:

Step 1: I'll need to access the ERP database since customer information is typically stored there.

Step 2: Customer data is usually stored in a 'customers' table in the ERP system, so I'll first check if this table exists.

Step 3a: Let me explore the database schema:
[Schema exploration results]

Step 3b: Based on the schema, I'll construct a SQL query to count the number of customers:
```sql
SELECT COUNT(*) AS customer_count FROM customers
```

Step 3c: Executing this query against the ERP database...

Step 5: Results: [show the actual results]"

Always structure your responses this way to make your reasoning process transparent.
"""
    
    try:
        # Create a new assistant with the tools
        assistant = openai_client.beta.assistants.create(
            name="Database Query Assistant",
            instructions=system_message,
            tools=tools,
            model="gpt-4o",
            temperature=0.3  # Lower temperature for more focused responses
        )
        
        # Create a thread
        thread = openai_client.beta.threads.create()
        
        # Add the user message to the thread
        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )
        
        # Run the assistant
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        
        # Poll for the run to complete with a timeout
        start_time = time.time()
        timeout = 20  # 20 seconds timeout for the entire run
        tool_timeout = 8  # 8 seconds timeout for tool calls
        
        while run.status in ["queued", "in_progress", "requires_action"]:
            # Check if we've exceeded the timeout
            if time.time() - start_time > timeout:
                logger.warning(f"OpenAI run timed out after {timeout} seconds")
                try:
                    # Try to cancel the run
                    openai_client.beta.threads.runs.cancel(
                        thread_id=thread.id,
                        run_id=run.id
                    )
                except Exception as e:
                    logger.error(f"Error canceling run: {str(e)}")
                    
                # Clean up
                try:
                    openai_client.beta.assistants.delete(assistant.id)
                except Exception as e:
                    logger.error(f"Error deleting assistant: {str(e)}")
                    
                return "I'm sorry, but the request is taking too long to process. Please try a simpler query or try again later."
                
            # Sleep for a short time to avoid excessive API calls
            time.sleep(0.5)
            
            # Retrieve the current run status
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            
            # Check if the run requires action (tool calls)
            if run.status == "requires_action":
                tool_outputs = []
                tool_start_time = time.time()
                
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    # Check if we've exceeded the tool timeout
                    if time.time() - tool_start_time > tool_timeout:
                        logger.warning(f"Tool calls timed out after {tool_timeout} seconds")
                        break
                        
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    try:
                        # Execute the appropriate function based on the tool call with a timeout
                        result = execute_tool_call(function_name, arguments)
                    except Exception as e:
                        logger.error(f"Error executing tool call: {str(e)}")
                        result = f"Error executing {function_name}: {str(e)}"
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": result
                    })
                
                # If we have tool outputs, submit them
                if tool_outputs:
                    try:
                        # Submit the tool outputs
                        run = openai_client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread.id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                    except Exception as e:
                        logger.error(f"Error submitting tool outputs: {str(e)}")
                        # If we can't submit tool outputs, cancel the run
                        try:
                            openai_client.beta.threads.runs.cancel(
                                thread_id=thread.id,
                                run_id=run.id
                            )
                        except:
                            pass
                        return "I encountered an error while processing your request. Please try again."
        
        # Get the messages from the thread
        messages = openai_client.beta.threads.messages.list(
            thread_id=thread.id
        )
        
        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                # Clean up by deleting the assistant and thread
                openai_client.beta.assistants.delete(assistant.id)
                return message.content[0].text.value
        
        # Clean up by deleting the assistant and thread
        openai_client.beta.assistants.delete(assistant.id)
        return "I couldn't generate a response. Please try again."
    
    except Exception as e:
        logger.error(f"Error processing with OpenAI: {str(e)}")
        return f"I encountered an error while processing your request: {str(e)}"

def execute_tool_call(function_name, arguments):
    """Execute a tool call and return the result."""
    logger.info(f"Executing tool call: {function_name} with arguments: {arguments}")
    
    # Create a cache key from the function name and arguments
    cache_key = f"{function_name}:{json.dumps(arguments, sort_keys=True)}"
    
    # Check if we have a cached result
    if cache_key in query_cache:
        logger.info(f"Using cached result for {function_name}")
        return query_cache[cache_key]
    
    # Create an event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Set a timeout for all async operations
        start_time = time.time()
        timeout = 10  # 10 seconds timeout for database operations
        
        if function_name == "query_database":
            sql_query = arguments["sql_query"]
            result = loop.run_until_complete(execute_sql_query(sql_query))
        
        elif function_name == "get_database_schema":
            table_name = arguments.get("table_name")
            if table_name:
                result = loop.run_until_complete(query_table_schema(table_name))
            else:
                result = loop.run_until_complete(query_erp_tables())
        
        elif function_name == "query_document_storage":
            collection_name = arguments["collection_name"]
            query = arguments.get("query", {})
            limit = arguments.get("limit", 5)
            result = loop.run_until_complete(find_documents(collection_name, query, limit))
        
        elif function_name == "query_knowledge_graph":
            query_type = arguments["query_type"]
            
            if query_type == "node_types":
                result = loop.run_until_complete(query_node_types())
            elif query_type == "relationship_types":
                result = loop.run_until_complete(query_relationship_types())
            elif query_type == "nodes":
                node_type = arguments["node_type"]
                result = loop.run_until_complete(query_nodes(node_type))
            elif query_type == "relationships":
                relationship_type = arguments["relationship_type"]
                result = loop.run_until_complete(query_relationships(relationship_type))
            else:
                result = "Invalid query type"
        else:
            result = f"Unknown function: {function_name}"
        
        # Cache the result for future use (only if it's not an error message)
        if not isinstance(result, str) or not result.startswith("Error"):
            query_cache[cache_key] = result
            
        # Log execution time
        execution_time = time.time() - start_time
        logger.info(f"Tool call executed in {execution_time:.2f} seconds")
        
        return result
    
    except asyncio.TimeoutError:
        logger.error(f"Timeout executing {function_name}")
        return f"Error: Operation timed out after {timeout} seconds"
    
    except Exception as e:
        logger.error(f"Error executing {function_name}: {str(e)}")
        return f"Error executing {function_name}: {str(e)}"
    
    finally:
        loop.close()

def process_with_keywords(message):
    """
    Process a message using keyword matching.
    
    This is a fallback method when the OpenAI client is not available.
    """
    logger.info(f"Processing message with keywords (lowercase): {message}")
    
    # Create an event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Check status command
        if 'check status' in message.lower():
            return loop.run_until_complete(check_server_status())
        
        # ERP queries
        if 'list tables' in message or 'show tables' in message:
            return loop.run_until_complete(query_erp_tables())
        
        if 'table schema' in message and 'for' in message:
            # Extract the table name
            parts = message.split('for')
            if len(parts) > 1:
                table_name = parts[1].strip()
                return loop.run_until_complete(query_table_schema(table_name))
        
        if 'sql' in message or 'query' in message:
            # Extract the SQL query
            if 'sql' in message:
                query = message.split('sql', 1)[1].strip()
            else:
                query = message.split('query', 1)[1].strip()
            
            return loop.run_until_complete(execute_sql_query(query))
        
        # Document Storage queries
        if 'list collections' in message or 'show collections' in message:
            return loop.run_until_complete(query_collections())
        
        if 'collection info' in message and 'for' in message:
            # Extract the collection name
            parts = message.split('for')
            if len(parts) > 1:
                collection_name = parts[1].strip()
                return loop.run_until_complete(query_collection_info(collection_name))
        
        if 'find documents' in message and 'in' in message:
            # Extract the collection name
            parts = message.split('in')
            if len(parts) > 1:
                collection_name = parts[1].strip()
                return loop.run_until_complete(find_documents(collection_name))
        
        # Knowledge Graph queries
        if 'node types' in message:
            return loop.run_until_complete(query_node_types())
        
        if 'relationship types' in message:
            return loop.run_until_complete(query_relationship_types())
        
        if 'nodes of type' in message:
            # Extract the node type
            parts = message.split('type')
            if len(parts) > 1:
                node_type = parts[1].strip()
                return loop.run_until_complete(query_nodes(node_type))
        
        if 'relationships of type' in message:
            # Extract the relationship type
            parts = message.split('type')
            if len(parts) > 1:
                rel_type = parts[1].strip()
                return loop.run_until_complete(query_relationships(rel_type))
        
        # Help message
        if 'help' in message:
            return get_help_message()
        
        # Default response
        return "I'm not sure how to respond to that. Type 'help' to see what I can do."
    
    finally:
        loop.close()

async def check_server_status():
    """Check if the MCP servers are running."""
    logger.info("Checking server status")
    
    status = {
        "ERP Server": "Not running",
        "Document Storage Server": "Not running",
        "Knowledge Graph Server": "Not running"
    }
    
    # Check ERP server
    try:
        async with MCPERPConnector() as connector:
            await connector.list_tables()
            status["ERP Server"] = "Running"
    except Exception as e:
        logger.error(f"Error checking ERP server: {str(e)}")
    
    # Check Document Storage server
    try:
        async with MCPDocumentStorageConnector() as connector:
            await connector.list_collections()
            status["Document Storage Server"] = "Running"
    except Exception as e:
        logger.error(f"Error checking Document Storage server: {str(e)}")
    
    # Check Knowledge Graph server
    try:
        async with MCPKnowledgeGraphConnector() as connector:
            await connector.get_node_types()
            status["Knowledge Graph Server"] = "Running"
    except Exception as e:
        logger.error(f"Error checking Knowledge Graph server: {str(e)}")
    
    # Format the status message
    message = "MCP Server Status:\n\n"
    for server, status_value in status.items():
        color = "green" if status_value == "Running" else "red"
        message += f"{server}: {status_value}\n"
    
    return message

# ERP connector methods
async def query_erp_tables():
    """Query the ERP server for a list of tables."""
    logger.info("Querying ERP tables")
    try:
        logger.info("Creating ERP connector")
        async with MCPERPConnector() as connector:
            logger.info("Calling list_tables method")
            # Set a short timeout to prevent hanging
            tables = await asyncio.wait_for(connector.list_tables(timeout=3.0), timeout=5.0)
            logger.info(f"Received tables: {tables}")
            return f"Tables in the ERP database: {', '.join(tables)}"
    except asyncio.TimeoutError:
        logger.error("Timeout querying ERP tables")
        return "Error: Timeout querying ERP tables. The server might be busy or unresponsive."
    except TimeoutError:
        logger.error("Connector timeout querying ERP tables")
        return "Error: Connector timeout querying ERP tables. The server might be busy or unresponsive."
    except Exception as e:
        logger.error(f"Error querying ERP tables: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the ERP server. Please make sure the MCP ERP server is running at http://localhost:8001."
        return f"Error querying ERP tables: {str(e)}"

async def query_table_schema(table_name):
    """Query the ERP server for a table schema."""
    try:
        async with MCPERPConnector() as connector:
            # Set a short timeout to prevent hanging
            schema = await asyncio.wait_for(connector.get_table_schema(table_name, timeout=3.0), timeout=5.0)
            return f"Schema for table '{table_name}':\n{json.dumps(schema, indent=2)}"
    except asyncio.TimeoutError:
        logger.error(f"Timeout querying schema for table {table_name}")
        return f"Error: Timeout querying schema for table '{table_name}'. The server might be busy or unresponsive."
    except TimeoutError:
        logger.error(f"Connector timeout querying schema for table {table_name}")
        return f"Error: Connector timeout querying schema for table '{table_name}'. The server might be busy or unresponsive."
    except Exception as e:
        logger.error(f"Error querying table schema: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the ERP server. Please make sure the MCP ERP server is running at http://localhost:8001."
        return f"Error querying table schema: {str(e)}"

async def execute_sql_query(query):
    """Execute a SQL query on the ERP server."""
    try:
        async with MCPERPConnector() as connector:
            # Set a short timeout to prevent hanging
            results = await asyncio.wait_for(connector.execute_sql_query(query, timeout=3.0), timeout=5.0)
            return f"Query results:\n{json.dumps(results, indent=2)}"
    except asyncio.TimeoutError:
        logger.error(f"Timeout executing SQL query: {query}")
        return f"Error: Timeout executing SQL query. The server might be busy or unresponsive."
    except TimeoutError:
        logger.error(f"Connector timeout executing SQL query: {query}")
        return f"Error: Connector timeout executing SQL query. The server might be busy or unresponsive."
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the ERP server. Please make sure the MCP ERP server is running at http://localhost:8001."
        return f"Error executing SQL query: {str(e)}"

# Document Storage connector methods
async def query_collections():
    """Query the Document Storage server for a list of collections."""
    try:
        async with MCPDocumentStorageConnector() as connector:
            collections = await connector.list_collections()
            return f"Collections in the Document Storage: {', '.join(collections)}"
    except Exception as e:
        logger.error(f"Error querying collections: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Document Storage server. Please make sure the MCP Document Storage server is running at http://localhost:8002."
        return f"Error querying collections: {str(e)}"

async def query_collection_info(collection_name):
    """Query the Document Storage server for collection info."""
    try:
        async with MCPDocumentStorageConnector() as connector:
            info = await connector.get_collection_info(collection_name)
            return f"Info for collection '{collection_name}':\n{json.dumps(info, indent=2)}"
    except Exception as e:
        logger.error(f"Error querying collection info: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Document Storage server. Please make sure the MCP Document Storage server is running at http://localhost:8002."
        return f"Error querying collection info: {str(e)}"

async def find_documents(collection_name, query=None, limit=5):
    """Find documents in a collection."""
    try:
        async with MCPDocumentStorageConnector() as connector:
            query = query or {}
            documents = await connector.find_documents(collection_name, query, limit=limit)
            return f"Documents in collection '{collection_name}' (limited to {limit}):\n{json.dumps(documents, indent=2)}"
    except Exception as e:
        logger.error(f"Error finding documents: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Document Storage server. Please make sure the MCP Document Storage server is running at http://localhost:8002."
        return f"Error finding documents: {str(e)}"

# Knowledge Graph connector methods
async def query_node_types():
    """Query the Knowledge Graph server for node types."""
    try:
        async with MCPKnowledgeGraphConnector() as connector:
            node_types = await connector.get_node_types()
            return f"Node types in the Knowledge Graph: {', '.join(node_types)}"
    except Exception as e:
        logger.error(f"Error querying node types: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Knowledge Graph server. Please make sure the MCP Knowledge Graph server is running at http://localhost:8003."
        return f"Error querying node types: {str(e)}"

async def query_relationship_types():
    """Query the Knowledge Graph server for relationship types."""
    try:
        async with MCPKnowledgeGraphConnector() as connector:
            rel_types = await connector.get_relationship_types()
            return f"Relationship types in the Knowledge Graph: {', '.join(rel_types)}"
    except Exception as e:
        logger.error(f"Error querying relationship types: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Knowledge Graph server. Please make sure the MCP Knowledge Graph server is running at http://localhost:8003."
        return f"Error querying relationship types: {str(e)}"

async def query_nodes(node_type):
    """Query nodes of a specific type."""
    try:
        async with MCPKnowledgeGraphConnector() as connector:
            nodes = await connector.query_nodes(node_type=node_type)
            return f"Nodes of type '{node_type}':\n{json.dumps(nodes, indent=2)}"
    except Exception as e:
        logger.error(f"Error querying nodes: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Knowledge Graph server. Please make sure the MCP Knowledge Graph server is running at http://localhost:8003."
        return f"Error querying nodes: {str(e)}"

async def query_relationships(rel_type):
    """Query relationships of a specific type."""
    try:
        async with MCPKnowledgeGraphConnector() as connector:
            relationships = await connector.query_relationships(relationship_type=rel_type)
            return f"Relationships of type '{rel_type}':\n{json.dumps(relationships, indent=2)}"
    except Exception as e:
        logger.error(f"Error querying relationships: {str(e)}", exc_info=True)
        if "ConnectError" in str(e) or "Connection refused" in str(e):
            return "Error: Cannot connect to the Knowledge Graph server. Please make sure the MCP Knowledge Graph server is running at http://localhost:8003."
        return f"Error querying relationships: {str(e)}"

def get_help_message():
    """Return a help message with available commands."""
    return """
    You can ask me questions in natural language, and I'll understand and answer them.
    For example:
    - "How many customers do we have?"
    - "Show me the latest orders"
    - "What products are in stock?"
    - "Find documents about marketing strategy"
    - "Which customers placed orders for product X?"
    - "What's the relationship between customer Y and supplier Z?"
    
    I'll analyze your question, determine which data source to use, and generate the appropriate query.
    I'll also show you my reasoning process so you can understand how I arrived at the answer.
    
    Special commands:
    - "help" - Show this help message
    - "check status" - Check if the MCP servers are running
    - "clear cache" - Clear the query cache to get fresh data
    
    To use my full capabilities, make sure the MCP servers are running:
    - ERP Database: http://localhost:8001
    - Document Storage: http://localhost:8002
    - Knowledge Graph: http://localhost:8003
    
    You can also use these specific commands:
    
    ERP Database:
    - "list tables" - Show all tables in the ERP database
    - "table schema for [table_name]" - Show the schema for a specific table
    - "sql [query]" - Execute a SQL query (e.g., "sql SELECT * FROM customers LIMIT 5")
    
    Document Storage:
    - "list collections" - Show all collections in the document storage
    - "collection info for [collection_name]" - Show info about a specific collection
    - "find documents in [collection_name]" - Find documents in a collection
    
    Knowledge Graph:
    - "node types" - Show all node types in the knowledge graph
    - "relationship types" - Show all relationship types in the knowledge graph
    - "nodes of type [node_type]" - Show nodes of a specific type
    - "relationships of type [rel_type]" - Show relationships of a specific type
    
    Other:
    - "help" - Show this help message
    - "check status" - Check if the MCP servers are running
    """

if __name__ == '__main__':
    # Create the templates directory if it doesn't exist
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Run the Flask app
    app.run(debug=True, port=5000)