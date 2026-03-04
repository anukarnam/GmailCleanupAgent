"""
Gmail API client for fetching and managing emails.
"""
import os
import pickle
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        creds = None
        token_path = Path(self.credentials_path).parent / 'token.pickle'

        # Load existing credentials
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)

    def get_email_metadata(self, max_results: int = 100, page_token: Optional[str] = None) -> Dict:
        """
        Fetch email metadata (no body content).

        Returns:
            Dict with 'emails' list and 'next_page_token'
        """
        try:
            # List messages
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                pageToken=page_token
            ).execute()

            messages = results.get('messages', [])
            next_page = results.get('nextPageToken')

            emails = []
            for msg in messages:
                # Get message metadata
                email_data = self._get_message_metadata(msg['id'])
                if email_data:
                    emails.append(email_data)

            return {
                'emails': emails,
                'next_page_token': next_page
            }

        except HttpError as error:
            print(f'An error occurred: {error}')
            return {'emails': [], 'next_page_token': None}

    def _get_message_metadata(self, msg_id: str) -> Optional[Dict]:
        """Get metadata for a single message."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            # Extract headers
            headers = {h['name']: h['value'] for h in message['payload']['headers']}

            return {
                'id': message['id'],
                'thread_id': message['threadId'],
                'labels': message.get('labelIds', []),
                'snippet': message.get('snippet', ''),
                'size_bytes': int(message.get('sizeEstimate', 0)),
                'sender': headers.get('From', ''),
                'subject': headers.get('Subject', ''),
                'date': headers.get('Date', ''),
            }

        except HttpError as error:
            print(f'Error fetching message {msg_id}: {error}')
            return None

    def trash_emails(self, email_ids: List[str]) -> Dict:
        """
        Move emails to trash (soft delete).

        Args:
            email_ids: List of email IDs to trash

        Returns:
            Dict with success/failure counts
        """
        success_count = 0
        failed_ids = []

        for email_id in email_ids:
            try:
                self.service.users().messages().trash(
                    userId='me',
                    id=email_id
                ).execute()
                success_count += 1
            except HttpError as error:
                print(f'Error trashing email {email_id}: {error}')
                failed_ids.append(email_id)

        return {
            'success': success_count,
            'failed': len(failed_ids),
            'failed_ids': failed_ids
        }

    def delete_emails_permanently(self, email_ids: List[str]) -> Dict:
        """
        Permanently delete emails (use with caution!).

        Args:
            email_ids: List of email IDs to delete

        Returns:
            Dict with success/failure counts
        """
        success_count = 0
        failed_ids = []

        for email_id in email_ids:
            try:
                self.service.users().messages().delete(
                    userId='me',
                    id=email_id
                ).execute()
                success_count += 1
            except HttpError as error:
                print(f'Error deleting email {email_id}: {error}')
                failed_ids.append(email_id)

        return {
            'success': success_count,
            'failed': len(failed_ids),
            'failed_ids': failed_ids
        }

    def get_mailbox_size(self) -> Dict:
        """Get mailbox size information."""
        try:
            profile = self.service.users().getProfile(userId='me').execute()

            return {
                'email_address': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal'),
                'threads_total': profile.get('threadsTotal'),
                'history_id': profile.get('historyId')
            }

        except HttpError as error:
            print(f'Error getting mailbox size: {error}')
            return {}