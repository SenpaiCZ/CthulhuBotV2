import aiohttp
import re

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

    # 4. Fetch the page to find the RSS URL or Channel ID
    # This handles handles (@user), custom URLs (/c/name), video pages, etc.
    local_session = False
    if session is None:
        session = aiohttp.ClientSession()
        local_session = True

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                text = await response.text()

                # Search for "rssUrl":"..."
                # This is often found in the ytInitialData JSON in the source
                rss_match = re.search(r'"rssUrl":"(https://www\.youtube\.com/feeds/videos\.xml\?channel_id=[^"]+)"', text)
                if rss_match:
                    return rss_match.group(1)

                # Fallback: Search for channelId in meta tags
                # <meta itemprop="channelId" content="UC...">
                # <meta property="og:url" content="https://www.youtube.com/channel/UC...">

                channel_id_meta = re.search(r'<meta itemprop="channelId" content="(UC[\w-]+)">', text)
                if channel_id_meta:
                    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id_meta.group(1)}"

    except Exception as e:
        print(f"Error extracting YouTube RSS from {url}: {e}")
    finally:
        if local_session:
            await session.close()

    return None
