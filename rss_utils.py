import re
import asyncio
import yt_dlp

async def get_youtube_rss_url(url, session=None):
    """
    Analyzes a URL and returns the YouTube RSS Feed URL if it's a YouTube channel/video link.
    Returns None if no YouTube RSS feed could be determined.
    """

    # 1. Check if it's already a YouTube RSS URL
    if "youtube.com/feeds/videos.xml?channel_id=" in url:
        return url

    # 2. Check if it's a YouTube URL
    if "youtube.com" not in url and "youtu.be" not in url:
        return None

    # 3. Try to extract Channel ID from URL directly (fast path)
    # Matches /channel/UCxxxxxxxx
    channel_id_match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
    if channel_id_match:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id_match.group(1)}"

    # 4. Use yt-dlp to find channel ID (Robust method)
    def fetch_channel_id_with_ytdlp(target_url):
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'dump_single_json': True,
            'playlist_items': '0', # specific optimization to not fetch videos
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(target_url, download=False)
                # info might be the channel info directly or a playlist
                return info.get('channel_id') or info.get('id')
            except Exception as e:
                # print(f"yt-dlp error: {e}")
                return None

    try:
        channel_id = await asyncio.to_thread(fetch_channel_id_with_ytdlp, url)
        if channel_id and channel_id.startswith("UC"):
             return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    except Exception as e:
        print(f"Error extracting YouTube RSS with yt-dlp from {url}: {e}")

    return None
