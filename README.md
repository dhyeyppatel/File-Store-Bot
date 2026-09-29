# Telegram File Store Bot

A serverless Telegram bot that stores files and messages in a private Telegram channel and generates unique, secure, encrypted links to share or retrieve them.

Built with Python, Vercel Serverless Functions, Telegram Bot API, and MongoDB.

## Features
- **Serverless Architecture**: Deploy directly to Vercel.
- **Upload Sessions**: Upload multiple files, photos, videos, and messages in a single batch.
- **Storage Channel**: Files are actually stored securely in a private Telegram channel.
- **Secure Links**: Generates random cryptographically secure tokens.
- **MongoDB**: Keeps track of metadata and token hashes (does not store raw tokens).
- **Deep Links**: Easily retrieve files through Telegram deep linking (`https://t.me/Bot?start=token`).

## Setup

1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure Environment Variables**: Copy `.env.example` to `.env` and fill in the values.
4. **Deploy to Vercel**: Import this project into Vercel and set your environment variables.
5. **Set Webhook**: Set your bot's webhook to `https://your-vercel-domain.vercel.app/api/webhook`.

### Environment Variables

- `BOT_TOKEN`: Your Telegram Bot API token.
- `MONGO_URI`: MongoDB connection string.
- `DB_NAME`: Database name (e.g., `file_store`).
- `STORAGE_CHAT_ID`: The ID of your private storage channel (e.g., `-100123456789`). Ensure the bot is an admin here!
- `BOT_USERNAME`: The bot's username without `@` (e.g., `MyFileStoreBot`).
- `WEBHOOK_SECRET`: (Optional) A secret token for validating incoming webhooks.

## Usage

Start an upload session by sending `/upload` to the bot. Send any number of files or messages, and click `✅ Done` to finish and generate your secure link.
