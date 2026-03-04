# Quick Start Guide 🚀

Get your Gmail Cleanup Agent running in 5 minutes!

## Step 1: Install Dependencies (1 min)

```bash
cd gmail_cleanup_agent
pip install -r requirements.txt
```

## Step 2: Set Up Gmail API (2 mins)

1. Visit: https://console.cloud.google.com/apis/credentials
2. Create project → Enable Gmail API
3. Create OAuth 2.0 Client ID (Desktop app)
4. Download JSON → Save as `config/credentials.json`

## Step 3: Set Up Anthropic API (1 min)

1. Visit: https://console.anthropic.com/
2. Get API key
3. Copy `.env.example` to `.env`
4. Add your API key to `.env`

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
```

## Step 4: Run! (1 min)

```bash
python main.py
```

First run will open a browser for Gmail authorization. Grant permissions.

## That's It!

Follow the interactive prompts:
1. Choose how many emails to process
2. Wait for categorization
3. Review results
4. Approve deletions
5. Done! ✅

## Quick Tips

- **Start small**: Process 100 emails first to test
- **Review samples**: Always check sample emails before approving
- **Safe deletion**: Emails go to trash (recoverable for 30 days)
- **Type 'DELETE'**: Final confirmation prevents accidents

## Need Help?

Check `README.md` for detailed documentation!