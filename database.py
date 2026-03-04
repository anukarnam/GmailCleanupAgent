"""
Database module for Gmail cleanup agent.
Handles email metadata storage and state management.
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class EmailDatabase:
    """Manages SQLite database for email metadata and processing state."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Emails table - stores metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                subject TEXT,
                sender TEXT,
                date TEXT,
                size_bytes INTEGER,
                labels TEXT,
                snippet TEXT,
                category TEXT,
                confidence_score REAL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Categories table - stores category definitions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                name TEXT PRIMARY KEY,
                description TEXT,
                action TEXT DEFAULT 'review',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Processing log - audit trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        # User decisions - tracks approval/rejection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_decisions (
                category TEXT PRIMARY KEY,
                decision TEXT,
                email_count INTEGER,
                decided_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        self._init_categories()

    def _init_categories(self):
        """Initialize default categories."""
        default_categories = [
            ("newsletters", "Marketing emails and newsletters"),
            ("promotions", "Promotional and advertising emails"),
            ("social_notifications", "Social media notifications"),
            ("old_conversations", "Email threads older than 6 months"),
            ("automated_reports", "Automated system reports and notifications"),
            ("receipts", "Purchase receipts and confirmations"),
            ("spam_likely", "Likely spam or unwanted emails"),
            ("keep", "Important emails to keep"),
        ]

        cursor = self.conn.cursor()
        cursor.executemany(
            "INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)",
            default_categories
        )
        self.conn.commit()

    def insert_emails(self, emails: List[Dict]):
        """Insert or update email records."""
        cursor = self.conn.cursor()

        for email in emails:
            cursor.execute("""
                INSERT OR REPLACE INTO emails 
                (id, thread_id, subject, sender, date, size_bytes, labels, snippet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email['id'],
                email.get('thread_id'),
                email.get('subject', ''),
                email.get('sender', ''),
                email.get('date', ''),
                email.get('size_bytes', 0),
                ','.join(email.get('labels', [])),
                email.get('snippet', '')
            ))

        self.conn.commit()
        return len(emails)

    def update_email_category(self, email_id: str, category: str, confidence: float):
        """Update email category and confidence score."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE emails 
            SET category = ?, confidence_score = ?, status = 'categorized'
            WHERE id = ?
        """, (category, confidence, email_id))
        self.conn.commit()

    def get_uncategorized_emails(self, limit: int = 50) -> List[Dict]:
        """Get emails that haven't been categorized yet."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM emails 
            WHERE category IS NULL 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_category_summary(self) -> List[Dict]:
        """Get summary of emails by category."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                category,
                COUNT(*) as count,
                SUM(size_bytes) as total_size,
                AVG(confidence_score) as avg_confidence,
                MIN(date) as oldest_date,
                MAX(date) as newest_date
            FROM emails 
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_emails_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Get sample emails from a category."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM emails 
            WHERE category = ? 
            ORDER BY date DESC
            LIMIT ?
        """, (category, limit))
        return [dict(row) for row in cursor.fetchall()]

    def save_user_decision(self, category: str, decision: str, email_count: int):
        """Save user's approval/rejection decision."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_decisions 
            (category, decision, email_count)
            VALUES (?, ?, ?)
        """, (category, decision, email_count))

        # Update email status
        if decision == 'approve':
            cursor.execute("""
                UPDATE emails 
                SET status = 'approved_for_deletion'
                WHERE category = ?
            """, (category,))

        self.conn.commit()

    def get_approved_emails(self) -> List[str]:
        """Get list of email IDs approved for deletion."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM emails 
            WHERE status = 'approved_for_deletion'
        """)
        return [row['id'] for row in cursor.fetchall()]

    def mark_emails_deleted(self, email_ids: List[str]):
        """Mark emails as deleted."""
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(email_ids))
        cursor.execute(f"""
            UPDATE emails 
            SET status = 'deleted'
            WHERE id IN ({placeholders})
        """, email_ids)
        self.conn.commit()

    def log_action(self, email_id: str, action: str, details: str = ""):
        """Log an action for audit trail."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO processing_log (email_id, action, details)
            VALUES (?, ?, ?)
        """, (email_id, action, details))
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Get overall statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM emails")
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as categorized FROM emails WHERE category IS NOT NULL")
        categorized = cursor.fetchone()['categorized']

        cursor.execute("SELECT COUNT(*) as approved FROM emails WHERE status = 'approved_for_deletion'")
        approved = cursor.fetchone()['approved']

        cursor.execute("SELECT COUNT(*) as deleted FROM emails WHERE status = 'deleted'")
        deleted = cursor.fetchone()['deleted']

        cursor.execute("SELECT SUM(size_bytes) as total_size FROM emails")
        total_size = cursor.fetchone()['total_size'] or 0

        cursor.execute("SELECT SUM(size_bytes) as approved_size FROM emails WHERE status = 'approved_for_deletion'")
        approved_size = cursor.fetchone()['approved_size'] or 0

        return {
            'total_emails': total,
            'categorized': categorized,
            'approved_for_deletion': approved,
            'deleted': deleted,
            'total_size_mb': total_size / (1024 * 1024),
            'approved_size_mb': approved_size / (1024 * 1024)
        }

    def close(self):
        """Close database connection."""
        self.conn.close()