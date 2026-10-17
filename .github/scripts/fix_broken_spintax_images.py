#!/usr/bin/env python3
"""Canonical Engine: Fix Broken Spintax and Upload-Prefixed Images in HTML.

Resolves broken image URLs caused by unexpanded spintax (e.g. pipe-delimited
lists of hotlinked image URLs from Page Generator Pro or theme templates)
or erroneous WordPress upload directory prefixes prepended to external URLs:
1. Strips erroneous '/wp-content/uploads/' or 'https?://.../wp-content/uploads/'
   prefixes prepended to external 'http(s)://' URLs.
2. Evaluates unexpanded image spintax (pipe-delimited '|' or '%7C' lists of image URLs)
   and selects one random image URL per page (seeded deterministically by file path).
3. Synchronizes Schema.org ImageObject (@id, url, primaryImageOfPage, image) and
   <img> tags to reference the same chosen image URL on the page.
4. Removes artificial width="1" height="1" dimensions on wp-post-image tags caused
   by failed local file resolution in WordPress.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Tuple


def resolve_broken_images_in_html(content: str, filepath: str) -> Tuple[str, int]:
    """Resolves broken upload prefixes and selects one random image from spintax lists.

    Protects Google Fonts (fonts.googleapis.com, fonts.gstatic.com) and stylesheets from
    accidental truncation, requires multi-candidate HTTP lists for spintax, and auto-heals
    any previously truncated astra-google-fonts-css tags.
    """
    changes = 0

    # Auto-heal any truncated Google Fonts stylesheets from previous defective runs
    def heal_corrupted_fonts(text: str) -> Tuple[str, int]:
        h_count = 0
        # 1. Truncated Astra Karla in epoxy.co.id
        pat_karla = re.compile(
            r'(<link\s+rel=["\']stylesheet["\']\s+id=["\']astra-google-fonts-css["\']\s+href=["\']https://fonts\.googleapis\.com/css\?family=Karla%3A400%2C)(["\'])'
        )
        if pat_karla.search(text):
            delim = "&amp;" if "&amp;display=" in text else "&#038;"
            text = pat_karla.sub(
                rf'\g<1>%7CBebas+Neue%3A400%2C%7CLato%3A700{delim}display=fallback{delim}ver=3.6.2\2',
                text,
            )
            h_count += 1

        # 2. Truncated Astra Poppins in DutaKoi.com
        pat_poppins = re.compile(
            r'(<link\s+rel=["\']stylesheet["\']\s+id=["\']astra-google-fonts-css["\']\s+href=["\']https://fonts\.googleapis\.com/css\?family=Poppins%3A400%2C)(["\'])'
        )
        if pat_poppins.search(text):
            delim = "&amp;" if "&amp;display=" in text else "&#038;"
            text = pat_poppins.sub(
                rf'\g<1>%7CBebas+Neue%3A400%2C%7CMontserrat%3A600{delim}display=fallback{delim}ver=3.7.9\2',
                text,
            )
            h_count += 1

        # 3. Truncated Elementor fonts in epoxy.co.id and DutaKoi.com
        pat_elem = re.compile(
            r'(<link\s+rel=["\']stylesheet["\']\s+id=["\']google-fonts-1-css["\']\s+href=["\']https://fonts\.googleapis\.com/css\?family=Roboto%3A100[^"\']*?%2C900italic)(["\'])'
        )
        if pat_elem.search(text):
            delim = "&amp;" if "&amp;display=" in text else "&#038;"
            if "ver=5.9.2" in text or "Montserrat%3A600" in text or "Poppins%3A400" in text:
                restored = (
                    r'\g<1>%7CRoboto+Slab%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic'
                    r'%7CPoppins%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic'
                    rf'{delim}display=auto{delim}ver=5.9.2\2'
                )
            else:
                restored = (
                    r'\g<1>%7CRoboto+Slab%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic'
                    r'%7CBebas+Neue%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic'
                    r'%7CKarla%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic'
                    rf'{delim}display=auto{delim}ver=5.7.2\2'
                )
            text = pat_elem.sub(restored, text)
            h_count += 1

        return text, h_count

    content, healed_count = heal_corrupted_fonts(content)
    changes += healed_count

    # Deterministic RNG per filepath so runs are idempotent across executions
    seed = int(hashlib.md5(filepath.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Cache chosen URL for identical spintax payloads within the same file
    chosen_cache: Dict[str, str] = {}

    def fix_url_match(match: re.Match) -> str:
        nonlocal changes
        full_match = match.group(0)
        prefix = match.group(1) or ""
        url_payload = match.group(2)

        # Strictly exclude Google Fonts and font stylesheets
        if "fonts.googleapis.com" in full_match or "fonts.gstatic.com" in full_match:
            return full_match

        # Check if url_payload contains spintax (| or %7C)
        if "|" in url_payload or "%7C" in url_payload:
            if url_payload in chosen_cache:
                chosen = chosen_cache[url_payload]
            else:
                candidates = [
                    u.strip()
                    for u in re.split(r"\||%7C", url_payload)
                    if u.strip().startswith("http")
                ]
                if len(candidates) < 2:
                    return full_match
                chosen = rng.choice(candidates)
                chosen_cache[url_payload] = chosen
            changes += 1
            return chosen
        elif prefix:
            # Single external URL with wp-content/uploads/ prepended
            changes += 1
            return url_payload
        return full_match

    # URL pattern matching defective wp-content/uploads/http or spintax | / %7C
    url_pattern = re.compile(
        r'((?:https?://[^"\'\s<>\\]+)?/wp-content/uploads/)?'
        r'(https?://(?:[^"\'\s<>\\|%]|%(?!7C))+(?:(?:\||%7C)https?://[^"\'\s<>\\]+)+|https?://[^"\'\s<>\\]+)'
    )

    def should_replace(m: re.Match) -> bool:
        full = m.group(0)
        prefix = m.group(1)
        payload = m.group(2)

        # Strictly exclude font services and non-image query parameters
        if "fonts.googleapis.com" in full or "fonts.gstatic.com" in full:
            return False
        if "display=" in payload or "family=" in payload:
            return False

        if prefix and payload.startswith("http"):
            return True
        if "|" in payload or "%7C" in payload:
            candidates = [
                u.strip()
                for u in re.split(r"\||%7C", payload)
                if u.strip().startswith("http")
            ]
            return len(candidates) >= 2
        return False

    def replacer(m: re.Match) -> str:
        if should_replace(m):
            return fix_url_match(m)
        return m.group(0)

    new_content = url_pattern.sub(replacer, content)

    # Also clean up width="1" height="1" on <img> tags that were wp-post-image
    def clean_img_tag(m: re.Match) -> str:
        nonlocal changes
        tag = m.group(0)
        cleaned = re.sub(r'\s+width=["\']1["\']', "", tag)
        cleaned = re.sub(r'\s+height=["\']1["\']', "", cleaned)
        if cleaned != tag:
            changes += 1
            return cleaned
        return tag

    new_content = re.sub(r"<img[^>]*wp-post-image[^>]*>", clean_img_tag, new_content)

    return new_content, changes


def process_html_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, int]:
    """Processes a single HTML file to fix broken image spintax and prefixes."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False, 0

    rel_path = str(file_path).replace("\\", "/")
    new_content, changes = resolve_broken_images_in_html(content, rel_path)

    if changes > 0 and new_content != content:
        if not dry_run:
            file_path.write_text(new_content, encoding="utf-8")
        return True, changes

    return False, 0


def scan_and_fix_directory(root_dir: Path, dry_run: bool = False) -> Dict[str, object]:
    """Scans and fixes all HTML files under root_dir."""
    modified_files: List[str] = []
    total_scanned = 0
    total_replacements = 0

    for root, _, files in os.walk(root_dir):
        # Ignore .git and node_modules
        if ".git" in root or "node_modules" in root:
            continue
        for f in files:
            if f.lower().endswith(".html") or f.lower().endswith(".htm"):
                p = Path(root) / f
                total_scanned += 1
                modified, count = process_html_file(p, dry_run=dry_run)
                if modified:
                    rel = p.relative_to(root_dir).as_posix()
                    modified_files.append(rel)
                    total_replacements += count

    return {
        "total_scanned": total_scanned,
        "modified_count": len(modified_files),
        "total_replacements": total_replacements,
        "modified_files": modified_files,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fix broken image spintax and wp-content/uploads prefixes in HTML"
    )
    parser.add_argument(
        "--root", default=".", help="Root directory containing HTML files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Scan without writing changes"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output summary as JSON"
    )

    args = parser.parse_args()
    root_path = Path(args.root).resolve()

    stats = scan_and_fix_directory(root_path, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print("=== Broken Image Spintax & Prefix Fix Summary ===")
        print(f"Directory:           {root_path}")
        print(f"HTML Files Scanned:  {stats['total_scanned']}")
        print(f"Files Modified:      {stats['modified_count']}")
        print(f"Replacements Made:   {stats['total_replacements']}")
        print(f"Dry Run:             {stats['dry_run']}")


if __name__ == "__main__":
    main()
