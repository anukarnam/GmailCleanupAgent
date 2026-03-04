"""
CLI interface for Gmail cleanup agent.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from typing import List, Dict
import sys

console = Console()


class CLI:
    """Command-line interface for Gmail cleanup."""

    def __init__(self):
        self.console = console

    def show_welcome(self):
        """Display welcome message."""
        welcome = Panel(
            "[bold cyan]Gmail Cleanup Agent[/bold cyan]\n\n"
            "This tool will help you:\n"
            "1. Fetch emails from your Gmail\n"
            "2. Categorize them using AI\n"
            "3. Review and approve deletions\n"
            "4. Clean up your mailbox safely\n\n"
            "[yellow]⚠ Only metadata is read - no email bodies are accessed[/yellow]",
            title="🧹 Welcome",
            border_style="cyan"
        )
        self.console.print(welcome)
        self.console.print()

    def get_processing_params(self) -> Dict:
        """Get user input for processing parameters."""
        self.console.print("[bold]Configuration:[/bold]")

        max_emails = Prompt.ask(
            "How many emails to process?",
            default="500",
            show_default=True
        )

        batch_size = Prompt.ask(
            "Batch size for categorization?",
            default="50",
            show_default=True
        )

        return {
            'max_emails': int(max_emails),
            'batch_size': int(batch_size)
        }

    def show_category_summary(self, summary: List[Dict], db_stats: Dict):
        """Display categorized emails summary."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold green]Processing Complete![/bold green]\n\n"
            f"Total emails analyzed: {db_stats['categorized']}\n"
            f"Total size: {db_stats['total_size_mb']:.2f} MB",
            title="📊 Summary",
            border_style="green"
        ))

        # Create table
        table = Table(title="\n📋 Categorization Results", box=box.ROUNDED)
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="magenta")
        table.add_column("Size (MB)", justify="right", style="yellow")
        table.add_column("Avg Confidence", justify="right", style="green")
        table.add_column("Date Range", style="blue")

        # Sort by count
        sorted_summary = sorted(summary, key=lambda x: x['count'], reverse=True)

        for cat in sorted_summary:
            size_mb = (cat['total_size'] or 0) / (1024 * 1024)
            confidence = cat['avg_confidence'] or 0

            oldest = cat['oldest_date'][:16] if cat['oldest_date'] else 'N/A'
            newest = cat['newest_date'][:16] if cat['newest_date'] else 'N/A'
            date_range = f"{oldest} to {newest}"

            table.add_row(
                cat['category'],
                str(cat['count']),
                f"{size_mb:.2f}",
                f"{confidence:.2f}",
                date_range
            )

        self.console.print(table)

    def show_sample_emails(self, category: str, emails: List[Dict], limit: int = 5):
        """Show sample emails from a category."""
        self.console.print(f"\n[bold cyan]Sample emails from '{category}':[/bold cyan]")

        for i, email in enumerate(emails[:limit], 1):
            panel = Panel(
                f"[yellow]From:[/yellow] {email['sender'][:50]}\n"
                f"[yellow]Subject:[/yellow] {email['subject'][:60]}\n"
                f"[yellow]Date:[/yellow] {email['date'][:25]}\n"
                f"[dim]{email['snippet'][:100]}...[/dim]",
                title=f"Email {i}",
                border_style="blue",
                box=box.ROUNDED
            )
            self.console.print(panel)

    def get_approval_decisions(self, summary: List[Dict], db) -> Dict:
        """Interactive approval process."""
        self.console.print("\n")
        self.console.print(Panel(
            "[bold yellow]⚠ Review and Approve Deletions[/bold yellow]\n\n"
            "For each category, you can:\n"
            "- Approve deletion (emails will be moved to trash)\n"
            "- Reject (keep the emails)\n"
            "- View samples before deciding",
            title="🔍 Approval Required",
            border_style="yellow"
        ))

        decisions = {}

        # Filter out 'keep' category and sort by count
        categories = [c for c in summary if c['category'] != 'keep']
        categories = sorted(categories, key=lambda x: x['count'], reverse=True)

        for cat_data in categories:
            category = cat_data['category']
            count = cat_data['count']
            size_mb = (cat_data['total_size'] or 0) / (1024 * 1024)

            self.console.print("\n" + "=" * 60)
            self.console.print(
                f"\n[bold cyan]Category:[/bold cyan] {category}\n"
                f"[bold]Count:[/bold] {count} emails\n"
                f"[bold]Size:[/bold] {size_mb:.2f} MB"
            )

            # Ask if user wants to see samples
            see_samples = Confirm.ask("View sample emails?", default=True)

            if see_samples:
                samples = db.get_emails_by_category(category, limit=5)
                self.show_sample_emails(category, samples)

            # Get decision
            decision = Prompt.ask(
                f"\n[bold]Approve deletion of {count} emails in '{category}'?[/bold]",
                choices=["approve", "reject", "skip"],
                default="reject"
            )

            decisions[category] = decision

            if decision == "approve":
                self.console.print(f"[green]✓[/green] Approved for deletion")
            elif decision == "reject":
                self.console.print(f"[red]✗[/red] Will keep these emails")
            else:
                self.console.print(f"[yellow]⊘[/yellow] Skipped")

        return decisions

    def show_deletion_results(self, results: Dict, approved_size_mb: float):
        """Display deletion results."""
        self.console.print("\n")

        if results['success'] > 0:
            panel = Panel(
                f"[bold green]Successfully deleted {results['success']} emails![/bold green]\n\n"
                f"Space freed: ~{approved_size_mb:.2f} MB\n"
                f"Emails moved to trash (can be restored for 30 days)",
                title="✅ Deletion Complete",
                border_style="green"
            )
        else:
            panel = Panel(
                "[bold yellow]No emails were deleted[/bold yellow]\n\n"
                "Either no categories were approved or an error occurred.",
                title="ℹ Info",
                border_style="yellow"
            )

        self.console.print(panel)

        if results['failed'] > 0:
            self.console.print(
                f"\n[bold red]⚠ Warning:[/bold red] Failed to delete {results['failed']} emails"
            )

    def show_final_stats(self, stats: Dict):
        """Show final statistics."""
        self.console.print("\n")

        table = Table(title="📈 Final Statistics", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="magenta")

        table.add_row("Total emails processed", str(stats['total_emails']))
        table.add_row("Emails categorized", str(stats['categorized']))
        table.add_row("Emails deleted", str(stats['deleted']))
        table.add_row("Total size analyzed", f"{stats['total_size_mb']:.2f} MB")

        self.console.print(table)

    def show_error(self, message: str):
        """Display error message."""
        self.console.print(f"\n[bold red]Error:[/bold red] {message}")

    def confirm_exit(self) -> bool:
        """Confirm before exiting."""
        return Confirm.ask("\nProcess complete. Exit?", default=True)