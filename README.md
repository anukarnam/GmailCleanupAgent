# Gmail Cleanup Agent 🧹

An intelligent agentic framework that helps you clean up your Gmail inbox by:
- Fetching emails metadata (no body content read)
- Categorizing them using Claude AI
- Presenting organized results for review
- Safely deleting approved emails

Built with **LangGraph** for orchestration, **Claude API** for intelligent categorization, and **SQLite** for state management.

## Features

✨ **Intelligent Categorization**: Uses Claude AI to categorize emails into:
- Newsletters
- Promotions
- Social notifications
- Old conversations
- Automated reports
- Receipts
- Spam
- Keep (important emails)

🔒 **Privacy First**: Only reads email metadata (sender, subject, date) - never the body

🎯 **User Control**: Interactive CLI approval process before any deletions

💾 **State Management**: SQLite tracks all operations with audit trail

🔄 **LangGraph Workflow**: Structured agent workflow with checkpointing

## Architecture

```
┌─────────────┐
│ Gmail API   │  Fetch metadata
└──────┬──────┘
       │
┌──────▼──────┐
│  Database   │  Store & track
└──────┬──────┘
       │
┌──────▼──────┐
│ Claude AI   │  Categorize
└──────┬──────┘
       │
┌──────▼──────┐
│  LangGraph  │  Orchestrate
│   Agent     │
└──────┬──────┘
       │
┌──────▼──────┐
│  CLI        │  User approval
└──────┬──────┘
       │
┌──────▼──────┐
│ Execution   │  Delete emails
└─────────────┘
```

## Prerequisites

1. **Python 3.9+**
2. **Google Cloud Project** with Gmail API enabled
3. **Anthropic API Key**

## Setup Instructions

### 1. Install Dependencies

```bash
cd gmail_cleanup_agent
pip install -r requirements.txt
```

### 2. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"
4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app"
   - Download the JSON file
   - Save it as `config/credentials.json`

### 3. Get Anthropic API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or sign in
3. Generate an API key
4. Copy the key

### 4. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=your_api_key_here
```

### 5. Run the Agent

```bash
python main.py
```

## Usage

### First Run

On the first run, you'll be prompted to authorize the application:

1. A browser window will open
2. Sign in to your Google account
3. Grant the requested permissions
4. The token will be saved for future use

### Workflow

**Step 1: Configuration**
```
How many emails to process? [500]: 500
Batch size for categorization? [50]: 50
```

**Step 2: Fetching & Categorization**
- Emails are fetched from Gmail
- Stored in local SQLite database
- Categorized using Claude AI
- Progress is displayed in real-time

**Step 3: Review Results**
- View category summary (count, size, confidence)
- See sample emails from each category
- Approve or reject deletions per category

**Step 4: Execution**
- Final confirmation required
- Approved emails moved to trash
- Audit trail maintained in database

## Safety Features

🛡️ **Multiple Safety Layers:**

1. **Soft Delete**: Emails moved to trash (not permanently deleted)
2. **30-Day Recovery**: Gmail keeps trashed emails for 30 days
3. **Conservative Categorization**: When in doubt, emails are marked as "keep"
4. **Sample Preview**: Review emails before approving deletion
5. **Final Confirmation**: Type 'DELETE' to confirm
6. **Audit Trail**: All actions logged in database

## Configuration Options

Edit `.env` to customize:

```bash
# Maximum emails to process per run
MAX_EMAILS_PER_RUN=500

# Batch size for Claude API calls
BATCH_SIZE=50

# Database location
DATABASE_PATH=data/gmail_cleanup.db

# Gmail credentials path
GMAIL_CREDENTIALS_PATH=config/credentials.json
```

## Database Schema

The SQLite database maintains:

- **emails**: Email metadata and categorization
- **categories**: Category definitions
- **processing_log**: Audit trail of all actions
- **user_decisions**: Record of approval decisions

View database:
```bash
sqlite3 data/gmail_cleanup.db
.tables
.schema
```

## Extending the Agent

### Adding New Categories

Edit `categorizer.py` and add to the category list:

```python
#- your_category: Description of category
```

Also update the database schema in `database.py`.

### Custom Categorization Logic

Modify the prompt in `categorizer.py` to adjust categorization behavior.

### Adding Analysis Steps

Extend the LangGraph workflow in `agent.py`:

```python
#workflow.add_node("your_step", your_function)
#workflow.add_edge("previous_step", "your_step")
```

## Cost Estimation

**Anthropic API** (Claude Sonnet 4):
- ~500 emails = ~50 API calls (batch of 10 emails each)
- Cost: ~$0.15-0.30 per 500 emails

**Gmail API**: Free (within quotas)

## Troubleshooting

### Issue: "No module named 'google'"

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Issue: "Credentials not found"

Ensure `config/credentials.json` exists with your OAuth credentials from Google Cloud Console.

### Issue: "ANTHROPIC_API_KEY not set"

Check `.env` file and ensure API key is set correctly.

### Issue: Token expired

Delete `config/token.pickle` and re-run to re-authenticate.

## Project Structure

```
gmail_cleanup_agent/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── README.md              # This file
├── config/
│   └── credentials.json   # Gmail OAuth (you create)
├── data/
│   └── gmail_cleanup.db   # SQLite database (auto-created)
└──
    ├── __init__.py
    ├── agent.py           # LangGraph workflow
    ├── gmail_client.py    # Gmail API client
    ├── categorizer.py     # Claude AI categorization
    ├── database.py        # SQLite operations
    └── cli.py             # Terminal interface
```

## Limitations

- Only processes metadata (no email body content)
- Batch size limited to prevent API rate limits
- Requires manual OAuth flow for first-time setup
- Gmail API quotas apply (10,000 quota units/day)

## Future Enhancements

- [ ] Web UI dashboard
- [ ] Scheduling/automation
- [ ] More granular categories
- [ ] Attachment analysis
- [ ] Batch unsubscribe feature
- [ ] Gmail filters creation
- [ ] Statistics dashboard

## License

MIT License - Feel free to use and modify!

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the code comments
3. Open an issue on GitHub

---

**⚠️ Important**: Always review before approving deletions. While emails go to trash (recoverable for 30 days), be careful with your data!
