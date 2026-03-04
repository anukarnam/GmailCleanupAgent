#!/usr/bin/env python3
"""
Gmail Cleanup Agent - Main Entry Point

This agent uses LangGraph to orchestrate a workflow that:
1. Fetches emails from Gmail (metadata only)
2. Categorizes them using Claude AI
3. Presents results for user approval
4. Safely deletes approved emails
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.gmail_client import GmailClient
from src.categorizer import EmailCategorizer
from src.database import EmailDatabase
from src.agent import GmailCleanupAgent
from src.cli import CLI


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Initialize CLI
    cli = CLI()
    cli.show_welcome()

    try:
        # Get configuration
        oci_compartment_id = os.getenv('OCI_COMPARTMENT_ID')
        oci_service_endpoint = os.getenv('OCI_SERVICE_ENDPOINT')
        oci_auth_profile = os.getenv('OCI_AUTH_PROFILE', 'DEFAULT')
        gmail_creds = os.getenv('GMAIL_CREDENTIALS_PATH', 'config/credentials.json')
        db_path = os.getenv('DATABASE_PATH', 'data/gmail_cleanup.db')

        if not oci_compartment_id:
            cli.show_error("OCI_COMPARTMENT_ID not found in environment")
            cli.console.print("\nPlease set your OCI configuration:")
            cli.console.print("1. Copy .env.example to .env")
            cli.console.print("2. Add your OCI_COMPARTMENT_ID")
            cli.console.print("3. Add your OCI_SERVICE_ENDPOINT")
            cli.console.print("4. Set OCI_AUTH_PROFILE (from ~/.oci/config)")
            return 1

        if not oci_service_endpoint:
            cli.show_error("OCI_SERVICE_ENDPOINT not found in environment")
            return 1

        if not Path(gmail_creds).exists():
            cli.show_error(f"Gmail credentials not found at {gmail_creds}")
            cli.console.print("\nTo set up Gmail API:")
            cli.console.print("1. Go to https://console.cloud.google.com/")
            cli.console.print("2. Create a project and enable Gmail API")
            cli.console.print("3. Create OAuth 2.0 credentials (Desktop app)")
            cli.console.print("4. Download and save as config/credentials.json")
            return 1

        # Initialize components
        cli.console.print("\n[bold]Initializing components...[/bold]")

        gmail = GmailClient(gmail_creds)
        categorizer = EmailCategorizer(
            compartment_id=oci_compartment_id,
            service_endpoint=oci_service_endpoint,
            auth_profile=oci_auth_profile
        )
        db = EmailDatabase(db_path)
        agent = GmailCleanupAgent(gmail, categorizer, db)

        cli.console.print("[green]✓[/green] All components initialized\n")

        # Get processing parameters
        params = cli.get_processing_params()

        # Phase 1: Fetch and Categorize
        cli.console.print("\n[bold cyan]Phase 1: Fetching and Categorizing Emails[/bold cyan]")
        cli.console.print("=" * 60)

        state = agent.run_fetch_and_categorize(
            max_emails=params['max_emails'],
            batch_size=params['batch_size']
        )

        # Show results
        stats = db.get_stats()
        summary = db.get_category_summary()

        if not summary:
            cli.console.print("\n[yellow]No emails were categorized.[/yellow]")
            return 0

        cli.show_category_summary(summary, stats)

        # Phase 2: User Approval
        cli.console.print("\n[bold cyan]Phase 2: Review and Approval[/bold cyan]")
        cli.console.print("=" * 60)

        decisions = cli.get_approval_decisions(summary, db)

        # Check if any approved
        approved = [k for k, v in decisions.items() if v == 'approve']

        if not approved:
            cli.console.print("\n[yellow]No categories approved for deletion.[/yellow]")
            cli.show_final_stats(db.get_stats())
            return 0

        # Final confirmation
        cli.console.print(f"\n[bold red]⚠ FINAL CONFIRMATION[/bold red]")
        cli.console.print(f"You are about to delete emails from {len(approved)} categories:")
        for cat in approved:
            cat_data = next(c for c in summary if c['category'] == cat)
            cli.console.print(f"  • {cat}: {cat_data['count']} emails")

        final_confirm = cli.console.input("\n[bold]Type 'DELETE' to confirm: [/bold]")

        if final_confirm != 'DELETE':
            cli.console.print("\n[yellow]Deletion cancelled.[/yellow]")
            return 0

        # Phase 3: Execute Deletion
        cli.console.print("\n[bold cyan]Phase 3: Executing Deletion[/bold cyan]")
        cli.console.print("=" * 60)

        deletion_state = agent.run_deletion(decisions)

        # Show results
        final_stats = db.get_stats()
        cli.show_deletion_results(
            deletion_state.get('deletion_results', {}),
            final_stats['approved_size_mb']
        )

        # Final statistics
        cli.show_final_stats(final_stats)

        cli.console.print("\n[bold green]✅ All done![/bold green]")
        cli.console.print("\n[dim]Note: Deleted emails are in trash and can be restored for 30 days.[/dim]")

        # Cleanup
        db.close()

        return 0

    except KeyboardInterrupt:
        cli.console.print("\n\n[yellow]Interrupted by user[/yellow]")
        return 130

    except Exception as e:
        cli.show_error(str(e))
        import traceback
        cli.console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())