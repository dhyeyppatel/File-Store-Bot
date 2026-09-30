# Telegram File Store Bot

A serverless Telegram bot that stores files and messages in a private Telegram channel and generates unique, secure, encrypted links to share or retrieve them.

Built with Python, Vercel Serverless Functions, Telegram Bot API, and MongoDB.

## Features
- **Serverless Architecture**: Deploy directly to Vercel.
- **Upload Sessions**: Upload multiple files, photos, videos, and messages in a single batch.
- **Batch Forwarding**: Create a file collection directly from an existing channel using message links.
- **Storage Channel**: Files are actually stored securely in a private Telegram channel.
- **Secure Links**: Generates random cryptographically secure tokens.
- **MongoDB**: Keeps track of metadata and token hashes (does not store raw tokens).
- **Deep Links**: Easily retrieve files through Telegram deep linking (`https://t.me/Bot?start=token`).
- **Bot Cloning System**: Users can clone the main bot using their own Bot Token. The main bot acts as the host and managers all webhooks automatically.
- **Customizable Clones**: Clone owners get a dedicated control panel to configure settings:
  - **Force Sub**: Require users to join a specific channel before they can retrieve files.
  - **Auto Delete**: Automatically delete files sent to users after a certain time limit. *(Requires setting up a cron job like cron-job.org to ping `https://your-vercel-domain.vercel.app/api?cron=true` every 1 minute)*.
  - **Custom Start Message**: Configure what the bot says when users run `/start`.
  - **Link Shortener Integration**: Force users to pass through shortener services (like earn4link.in) before accessing files, enabling monetization.
  - **Custom Storage Channels**: Clone owners can route their uploads to their own private database channels.
  - **Moderators**: Assign specific users who can upload and create batches.
  - **Stats Tracking**: Track the total number of users and total uploads across the bot.
  - **Public/Private Modes**: Restrict uploads to only admins/moderators (Private) or allow anyone to upload (Public).
- **Global Search**: Search for files (`/search <query>`) directly from the main bot. It will scan uploads across all clone bots and return direct hyperlinks.
- **Inline Menus**: Clean and modern UI using inline buttons instead of bulky reply keyboards.

## Setup

1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure Environment Variables**: Copy `.env.example` to `.env` and fill in the values.
4. **Deploy to Vercel**: Import this project into Vercel and set your environment variables.
5. **Set Webhook**: Just visit `https://your-vercel-domain.vercel.app/api?setup=true` in your browser. This will automatically configure the Telegram webhook and register all bot commands.

### Environment Variables

- `BOT_TOKEN`: Your Telegram Bot API token.
- `MONGO_URI`: MongoDB connection string.
- `DB_NAME`: Database name (e.g., `file_store`).
- `STORAGE_CHAT_ID`: The ID of your private storage channel (e.g., `-100123456789`). Ensure the bot is an admin here!
- `BOT_USERNAME`: The bot's username without `@` (e.g., `MyFileStoreBot`).
- `WEBHOOK_SECRET`: (Optional) A secret token for validating incoming webhooks.

## Usage

- **/start**: Open the inline main menu.
- **/upload**: Start a session to store new files. Send files and click `✅ Done`.
- **/batch**: Create a link from an existing sequence of messages in a channel.
- **/search <query>**: Search for files across the main bot and all clones (Main bot only).
- **/settings**: Toggle media grouping and change the main bot's Public/Private mode (Admins only).
- **/clone**: Start the process to clone the bot.
- **/mybots**: View and configure comprehensive settings for your cloned bots.
