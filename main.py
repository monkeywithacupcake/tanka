#!/usr/bin/env python3
"""
Tanka Main Entry Point

Usage:
    python main.py
"""
import time
import subprocess
import sys

def main():

    # Call the downloader
    # default is today and yesterday (to have full yesterday data)
    subprocess.run([sys.executable, "download.py"])
    # 5-second delay
    time.sleep(5)
    # Call analysis
    subprocess.run([sys.executable, "analyze.py"])
    time.sleep(5)
    # Call poster
    subprocess.run([sys.executable, "bsky_post.py","--dryrun"])

if __name__ == "__main__":
    main()
