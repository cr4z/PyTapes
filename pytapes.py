import argparse, os, sys, logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', filename='pytapes.log')

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


def search(youtube, query, count):
    logging.info(f"Searching for '{query}' (max {count} results)")
    resp = (
        youtube.search()
        .list(part="id", q=query, type="video", order="relevance", maxResults=count)
        .execute()
    )
    results = [it["id"]["videoId"] for it in resp.get("items", [])]
    logging.info(f"Found {len(results)} videos")
    return results


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


def update_playlist(youtube, playlist_id, drift_q, skate_q, n=25):
    logging.info("Starting playlist update")
    # grab top N of each
    drift_ids = search(youtube, drift_q, n)
    skate_ids = search(youtube, skate_q, n)
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
