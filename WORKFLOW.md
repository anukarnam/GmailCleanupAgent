# LangGraph Workflow Diagram

## State Machine Flow

```
                    START
                      │
                      ▼
            ┌─────────────────┐
            │  fetch_emails   │  Fetch from Gmail API
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  store_emails   │  Save to SQLite
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │categorize_emails│  Claude AI categorization
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ prepare_summary │  Generate category stats
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ await_approval  │  Pause for user input
            └────────┬────────┘
                     │
                     ▼
              ┌─────────────┐
              │ Has approval? │
              └─────┬────┬───┘
                    │    │
              YES   │    │  NO
                    │    │
                    ▼    ▼
         ┌──────────────┐  END
         │execute_deletion│
         └───────┬────────┘
                 │
                 ▼
               END
```

## State Schema

The agent maintains this state throughout the workflow:

```python
{
    # Configuration
    'max_emails': int,
    'batch_size': int,
    
    # Gmail data
    'emails_fetched': List[dict],
    'next_page_token': str | None,
    
    # Categorization
    'emails_to_categorize': List[dict],
    'categorization_results': List[dict],
    
    # User approval
    'category_summary': List[dict],
    'user_decisions': dict,
    
    # Execution
    'emails_to_delete': List[str],
    'deletion_results': dict,
    
    # Tracking
    'current_step': str,
    'total_processed': int,
    'errors': List[str]
}
```

## Key Design Decisions

### 1. Human-in-the-Loop Pattern
- Workflow pauses at `await_approval` node
- User reviews categorized emails
- Agent resumes only after explicit approval

### 2. State Persistence
- LangGraph's MemorySaver maintains state
- Agent can resume from any point
- Useful for long-running operations

### 3. Conditional Branching
- `should_execute_deletion()` checks user decisions
- Only proceeds to deletion if categories approved
- Enables safe, controlled execution

### 4. Error Handling
- Each node catches and logs errors
- State includes error list
- Agent continues even if individual operations fail

### 5. Batch Processing
- Emails processed in configurable batches
- Prevents API rate limit issues
- Allows for progress tracking

## Extending the Workflow

### Add a New Node

```python
def your_custom_node(state: AgentState) -> AgentState:
    # Your logic here
    return {**state, 'your_field': value}

# Add to workflow
workflow.add_node("your_node", your_custom_node)
workflow.add_edge("previous_node", "your_node")
```

### Add Conditional Logic

```python
def should_do_something(state: AgentState) -> str:
    if state['some_condition']:
        return "option_a"
    return "option_b"

workflow.add_conditional_edges(
    "node_name",
    should_do_something,
    {
        "option_a": "next_node_a",
        "option_b": "next_node_b"
    }
)
```

## Checkpointing

LangGraph automatically saves state at each node:
- Enables workflow resumption
- Supports rollback to previous states
- Useful for debugging and testing

```python
# Run with specific thread ID
config = {"configurable": {"thread_id": "cleanup_session_1"}}
agent.app.stream(initial_state, config)

# Resume same session later
agent.app.stream(update_state, config)
```