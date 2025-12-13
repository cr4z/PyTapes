# PyTapes

This script automatically populates a specified YouTube playlist with alternating drift and skate videos for use as a screensaver.

## Setup

1. **Get YouTube API credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the YouTube Data API v3
   - Create OAuth 2.0 credentials (Desktop app)
   - Download the credentials and save as `credentials.json` in this directory

2. **Install dependencies**
   ```bash
   pip install google-api-python-client google-auth-oauthlib
   ```

3. **Create a YouTube playlist**
   - Go to YouTube and create a new playlist
   - Copy the playlist ID from the URL (the part after `list=`)

## Usage

Run the script with your playlist ID:

```bash
python pytapes.py --playlist-id YOUR_PLAYLIST_ID
```

On first run, a browser window will open for you to authorize the app. This creates a `token.json` file for future runs.

### Options

- `--playlist-id` (required): Your YouTube playlist ID
- `--drift-q`: Search query for drift videos (default: "drift background")
- `--skate-q`: Search query for skate videos (default: "skate video part")
- `--count`: Number of each type of video (default: 25)

### Example

```bash
python pytapes.py --playlist-id PLzHXJIjQo-47OKrD-1KmjfNPeD4EEaPoJ --count 30
```

This clears your playlist and adds 60 videos (30 drift, 30 skate) in alternating order.
