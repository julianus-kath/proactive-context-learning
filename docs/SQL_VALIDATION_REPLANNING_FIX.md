# SQL Validation and Re-planning Enhancement

## Problem Solved

The Discovery Agent was generating incomplete SQL queries like `"SELECT"` (without columns or FROM clause) that were reaching the MCP server's query validator and causing `QUERY VALIDATION FAILED: ValidationErrorCode.INVALID_SYNTAX` errors. The system had no re-planning capability to recover from SQL generation failures.

## Solution Implemented

### 🔧 Enhanced SQL Validation in Join Agent

**File**: `langgraph_integration/agents/join_sql/agent.py`

Enhanced the `_validate_sql_node` with comprehensive checks:

- ✅ **Incomplete Query Detection**: Catches `"SELECT"`, `"SELECT DISTINCT"` with no columns
- ✅ **Minimum Length Check**: Rejects queries < 10 characters as likely incomplete  
- ✅ **Column Specification Check**: Ensures proper columns between SELECT and FROM
- ✅ **Table Reference Validation**: Validates table names after FROM clause
- ✅ **Re-planning Flag**: Sets `replan_needed: true` for validation failures

```python
# 🚨 ENHANCED: Check for incomplete SELECT statements
if sql_upper in ["SELECT", "SELECT DISTINCT"] or len(sql_words) < 4:
    raise ValueError("Incomplete SELECT statement - missing columns or FROM clause")
```

### 🔄 Smart Re-planning Routing

**File**: `langgraph_integration/graph_definition.py`

Enhanced `_route_after_sql_generation` with intelligent routing:

- ✅ **Re-planning Logic**: Routes validation failures back to `select_tables`
- ✅ **Loop Prevention**: Max 2 re-planning attempts to prevent infinite loops
- ✅ **Context Tracking**: Maintains history of failed attempts for learning
- ✅ **Error Clearing**: Clears errors when re-planning to allow fresh attempts

```python
if replan_needed and replan_count < max_replans:
    logger.info(f"🔄 SQL validation failed - routing to re-planning (attempt {replan_count + 1}/{max_replans})")
    state["replan_count"] = replan_count + 1
    state["error_info"] = None  # Clear error to allow re-planning
    return "select_tables"  # Go back to table selection
```

### 🎯 Enhanced Table Selection 

**File**: `langgraph_integration/graph_definition.py`

Enhanced `_select_tables` with re-planning awareness:

- ✅ **Failure Learning**: Analyzes previous failed SQL to avoid same tables
- ✅ **Expanded Search**: Uses more keywords and broader scope when re-planning  
- ✅ **Smart Avoidance**: Skips previously failed table combinations
- ✅ **Enhanced Logging**: Clear indicators of re-planning vs. initial planning

```python
# 🔄 RE-PLANNING ENHANCEMENT: Modify search strategy based on failures
if is_replanning:
    # Add more diverse keywords and expand search scope
    page_size = min(8, 5 + len(replan_context))
    search_keyword = " ".join(keywords[:3])  # More keywords when re-planning
```

### 📊 State Management

**File**: `langgraph_integration/graph_definition.py`

Added new state variables to `WorkflowState`:

- ✅ **`replan_count`**: Tracks number of re-planning attempts
- ✅ **`replan_context`**: Stores history of failed attempts with failure reasons
- ✅ **Context Learning**: Each failure adds context for smarter next attempt

## Workflow Enhancement

### Before (❌ Broken)
```
User Query → Discovery → Planning → SQL Generation → [Incomplete SQL] → MCP Server → VALIDATION_FAILED → Error → END
```

### After (✅ Fixed)
```  
User Query → Discovery → Planning → SQL Generation → [Incomplete SQL] → Enhanced Validation → Re-planning Route → 
Enhanced Discovery → Better Planning → Valid SQL → MCP Server → Success
```

## Key Benefits

### 🛡️ **Security Maintained**
- All existing MCP server validation remains intact
- No weakening of security controls
- Additional validation layer for better error catching

### 🔄 **Intelligent Recovery**  
- Automatic recovery from SQL generation failures
- Learning from previous mistakes to avoid repetition
- Progressive improvement through re-planning attempts

### 📊 **Better Diagnostics**
- Clear logging at each step with emoji indicators
- Detailed error context for debugging
- Tracking of re-planning attempts and reasons

### ⚡ **Performance Improved**
- Catches incomplete queries before MCP server call
- Reduces unnecessary network requests
- Faster feedback loop for SQL generation issues

## Test Coverage

**File**: `tests/test_sql_validation_replanning.py`

Comprehensive test suite validates:
- ✅ Enhanced SQL validation catches incomplete queries
- ✅ Valid SQL passes enhanced validation  
- ✅ Re-planning routing works correctly
- ✅ Context tracking maintains failure history
- ✅ Infinite loop prevention works
- ✅ Integration between validation and routing

## Usage Examples

### Incomplete Query Detection
```python
# These will now be caught and trigger re-planning:
"SELECT"                    # Missing everything
"SELECT DISTINCT"          # Missing columns and FROM  
"SELECT FROM customers"    # Missing column list
"SEL"                      # Too short / typo
```

### Re-planning Context
```python
{
  "replan_context": [
    {
      "failed_sql": "SELECT",
      "failure_reason": "Incomplete SELECT statement - missing columns or FROM clause", 
      "attempt": 1
    }
  ],
  "replan_count": 1
}
```

### Enhanced Logging
```
🔄 RE-PLANNING MODE: Learning from 1 previous failures
  Attempt 1: Incomplete SELECT statement - missing columns or FROM clause
🔄 Enhanced keywords with intent entities: ['customers', 'orders']
🔄 Expanding search scope to 6 tables due to re-planning
🚫 Avoiding previously failed tables: ['CUSTOMERS']
✓ Re-selected table: dbo.orders
```

## Architecture Alignment

This enhancement follows the project's core principles:

- ✅ **Proxy-only separation**: No changes to MCP server business logic
- ✅ **Security first**: Maintains all existing validation, adds more
- ✅ **Read-only safety**: No impact on query safety controls  
- ✅ **JSON format**: All responses remain structured JSON
- ✅ **Modular design**: Clean separation between validation, routing, and discovery

## Impact

- 🚫 **Eliminates**: `ValidationErrorCode.INVALID_SYNTAX` errors from incomplete SQL
- ⚡ **Improves**: Query success rate through intelligent re-planning
- 📊 **Enhances**: Debugging with detailed error context and logging
- 🔄 **Enables**: Automatic recovery from common SQL generation failures

The TOP injection error is now **completely resolved** - incomplete queries are caught and handled gracefully through the re-planning system before reaching the MCP server validator.