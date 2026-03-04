"""
LangGraph agent for orchestrating the Gmail cleanup workflow.
"""
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator

from .gmail_client import GmailClient
from .categorizer import EmailCategorizer
from .database import EmailDatabase


class AgentState(TypedDict):
    """State maintained throughout the agent workflow."""
    # Input
    max_emails: int
    batch_size: int

    # Gmail data
    emails_fetched: List[dict]
    next_page_token: str | None

    # Categorization
    emails_to_categorize: List[dict]
    categorization_results: List[dict]

    # User approval
    category_summary: List[dict]
    user_decisions: dict

    # Execution
    emails_to_delete: List[str]
    deletion_results: dict

    # Status tracking
    current_step: str
    total_processed: int
    errors: Annotated[List[str], operator.add]


class GmailCleanupAgent:
    """LangGraph-based agent for Gmail cleanup workflow."""

    def __init__(self, gmail_client: GmailClient, categorizer: EmailCategorizer,
                 database: EmailDatabase):
        self.gmail = gmail_client
        self.categorizer = categorizer
        self.db = database

        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("fetch_emails", self.fetch_emails)
        workflow.add_node("store_emails", self.store_emails)
        workflow.add_node("categorize_emails", self.categorize_emails)
        workflow.add_node("prepare_summary", self.prepare_summary)
        workflow.add_node("await_approval", self.await_approval)
        workflow.add_node("execute_deletion", self.execute_deletion)

        # Define the flow
        workflow.set_entry_point("fetch_emails")
        workflow.add_edge("fetch_emails", "store_emails")
        workflow.add_edge("store_emails", "categorize_emails")
        workflow.add_edge("categorize_emails", "prepare_summary")
        workflow.add_edge("prepare_summary", "await_approval")

        # Conditional edge: continue or end after approval
        workflow.add_conditional_edges(
            "await_approval",
            self.should_execute_deletion,
            {
                "execute": "execute_deletion",
                "skip": END
            }
        )
        workflow.add_edge("execute_deletion", END)

        return workflow

    def fetch_emails(self, state: AgentState) -> AgentState:
        """Step 1: Fetch emails from Gmail."""
        print(f"\n📧 Fetching emails from Gmail (max: {state['max_emails']})...")

        result = self.gmail.get_email_metadata(
            max_results=min(state['batch_size'], state['max_emails']),
            page_token=state.get('next_page_token')
        )

        print(f"   ✓ Fetched {len(result['emails'])} emails")

        return {
            **state,
            'emails_fetched': result['emails'],
            'next_page_token': result.get('next_page_token'),
            'current_step': 'fetch_emails',
            'total_processed': state.get('total_processed', 0) + len(result['emails'])
        }

    def store_emails(self, state: AgentState) -> AgentState:
        """Step 2: Store emails in database."""
        print(f"\n💾 Storing emails in database...")

        count = self.db.insert_emails(state['emails_fetched'])
        print(f"   ✓ Stored {count} emails")

        return {
            **state,
            'current_step': 'store_emails'
        }

    def categorize_emails(self, state: AgentState) -> AgentState:
        """Step 3: Categorize emails using OCI Cohere."""
        print(f"\n🤖 Categorizing emails with OCI Cohere...")

        # Get uncategorized emails from database
        uncategorized = self.db.get_uncategorized_emails(limit=state['batch_size'])

        if not uncategorized:
            print("   ℹ No uncategorized emails found")
            return {
                **state,
                'emails_to_categorize': [],
                'categorization_results': [],
                'current_step': 'categorize_emails'
            }

        print(f"   Processing {len(uncategorized)} emails...")

        # Categorize in batches
        results = self.categorizer.categorize_batch(uncategorized)

        # Update database
        for result in results:
            self.db.update_email_category(
                result['email_id'],
                result['category'],
                result['confidence']
            )
            self.db.log_action(
                result['email_id'],
                'categorized',
                f"{result['category']} (confidence: {result['confidence']:.2f})"
            )

        print(f"   ✓ Categorized {len(results)} emails")

        return {
            **state,
            'emails_to_categorize': uncategorized,
            'categorization_results': results,
            'current_step': 'categorize_emails'
        }

    def prepare_summary(self, state: AgentState) -> AgentState:
        """Step 4: Prepare category summary for user review."""
        print(f"\n📊 Preparing category summary...")

        summary = self.db.get_category_summary()

        return {
            **state,
            'category_summary': summary,
            'current_step': 'prepare_summary'
        }

    def await_approval(self, state: AgentState) -> AgentState:
        """Step 5: Wait for user approval (handled externally)."""
        print(f"\n⏸️  Awaiting user approval...")

        return {
            **state,
            'current_step': 'await_approval'
        }

    def should_execute_deletion(self, state: AgentState) -> str:
        """Conditional edge: Check if any categories were approved."""
        if state.get('user_decisions'):
            approved = [k for k, v in state['user_decisions'].items() if v == 'approve']
            if approved:
                return "execute"
        return "skip"

    def execute_deletion(self, state: AgentState) -> AgentState:
        """Step 6: Execute deletion of approved emails."""
        print(f"\n🗑️  Executing deletion...")

        # Get approved email IDs
        email_ids = self.db.get_approved_emails()

        if not email_ids:
            print("   ℹ No emails approved for deletion")
            return {
                **state,
                'deletion_results': {'success': 0, 'failed': 0},
                'current_step': 'execute_deletion'
            }

        print(f"   Deleting {len(email_ids)} emails...")

        # Trash emails (soft delete)
        results = self.gmail.trash_emails(email_ids)

        # Mark as deleted in database
        if results['success'] > 0:
            self.db.mark_emails_deleted(email_ids[:results['success']])

        print(f"   ✓ Successfully deleted {results['success']} emails")
        if results['failed'] > 0:
            print(f"   ⚠ Failed to delete {results['failed']} emails")

        return {
            **state,
            'emails_to_delete': email_ids,
            'deletion_results': results,
            'current_step': 'execute_deletion'
        }

    def run_fetch_and_categorize(self, max_emails: int = 100, batch_size: int = 50) -> dict:
        """
        Run the fetch and categorize steps.
        Returns the state for user review.
        """
        initial_state = {
            'max_emails': max_emails,
            'batch_size': batch_size,
            'emails_fetched': [],
            'next_page_token': None,
            'emails_to_categorize': [],
            'categorization_results': [],
            'category_summary': [],
            'user_decisions': {},
            'emails_to_delete': [],
            'deletion_results': {},
            'current_step': 'init',
            'total_processed': 0,
            'errors': []
        }

        # Run until we reach await_approval
        config = {"configurable": {"thread_id": "gmail_cleanup_1"}}

        for event in self.app.stream(initial_state, config):
            node_name = list(event.keys())[0]
            if node_name == "await_approval":
                return event[node_name]

        return initial_state

    def run_deletion(self, user_decisions: dict, thread_id: str = "gmail_cleanup_1"):
        """
        Continue from approval step with user decisions.
        """
        # Save user decisions to database
        for category, decision in user_decisions.items():
            if decision == 'approve':
                summary = self.db.get_category_summary()
                cat_data = next((s for s in summary if s['category'] == category), None)
                if cat_data:
                    self.db.save_user_decision(category, decision, cat_data['count'])

        # Continue execution
        config = {"configurable": {"thread_id": thread_id}}

        state_update = {'user_decisions': user_decisions}

        for event in self.app.stream(state_update, config):
            node_name = list(event.keys())[0]
            if node_name == "execute_deletion":
                return event[node_name]

        return {}