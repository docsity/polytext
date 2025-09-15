import yt_dlp

def download_youtube_m4a(url: str, outdir: str = ".", title: str = "test") -> str:
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": f"{outdir}/{title}.%(ext)s",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "0"},
            {"key": "FFmpegMetadata"},
        ],
        "ffmpeg_location": "/Users/marcodelgiudice/opt/anaconda3/bin",  # <-- point here
        "noprogress": True,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return f"{outdir}/{title}.m4a"

url = "https://www.youtube.com/watch?v=HMubfzOyRYU"

print(download_youtube_m4a(url=url, title="audio_8_barbero_0_5_ore"))