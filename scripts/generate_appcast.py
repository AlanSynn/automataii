#!/usr/bin/env python3
"""
Generate Sparkle appcast for automatic updates.
This script creates an appcast.xml file for Sparkle auto-updates using GitHub releases.
"""

import os
import sys
import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import subprocess
import requests
import re

def get_file_info(file_path):
    """Get file size and SHA-256 hash."""
    stat = os.stat(file_path)
    size = stat.st_size
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    return size, sha256_hash.hexdigest()

def get_github_releases(repo_owner, repo_name, token=None):
    """Fetch GitHub releases using GitHub API."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    headers = {}
    if token:
        headers['Authorization'] = f"token {token}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching GitHub releases: {e}")
        return []

def create_appcast_from_github(repo_owner, repo_name, output_file="appcast.xml", token=None):
    """Create Sparkle appcast XML file from GitHub releases."""
    
    # Fetch GitHub releases
    releases = get_github_releases(repo_owner, repo_name, token)
    
    # Create RSS root element
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:sparkle", "http://www.andymatuschak.org/xml-namespaces/sparkle")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    
    channel = ET.SubElement(rss, "channel")
    
    # Channel metadata
    ET.SubElement(channel, "title").text = "Automataii Updates"
    ET.SubElement(channel, "link").text = f"https://github.com/{repo_owner}/{repo_name}"
    ET.SubElement(channel, "description").text = "Updates for Automataii application"
    ET.SubElement(channel, "language").text = "en"
    
    # Process each release
    for release in releases:
        if release.get('draft', False) or release.get('prerelease', False):
            continue
            
        tag_name = release.get('tag_name', '')
        version = tag_name.lstrip('v')  # Remove 'v' prefix
        
        # Find DMG asset
        dmg_asset = None
        for asset in release.get('assets', []):
            if asset['name'].endswith('.dmg'):
                dmg_asset = asset
                break
        
        if not dmg_asset:
            continue
            
        # Create item element
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Automataii {version}"
        
        # Use release body as description, or default
        description = release.get('body', f"Update to version {version}")
        ET.SubElement(item, "description").text = f"<![CDATA[{description}]]>"
        
        # Parse publication date
        pub_date = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
        ET.SubElement(item, "pubDate").text = pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Sparkle-specific elements
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", dmg_asset['browser_download_url'])
        enclosure.set("length", str(dmg_asset['size']))
        enclosure.set("type", "application/octet-stream")
        enclosure.set("sparkle:version", version)
        enclosure.set("sparkle:shortVersionString", version)
        
        # Add minimum system version
        ET.SubElement(item, "sparkle:minimumSystemVersion").text = "10.15"
        
        # Add release notes link if available
        if release.get('html_url'):
            ET.SubElement(item, "sparkle:releaseNotesLink").text = release['html_url']
    
    # Write XML file
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    
    output_path = Path(output_file)
    with open(output_path, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding='utf-8')
    
    print(f"Appcast created: {output_path}")
    return output_path

def create_appcast(releases_dir, base_url, output_file="appcast.xml"):
    """Create Sparkle appcast XML file from local files (fallback)."""
    
    # Create RSS root element
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:sparkle", "http://www.andymatuschak.org/xml-namespaces/sparkle")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    
    channel = ET.SubElement(rss, "channel")
    
    # Channel metadata
    ET.SubElement(channel, "title").text = "Automataii Updates"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Updates for Automataii application"
    ET.SubElement(channel, "language").text = "en"
    
    # Find all DMG files in releases directory
    releases_path = Path(releases_dir)
    dmg_files = list(releases_path.glob("*.dmg"))
    
    # Sort by modification time (newest first)
    dmg_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for dmg_file in dmg_files:
        # Extract version from filename (e.g., "Automataii-v1.0.0.dmg" -> "1.0.0")
        filename = dmg_file.stem
        if "-v" in filename:
            version = filename.split("-v")[1]
        else:
            # Fallback: use timestamp
            version = str(int(dmg_file.stat().st_mtime))
        
        # Get file info
        size, sha256 = get_file_info(dmg_file)
        
        # Create item element
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Automataii {version}"
        ET.SubElement(item, "description").text = f"<![CDATA[Update to version {version}]]>"
        ET.SubElement(item, "pubDate").text = datetime.fromtimestamp(
            dmg_file.stat().st_mtime
        ).strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Sparkle-specific elements
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", f"{base_url}/{dmg_file.name}")
        enclosure.set("length", str(size))
        enclosure.set("type", "application/octet-stream")
        enclosure.set("sparkle:version", version)
        enclosure.set("sparkle:shortVersionString", version)
        enclosure.set("sparkle:sha256Sum", sha256)
        
        # Add minimum system version
        ET.SubElement(item, "sparkle:minimumSystemVersion").text = "10.15"
        
        # Check for release notes
        release_notes_file = dmg_file.with_suffix('.html')
        if release_notes_file.exists():
            ET.SubElement(item, "sparkle:releaseNotesLink").text = f"{base_url}/{release_notes_file.name}"
    
    # Write XML file
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    
    output_path = releases_path / output_file
    with open(output_path, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding='utf-8')
    
    print(f"Appcast created: {output_path}")
    return output_path

def main():
    # GitHub releases 방식 (우선)
    if len(sys.argv) >= 3:
        arg1 = sys.argv[1]
        arg2 = sys.argv[2]
        
        # GitHub repo 형식인지 확인 (owner/repo)
        if '/' in arg1 and not os.path.exists(arg1):
            # GitHub API 방식
            repo_parts = arg1.split('/')
            if len(repo_parts) == 2:
                repo_owner, repo_name = repo_parts
                output_file = arg2 if arg2.endswith('.xml') else "appcast.xml"
                token = os.environ.get('GITHUB_TOKEN')
                
                print(f"Generating appcast from GitHub releases for {repo_owner}/{repo_name}")
                create_appcast_from_github(repo_owner, repo_name, output_file, token)
                return
        
        # 로컬 파일 방식 (fallback)
        releases_dir = arg1
        base_url = arg2.rstrip('/')
        
        if not os.path.exists(releases_dir):
            print(f"Error: Releases directory '{releases_dir}' does not exist")
            sys.exit(1)
        
        create_appcast(releases_dir, base_url)
    else:
        print("Usage:")
        print("  GitHub API: python generate_appcast.py owner/repo [output.xml]")
        print("  Local files: python generate_appcast.py <releases_dir> <base_url>")
        print("\nExamples:")
        print("  python generate_appcast.py automataii/automataii appcast.xml")
        print("  python generate_appcast.py releases/ https://github.com/user/repo/releases/download/")
        sys.exit(1)

if __name__ == "__main__":
    main()