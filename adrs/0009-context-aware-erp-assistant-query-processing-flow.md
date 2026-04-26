# ADR-0009: Context-Aware ERP Assistant Query Processing Flow
**Status**: Accepted
**Date**: 2025-09-01
**Author**: Julianus Kath


## Status
**ACCEPTED** - Implemented and Production Ready

## Date
2025-01-04

## Context

The ERP Assistant system has evolved from a simple query-response mechanism to a sophisticated context-aware conversational AI that maintains full conversation history and makes intelligent decisions about when to clarify versus when to execute queries directly. This ADR documents the complete query processing flow and the significant improvements made to context awareness throughout the conversation pipeline.

The key challenge addressed was enabling natural, multi-turn conversations where users can ask follow-up questions like "What about their names?" after previously asking about customers, without having to repeat context or be overly specific in each query.

## Decision

We have implemented a comprehensive context-aware query processing flow with the following architectural improvements:

### 1. Context-Aware Architecture Overview

```
┌─────────────────┐    Full Conversation    ┌──────────────────┐    Context-Aware     ┌─────────────────┐
│   Streamlit UI  │ ──────────────────────► │ LangGraph Service │ ──────────────────► │ Intent Parser   │
│ (Chat History)  │                         │ (Conversation     │                     │ (GPT-4o with    │
└─────────────────┘                         │  Processing)      │                     │  Full Context)  │
        │                                   └──────────────────┘                     └─────────────────┘
        │                                            │                                         │
        ▼                                            ▼                                         ▼
┌─────────────────┐                         ┌──────────────────┐                     ┌─────────────────┐
│ Session State   │                         │ Workflow State   │                     │ Decision Engine │
│ Persistence     │                         │ Management       │                     │ (Clarify vs     │
│ (chat_logs.json)│                         │ (Full Messages)  │                     │  Query Direct)  │
└─────────────────┘                         └──────────────────┘                     └─────────────────┘
```

### 2. Enhanced Context Awareness Features

#### 2.1 Full Conversation History Maintenance

**Previous Limitation:** Only the latest user message was processed, losing conversation context.

**New Implementation:**
```python
# In langgraph_service.py - process_conversation endpoint
class ConversationRequest(BaseModel):
    messages: list  # Full conversation history
    api_key: str

# Workflow receives complete message array
result = await workflow.process_conversation(request.messages)
```

**State Management Enhancement:**
```python
# In graph_definition.py - WorkflowState
class WorkflowState(TypedDict):
    messages: List[Dict[str, Any]]  # NEW: Full conversation context
    user_input: str                 # Latest user message for compatibility
    intent_analysis: Optional[Dict[str, Any]]
    # ... other fields
```

#### 2.2 Context-Aware Intent Parsing

**Revolutionary Improvement:** The intent parser now analyzes the entire conversation history to make intelligent decisions.

**Enhanced Prompt Design:**
```python
INTENT_PARSER_PROMPT = """
You are an expert agent that maintains full conversation context and decides whether to ask clarifying questions or execute queries.

Here is the chat history as a JSON array of messages (role: user/assistant, content):
{messages}

Based on the entire conversation, decide:
1. If the user's last message requires you to ask a follow-up question
2. Otherwise, generate a safe single SELECT SQL statement.

Examples:
User: "How many customers in New York?" → {{"operation": "query", "sql": "SELECT COUNT(*) FROM customers WHERE city = 'New York'"}}

User: "What about their names?" (after asking about customers) → {{"operation": "query", "sql": "SELECT name FROM customers WHERE city = 'New York'", "reasoning": "Context from previous query about New York customers"}}
"""
```

**Context Processing Logic:**
```python
async def _parse_intent(self, state: WorkflowState) -> WorkflowState:
    # Use the full conversation messages for context-aware intent parsing
    messages = state.get("messages", [])
    prompt = format_intent_parser_prompt(messages)
    
    response = await self.llm.ainvoke([SystemMessage(content=prompt)])
    intent_analysis = self._parse_intent_json_response(response.content)
```

#### 2.3 Intelligent Clarification vs Direct Query Decision

**Decision Engine Enhancement:**
```python
def _route_after_intent(self, state: WorkflowState) -> str:
    intent = state.get("intent_analysis", {})
    operation = intent.get("operation", "DATA_QUERY")
    
    # Handle new conversation-aware operations
    if operation == "clarify":
        return "clarify"
    elif operation == "query":
        # Check if SQL is already provided by context-aware intent parser
        if "sql" in intent and intent["sql"]:
            return "execute_direct"  # Skip schema and SQL generation
        else:
            return "query"  # Go through normal flow
```

**Direct Execution Path:**
```python
async def _execute_direct(self, state: WorkflowState) -> WorkflowState:
    """Execute SQL query directly when provided by intent parser."""
    intent = state["intent_analysis"]
    sql_query = intent.get("sql", "")
    
    # Store the SQL query in state for consistency
    state["sql_query"] = sql_query
    
    # Execute the query directly
    results = await execute_sql_query(sql_query)
    state["query_results"] = results
```

### 3. Complete Query Processing Flow

#### 3.1 Enhanced 10-Step Processing Pipeline

```
1. User Input (Streamlit UI)
   ├─ Maintains full conversation history in session state
   ├─ Packages entire message array in API request
   └─ Preserves context across user sessions via chat_logs.json

2. HTTP Service Layer (LangGraph Service)
   ├─ Receives ConversationRequest with full message history
   ├─ Validates API key and input
   └─ Invokes workflow.process_conversation(messages)

3. Context-Aware Intent Parsing (LangGraph Workflow)
   ├─ Analyzes ENTIRE conversation history (not just latest message)
   ├─ Uses GPT-4o with conversation-aware prompts
   ├─ Decides: clarify vs query vs direct execution
   └─ Can generate SQL immediately if context is sufficient

4. Intelligent Routing Decision
   ├─ clarify → Generate clarifying question → END
   ├─ query (with SQL) → execute_direct → format_results → END
   └─ query (without SQL) → get_schema → generate_sql → execute_query → format_results → END

5. Schema Retrieval (if needed)
   ├─ MCP client calls get_schema tool
   └─ Retrieves database structure for SQL generation

6. SQL Generation (if needed)
   ├─ Uses schema + intent + conversation context
   ├─ GPT-4o generates safe SELECT queries
   └─ Enforces security constraints (SELECT only, LIMIT clauses)

7. Query Execution
   ├─ MCP server processes SQL against PostgreSQL
   ├─ Enforces safety (read-only, row limits)
   └─ Returns formatted results

8. Result Formatting
   ├─ Context-aware formatting using conversation history
   ├─ Extremely concise responses (1-2 sentences)
   └─ User-friendly natural language

9. Response Delivery
   ├─ Updates conversation history with assistant response
   ├─ Returns structured response with operation type
   └─ Handles both clarifications and direct answers

10. UI Update & Persistence
    ├─ Streamlit displays response in chat interface
    ├─ Updates session state with new message
    └─ Persists conversation to chat_logs.json
```

#### 3.2 Context Preservation Mechanisms

**Session State Management:**
```python
# In app.py - Streamlit UI
if "messages" not in st.session_state:
    st.session_state.messages = []

# Conversation persistence
def save_conversation_to_file(messages):
    with open("chat_logs.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        }, f, indent=2)
```

**Workflow State Continuity:**
```python
# In graph_definition.py - process_conversation
initial_state = WorkflowState(
    messages=messages.copy(),  # Full conversation history
    user_input=last_user_message,  # Latest message for compatibility
    # ... other fields
)
```

### 4. Context-Aware Conversation Examples

#### 4.1 Multi-Turn Query Resolution

**Conversation Flow:**
```
User: "How many customers do we have?"
Assistant: "10 customers"

User: "What about their names?"
Context-Aware Processing:
- Intent parser sees full conversation history
- Understands "their" refers to customers from previous query
- Generates: SELECT name FROM customers
Assistant: "John Smith, Jane Doe, Bob Johnson, ..."

User: "Any from New York?"
Context-Aware Processing:
- Understands context is still about customers
- Generates: SELECT name FROM customers WHERE city = 'New York'
Assistant: "John Smith, Jane Doe"
```

#### 4.2 Intelligent Clarification

**Conversation Flow:**
```
User: "Show me sales data"
Context-Aware Processing:
- Recognizes insufficient information
- operation: "clarify"
- missing_fields: ["time_period", "specific_metrics"]
Assistant: "Which time period would you like to see sales data for? (e.g., last month, this year, specific date range)"

User: "Last month"
Context-Aware Processing:
- Combines previous context (sales data) with new info (last month)
- Generates appropriate SQL with date filtering
Assistant: "Last month's sales totaled $45,230 across 127 transactions"
```

### 5. Technical Implementation Details

#### 5.1 Enhanced Prompt Engineering

**Context-Aware Clarification Prompts:**
```python
def format_clarification_prompt(messages: list, missing_fields: list) -> str:
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    return CLARIFICATION_PROMPT.format(
        last_user_message=last_user_message,
        messages=json.dumps(messages, indent=2),
        missing_fields=", ".join(missing_fields)
    )
```

**JSON Response Parsing:**
```python
def _parse_intent_json_response(self, response_text: str) -> Dict[str, Any]:
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        
        result = {
            "operation": parsed.get("operation", "query"),
            "reasoning": parsed.get("reasoning", ""),
        }
        
        if result["operation"] == "clarify":
            result["missing_fields"] = parsed.get("missing_fields", [])
        else:
            result["sql"] = parsed.get("sql", "")
```

#### 5.2 Workflow State Management

**Message History Preservation:**
```python
# Throughout the workflow, messages are preserved and updated
state["messages"].append({
    "role": "assistant",
    "content": response.content
})
```

**Backward Compatibility:**
```python
# Support for both old process_query and new process_conversation
async def process_query(self, user_input: str) -> str:
    # Convert single query to conversation format
    initial_state = WorkflowState(
        messages=[{"role": "user", "content": user_input}],
        user_input=user_input,
        # ... other fields
    )
```

### 6. Performance and Scalability Improvements

#### 6.1 Context Processing Optimization

**Efficient Message Handling:**
- Only relevant conversation history is passed to LLM
- Token usage optimized through selective context inclusion
- Conversation pruning for very long chat histories (future enhancement)

**Caching Strategy:**
- Schema information cached to reduce MCP calls
- Intent analysis patterns could be cached (future enhancement)
- Database connection pooling for concurrent users

#### 6.2 Error Handling with Context

**Context-Aware Error Recovery:**
```python
async def _handle_error(self, state: WorkflowState) -> WorkflowState:
    error_info = state.get("error_info", {})
    user_input = state["user_input"]
    
    # Use conversation context for better error messages
    prompt = format_error_handler_prompt(
        user_input=user_input,
        error_type=error_info.get("type", "unknown_error"),
        error_message=error_info.get("message", "Unknown error occurred"),
        context=error_info.get("context", "")
    )
```

## Consequences

### Positive Outcomes

1. **Revolutionary User Experience:**
   - **Natural Conversations:** Users can ask follow-up questions without repeating context
   - **Intelligent Clarification:** System asks specific questions only when necessary
   - **Context Continuity:** Maintains conversation flow across multiple queries
   - **Reduced Cognitive Load:** Users don't need to be overly specific in each query

2. **Technical Excellence:**
   - **Context Preservation:** Full conversation history maintained throughout pipeline
   - **Intelligent Routing:** Optimized workflow paths based on context analysis
   - **Direct Execution:** Bypasses unnecessary steps when context provides sufficient information
   - **Backward Compatibility:** Supports both single queries and full conversations

3. **AI Processing Improvements:**
   - **Context-Aware Prompts:** LLM receives full conversation context for better decisions
   - **Reduced Ambiguity:** Better understanding of user intent through conversation history
   - **Smarter SQL Generation:** Can reference previous queries and results
   - **Improved Error Handling:** Context-aware error messages and recovery

4. **System Robustness:**
   - **State Management:** Comprehensive workflow state with message history
   - **Session Persistence:** Conversations saved and restored across sessions
   - **Graceful Degradation:** Fallback mechanisms when context is insufficient
   - **Performance Optimization:** Efficient context processing and caching

### Challenges Addressed

1. **Context Loss Prevention:**
   - **Problem:** Previous system lost conversation context between queries
   - **Solution:** Full message history preservation and processing

2. **Over-Clarification Reduction:**
   - **Problem:** System asked unnecessary clarifying questions
   - **Solution:** Context-aware decision making about when to clarify vs execute

3. **User Experience Friction:**
   - **Problem:** Users had to repeat information in follow-up questions
   - **Solution:** Intelligent context understanding and reference resolution

4. **Workflow Efficiency:**
   - **Problem:** Unnecessary processing steps for context-rich queries
   - **Solution:** Direct execution path when context provides sufficient information

### Future Enhancements

1. **Advanced Context Management:**
   - Conversation summarization for very long chat histories
   - Context relevance scoring and pruning
   - Multi-session context persistence

2. **Enhanced AI Capabilities:**
   - Few-shot learning from conversation patterns
   - Personalized response styles based on user preferences
   - Proactive suggestions based on conversation context

3. **Performance Optimizations:**
   - Context-aware caching strategies
   - Parallel processing for complex multi-step queries
   - Real-time context analysis and prediction

## Implementation Notes

### Key Files Modified

1. **`chatbot_ui/langgraph_service.py`:**
   - Added `process_conversation` endpoint
   - Enhanced request/response models with conversation support
   - Maintained backward compatibility with `process_query`

2. **`langgraph_integration/graph_definition.py`:**
   - Enhanced `WorkflowState` with full message history
   - Implemented context-aware intent parsing
   - Added direct execution path for context-rich queries
   - Enhanced routing logic with conversation awareness

3. **`langgraph_integration/prompts.py`:**
   - Redesigned intent parser prompt with conversation context
   - Added clarification prompt with message history
   - Enhanced all prompts to leverage conversation context

4. **`chatbot_ui/app.py`:**
   - Enhanced session state management
   - Added conversation persistence to `chat_logs.json`
   - Improved error handling with context preservation

### Testing Strategy

**Context-Aware Test Scenarios:**
```python
test_conversations = [
    # Multi-turn context preservation
    [
        {"role": "user", "content": "How many customers do we have?"},
        {"role": "assistant", "content": "10 customers"},
        {"role": "user", "content": "What about their names?"}
    ],
    
    # Clarification with context
    [
        {"role": "user", "content": "Show me sales data"},
        {"role": "assistant", "content": "Which time period...?"},
        {"role": "user", "content": "Last month"}
    ],
    
    # Complex context resolution
    [
        {"role": "user", "content": "How many customers in New York?"},
        {"role": "assistant", "content": "3 customers in New York"},
        {"role": "user", "content": "What products did they buy?"}
    ]
]
```

This context-aware architecture represents a significant evolution in conversational AI for enterprise data access, enabling natural, efficient, and intelligent interactions with complex database systems.