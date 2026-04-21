import yt_dlp


def download_youtube_m4a(url: str, outdir: str = ".", title: str = "test") -> str:
    base_opts = {
        "outtmpl": f"{outdir}/{title}.%(ext)s",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "0"},
            {"key": "FFmpegMetadata"},
        ],
        "ffmpeg_location": "/Users/marcodelgiudice/opt/anaconda3/bin",
        "noprogress": True,
        "quiet": True,
        "noplaylist": True,
        "hls_prefer_native": False,
        "extractor_args": {
            "youtube": {
                # Avoid fragile web-only extraction paths when possible.
                "player_client": ["android", "ios", "web"],
            }
        },
    }

    attempt_opts = [
        {
            **base_opts,
            # Prefer direct HTTPS audio first to reduce SABR/HLS failures.
            "format": "bestaudio[ext=m4a][protocol=https]/bestaudio[protocol=https]/bestaudio/best",
        },
        {
            **base_opts,
            # Fallback: let yt-dlp choose any best audio and transcode to m4a.
            "format": "bestaudio/best",
        },
    ]

    last_error = None
    for ydl_opts in attempt_opts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                return f"{outdir}/{title}.m4a"
        except yt_dlp.utils.DownloadError as exc:
            last_error = exc
            continue

    raise last_error if last_error is not None else RuntimeError("Failed to download YouTube audio")


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=5PPyZg2QYYA"
    print(download_youtube_m4a(url=url, title="lezione_società_cinese_70_min"))
