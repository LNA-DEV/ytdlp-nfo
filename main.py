import os
import sys
import json
from datetime import datetime
import yt_dlp
import yt_dlp.version
import xml.etree.ElementTree as ET

__version__ = "1.1.4"


def make_safe_name(name: str) -> str:
    # Remove characters that are invalid on common filesystems
    return "".join(c for c in name if c not in r'<>:"/\|?*').strip() or "video"


def get_video_info(url: str) -> dict:
    """Use yt-dlp to fetch metadata without downloading the video."""
    ydl_opts_info = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreconfig": True,              
        "format": "bv*+ba/best",
    }
    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        return ydl.extract_info(url, download=False)


def discover_audio_formats(info: dict) -> dict[tuple, str]:
    """Find best audio format ID for each (language, channels) combo.
    Returns {(language, channels): format_id}. Keeps both surround and stereo per language."""
    best = {}  # (lang, channels) -> (format_id, abr)
    for f in info.get("formats") or []:
        lang = f.get("language")
        fid = f.get("format_id")
        if not lang or not fid:
            continue
        if f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none":
            channels = f.get("audio_channels") or 2
            abr = f.get("abr") or 0
            key = (lang, channels)
            if key not in best or abr > best[key][1]:
                best[key] = (fid, abr)
    return {k: fid for k, (fid, _) in best.items()}


def format_upload_date(upload_date: str):
    """
    Convert yt-dlp's YYYYMMDD upload_date to (year, YYYY-MM-DD).
    Returns (None, None) if invalid/missing.
    """
    if not upload_date:
        return None, None
    try:
        dt = datetime.strptime(upload_date, "%Y%m%d")
        return dt.year, dt.strftime("%Y-%m-%d")
    except Exception:
        return None, None


def create_nfo_from_json(json_path: str, nfo_path: str):
    """Convert yt-dlp info JSON into a Jellyfin/Kodi-style NFO (movie) file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title") or data.get("fulltitle") or "Unknown Title"
    original_title = data.get("fulltitle") or title
    plot = data.get("description") or ""
    uploader = data.get("uploader") or data.get("channel") or ""
    tags = data.get("tags") or []
    categories = data.get("categories") or []
    upload_date = data.get("upload_date")
    video_id = data.get("id") or ""
    webpage_url = data.get("webpage_url") or ""
    duration = data.get("duration")  # seconds
    extractor = data.get("extractor")
    age_limit = data.get("age_limit")
    webpage_url_domain = data.get("webpage_url_domain")

    year, premiered = format_upload_date(upload_date)

    # Root element
    movie = ET.Element("movie")

    # Basic fields
    ET.SubElement(movie, "title").text = title
    ET.SubElement(movie, "originaltitle").text = original_title

    if plot:
        ET.SubElement(movie, "plot").text = plot
        ET.SubElement(movie, "outline").text = plot

    if premiered:
        ET.SubElement(movie, "premiered").text = premiered
    if year:
        ET.SubElement(movie, "year").text = str(year)

    if uploader:
        actor = ET.SubElement(movie, "actor")
        ET.SubElement(actor, "name").text = uploader
        ET.SubElement(actor, "type").text = "Actor"

    if duration:
        minutes = round(duration / 60)
        ET.SubElement(movie, "runtime").text = str(minutes)

    for tag in tags:
        ET.SubElement(movie, "tag").text = str(tag)

    for category in categories:
        ET.SubElement(movie, "genre").text = str(category)

    if video_id:
        uid = ET.SubElement(movie, "uniqueid")
        uid.set("type", webpage_url_domain or "unknown")
        uid.set("default", "true")
        uid.text = video_id

    extractor_lower = str(extractor).lower()
    if any(kw in extractor_lower for kw in ("porn", "fetish")):
        ET.SubElement(movie, "mpaa").text = "XXX"
    elif age_limit:
        ET.SubElement(movie, "mpaa").text = str(age_limit)
        
    if webpage_url:
        ET.SubElement(movie, "url").text = webpage_url

    # Pretty-print XML
    def indent(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for e in elem:
                indent(e, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent(movie)

    tree = ET.ElementTree(movie)
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)


def _flatten_entries(info: dict) -> list[dict]:
    """Recursively flatten nested playlists into individual video entries."""
    if "entries" not in info:
        return [info]
    result = []
    for entry in info.get("entries") or []:
        if entry is None:
            continue
        result.extend(_flatten_entries(entry))
    return result


def _execute_download(url: str, ydl_opts: dict) -> tuple[int, bool]:
    """Run yt-dlp download and post-process results. Returns (processed_count, had_errors)."""
    had_errors = False
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            retcode = ydl.download([url])
            if retcode != 0:
                had_errors = True
        except Exception as e:
            print(f"⚠ Error during download: {e}")
            print("Continuing to process any successfully downloaded items...")
            had_errors = True

    # Now scan every subfolder created
    processed = 0
    for folder, subfolders, files in os.walk("."):
        info_files = [f for f in files if f.endswith(".info.json")]
        if not info_files:
            continue

        try:
            info_path = os.path.join(folder, info_files[0])
            nfo_path = os.path.join(folder, "movie.nfo")

            create_nfo_from_json(info_path, nfo_path)
            os.remove(info_path)

            # Move thumbnail → folder.jpg
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    old = os.path.join(folder, f)
                    new = os.path.join(folder, "folder.jpg")
                    os.replace(old, new)
                    break

            print("✔ Processed:", folder)
            processed += 1
        except Exception as e:
            print(f"⚠ Error processing {folder}: {e}")
            print("Continuing to next item...")

    return processed, had_errors


def download_video(url: str) -> tuple[int, bool]:
    container = os.environ.get("YTDLP_NFO_FORMAT", "mkv")
    all_audio = os.environ.get("YTDLP_NFO_ALL_AUDIO", "true").lower() == "true"
    subtitles = os.environ.get("YTDLP_NFO_SUBTITLES", "true").lower() == "true"

    base_opts = {
        "outtmpl": "%(playlist_title&{}/|)s%(title)s/%(title)s.%(ext)s",
        "merge_output_format": container,
        "writeinfojson": True,
        "writethumbnail": True,
        "convert_thumbnails": "jpg",
        "ignoreconfig": True,
        "ignoreerrors": True,
        "no_warnings": False,
        "download_archive": ".ytdlp-archive.txt",
        "fragment_retries": 10,
        "skip_unavailable_fragments": False,
    }
    if subtitles:
        base_opts["writesubtitles"] = True
        base_opts["subtitleslangs"] = ["all"]

    if not all_audio:
        # Simple path: single audio, download everything in one pass
        base_opts["format"] = "bv*+ba/best"
        return _execute_download(url, base_opts)

    # All-audio path: extract info first, then download per-video with tailored format
    try:
        with yt_dlp.YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True, "ignoreconfig": True, "ignoreerrors": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        # Discovery failed, fall back to single-audio download
        print("⚠ Audio language discovery failed, falling back to single audio")
        base_opts["format"] = "bv*+ba/best"
        return _execute_download(url, base_opts)

    entries = _flatten_entries(info)
    playlist_title = make_safe_name(info.get("title") or "") if "entries" in info else None

    had_errors = False
    total_processed = 0
    for entry in entries:
        if entry is None:
            continue
        entry_url = entry.get("webpage_url") or entry.get("url") or entry.get("id")
        if not entry_url:
            continue

        entry_title = make_safe_name(entry.get("title") or entry.get("fulltitle") or "video")

        # Playlist entries lack format info — extract individually
        if not entry.get("formats"):
            try:
                with yt_dlp.YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True, "ignoreconfig": True, "ignoreerrors": True}) as ydl:
                    entry_info = ydl.extract_info(entry_url, download=False)
                if entry_info:
                    entry = entry_info
            except Exception:
                pass

        lang_formats = discover_audio_formats(entry)
        if len(lang_formats) > 1:
            audio_ids = "+".join(lang_formats.values())
            fmt = f"bv+{audio_ids}/bv*+ba/best"
            labels = [f"{lang} ({ch}ch)" for lang, ch in lang_formats.keys()]
            print(f"Found {len(lang_formats)} audio tracks for {entry_title}: {', '.join(labels)}")
        else:
            fmt = "bv*+ba/best"

        opts = {
            **base_opts,
            "format": fmt,
            "allow_multiple_audio_streams": len(lang_formats) > 1,
            "outtmpl": f"{playlist_title}/{entry_title}/{entry_title}.%(ext)s" if playlist_title else f"{entry_title}/{entry_title}.%(ext)s",
        }
        processed, errors = _execute_download(entry_url, opts)
        total_processed += processed
        if errors:
            had_errors = True

    return total_processed, had_errors


def main():
    if len(sys.argv) < 2:
        print("Usage: ytdlp-nfo <video_url>")
        return 1

    if sys.argv[1] in ("--version", "-v"):
        print(f"ytdlp-nfo {__version__}")
        print(f"yt-dlp    {yt_dlp.version.__version__}")
        return 0

    link = sys.argv[1]
    processed, had_errors = download_video(link)
    if processed == 0 and had_errors:
        print("✘ No items were successfully processed")
        return 1
    if processed == 0:
        print("✔ All items already in archive")
        return 0
    if had_errors:
        print(f"⚠ {processed} item(s) processed, but some items failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
