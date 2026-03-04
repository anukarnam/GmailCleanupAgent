"""
Email categorization using OCI Cohere model.
"""
from langchain_community.chat_models.oci_generative_ai import ChatOCIGenAI
from typing import Dict, List
import json


class EmailCategorizer:
    """Categorizes emails using OCI Cohere model."""

    def __init__(self, compartment_id: str, service_endpoint: str, auth_profile: str = "DEFAULT"):
        """
        Initialize OCI Cohere client.

        Args:
            compartment_id: OCI compartment OCID
            service_endpoint: OCI GenAI service endpoint
            auth_profile: OCI config profile name (default: "DEFAULT")
        """
        self.client = ChatOCIGenAI(
            model_id="cohere.command-r-plus-08-2024",
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            model_kwargs={"temperature": 0.7, "max_tokens": 4000},
            auth_profile=auth_profile
        )

    def categorize_batch(self, emails: List[Dict]) -> List[Dict]:
        """
        Categorize a batch of emails using OCI Cohere.

        Args:
            emails: List of email metadata dicts

        Returns:
            List of dicts with email_id, category, confidence, reasoning
        """
        if not emails:
            return []

        # Prepare batch prompt
        email_list = []
        for i, email in enumerate(emails):
            email_list.append(f"""
Email {i+1}:
ID: {email['id']}
From: {email['sender']}ple emails fro
Subject: {email['subject']}
Date: {email['date']}
Labels: {email.get('labels', [])}
Snippet: {email['snippet'][:200]}
""")

#- newsletters: Marketing emails and newsletters
# - promotions: Promotional and advertising emails
# - social_notifications: Social media notifications (Facebook, LinkedIn, Twitter, etc.)
# - automated_reports: Automated system reports, CI/CD notifications, monitoring alerts
# - receipts: Purchase receipts and order confirmations
# - spam_likely: Likely spam or unwanted emails
        prompt = f"""You are an email categorization assistant. Analyze the following emails and categorize each one.

Available categories:
- social_notifications: Get all Instagram mails first of all
- old_conversations: Personal/work conversations (check date - if older than 6 months)
- keep: Important emails that should be kept (personal correspondence, important work emails, financial documents)

Emails to analyze:
{chr(10).join(email_list)}

For each email, respond with a JSON array where each object has:
- email_id: The email ID
- category: One of the categories above
- confidence: Float between 0 and 1
- reasoning: Brief explanation (1 sentence)

Important: Be conservative with categorization. When in doubt, use "keep". Look for clear signals like:
- Unsubscribe links → newsletters/promotions
- "no-reply@" addresses → automated_reports/receipts
- Social media domains → social_notifications
- Old dates → old_conversations (if conversational)

Return ONLY the JSON array, no other text or markdown formatting.
"""

        try:
            # Invoke the OCI Cohere model
            message = self.client.invoke(prompt)

            # Extract content from AIMessage
            response_text = message.content.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            # Parse JSON response
            results = json.loads(response_text)
            return results

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print(f"Response was: {response_text[:200]}...")
            # Return default "keep" for all emails on error
            return [
                {
                    'email_id': email['id'],
                    'category': 'keep',
                    'confidence': 0.5,
                    'reasoning': 'JSON parsing error - defaulting to keep for safety'
                }
                for email in emails
            ]

        except Exception as e:
            print(f"Error categorizing emails: {e}")
            # Return default "keep" for all emails on error
            return [
                {
                    'email_id': email['id'],
                    'category': 'keep',
                    'confidence': 0.5,
                    'reasoning': 'Error during categorization - defaulting to keep'
                }
                for email in emails
            ]

    def categorize_single(self, email: Dict) -> Dict:
        """Categorize a single email (wrapper for batch)."""
        results = self.categorize_batch([email])
        return results[0] if results else {
            'email_id': email['id'],
            'category': 'keep',
            'confidence': 0.5,
            'reasoning': 'Error during categorization'
        }