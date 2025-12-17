import argparse, os, sys, logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.FileHandler('pytapes.log', mode='a')
handler.setFormatter(logging.Formatter('[%(asctime)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(handler)

blocked_channels = ["eletor"]
skipped_keywords = ["phonk", "wallpaper", "instrumentals"]
maximum = 25

SCOPES = ["https://www.googleapis.com/auth/youtube"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)


def search(youtube, query, blocked_channels=None, skipped_keywords=None):
    if blocked_channels is None:
        blocked_channels = []
    if skipped_keywords is None:
        skipped_keywords = []

    logging.info(f"Searching for '{query}' (max 50 results, per API defaults)")
    # Fetch more results to account for filtering
    resp = (
        youtube.search()
        .list(part="snippet", q=query, type="video", order="relevance", maxResults=50)
        .execute()
    )

    # Collect video IDs to check durations
    video_ids = [it["id"]["videoId"] for it in resp.get("items", [])]

    # Get video details including duration and category
    videos_resp = youtube.videos().list(part="snippet,contentDetails", id=",".join(video_ids)).execute()

    # Filter videos
    results = []
    for video in videos_resp.get("items", []):
        video_id = video["id"]
        title = video["snippet"].get("title", "").lower()
        description = video["snippet"].get("description", "").lower()
        channel_name = video["snippet"].get("channelTitle", "")
        duration = video["contentDetails"].get("duration", "")

        # Check if channel is blocked
        if any(blocked in channel_name.lower() for blocked in blocked_channels):
            logging.info(f"Skipping video {video_id} from blocked channel: {channel_name}")
            continue

        # Check for skipped keywords in title or description
        if any(keyword.lower() in title or keyword.lower() in description for keyword in skipped_keywords):
            logging.info(f"Skipping video {video_id} - contains blocked keyword: {title[:50]}")
            continue

        # Skip Shorts (duration <= 60 seconds)
        # Parse ISO 8601 duration (PT#M#S format)
        duration_seconds = parse_duration(duration)
        if duration_seconds < 120:
            logging.info(f"Skipping video {video_id} - too short ({duration_seconds}s): {title[:50]}")
            continue

        results.append(video_id)

    logging.info(f"Found {len(results)} videos (after filtering)")
    return results


def parse_duration(duration_str):
    """Parse ISO 8601 duration to seconds (e.g., PT1M30S -> 90)"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def list_items(youtube, playlist_id):
    out, page = [], None
    while True:
        resp = (
            youtube.playlistItems()
            .list(part="id", playlistId=playlist_id, maxResults=50, pageToken=page)
            .execute()
        )
        out.extend([it["id"] for it in resp.get("items", [])])
        page = resp.get("nextPageToken")
        if not page:
            break
    return out


def clear_playlist(youtube, playlist_id):
    logging.info(f"Clearing playlist {playlist_id}")
    items = list_items(youtube, playlist_id)
    for item_id in items:
        youtube.playlistItems().delete(id=item_id).execute()
    logging.info(f"Cleared {len(items)} items")


def insert(youtube, playlist_id, video_id):
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()


def update_playlist(youtube, playlist_id, drift_q, skate_q, n=50):
    logging.info("Starting playlist update")
    # grab top N of each
    drift_ids = search(youtube, drift_q, blocked_channels, skipped_keywords)
    skate_ids = search(youtube, skate_q, blocked_channels, skipped_keywords)
    # zip them
    merged = []
    for d, s in zip(drift_ids, skate_ids):
        merged.append(s)
        merged.append(d)
    # wipe playlist
    clear_playlist(youtube, playlist_id)
    # insert in order
    logging.info(f"Inserting {len(merged)} videos")
    for vid in merged:
        insert(youtube, playlist_id, vid)
    logging.info(f"Successfully inserted {len(merged)} videos")


def main():
    ap = argparse.ArgumentParser(
        description="Clear + repopulate a playlist with 25 drift + 25 skate videos."
    )
    ap.add_argument("--playlist-id", required=True)
    ap.add_argument("--drift-q", default="drift background")
    ap.add_argument("--skate-q", default="skate video part")
    ap.add_argument("--count", type=int, default=25)
    args = ap.parse_args()

    yt = get_service()
    update_playlist(yt, args.playlist_id, args.drift_q, args.skate_q, n=args.count)


if __name__ == "__main__":
    try:
        main()
        logging.info("Playlist update completed successfully")
    except HttpError as e:
        logging.error(f"API error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
