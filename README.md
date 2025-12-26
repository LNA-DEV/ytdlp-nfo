# ytdlp-nfo

Download videos using yt-dlp and automatically create NFO metadata files compatible with Jellyfin and Kodi media servers.

## Features

- Downloads videos using yt-dlp
- Automatically creates movie.nfo files with metadata
- Downloads and converts thumbnails to folder.jpg
- Supports playlists
- Compatible with Jellyfin and Kodi

## Installation

### Using Homebrew (macOS/Linux)

First, tap the repository:

```bash
brew tap LNA-DEV/homebrew-tap
```

Then install:

```bash
brew install ytdlp-nfo
```

### From Source

```bash
git clone https://github.com/LNA-DEV/ytdlp-nfo.git
cd ytdlp-nfo
pip install .
```

## Usage

```bash
ytdlp-nfo <video_url>
```

## License

MIT
