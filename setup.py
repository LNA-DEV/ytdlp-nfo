from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ytdlp-nfo",
    version="1.0.0",
    author="LNA-DEV",
    author_email="me@lna-dev.net",
    description="Download videos with NFO metadata files for Jellyfin/Kodi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LNA-DEV/ytdlp-nfo",
    py_modules=["main"],
    install_requires=[
        "yt-dlp>=2023.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ytdlp-nfo=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
