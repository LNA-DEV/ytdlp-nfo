import os
import sys
import json
from datetime import datetime
import yt_dlp
import xml.etree.ElementTree as ET


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
        uid.set("type", webpage_url_domain)
        uid.set("default", "true")
        uid.text = video_id

    if "porn" or "Porn" or "Fetish" or "fetish" in str(extractor):
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


def download_video(url: str):
    ydl_opts = {
        "outtmpl": "%(title)s/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "writeinfojson": True,
        "writethumbnail": True,
        "convert_thumbnails": "jpg",
        "ignoreconfig": True,
        "format": "bv*+ba/best",
        "ignoreerrors": True,  # Continue on download errors
        "no_warnings": False,  # Show warnings so user knows what failed
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            print(f"⚠ Error during download: {e}")
            print("Continuing to process any successfully downloaded items...")

    # Now scan every subfolder created
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
        except Exception as e:
            print(f"⚠ Error processing {folder}: {e}")
            print("Continuing to next item...")


def main():
    if len(sys.argv) < 2:
        print("Usage: ytdlp-nfo <video_url>")
        sys.exit(1)

    link = sys.argv[1]
    download_video(link)


if __name__ == "__main__":
    main()
