#!/usr/bin/env python3
"""Regression test suite for canonical fix_broken_spintax_images.py engine."""

import unittest
import sys
from pathlib import Path

# Add canonical scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "canonical" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fix_broken_spintax_images import resolve_broken_images_in_html


class TestFixBrokenSpintaxImages(unittest.TestCase):

    def test_spintax_resolution_and_schema_synchronization(self):
        """Tests that pipe-separated spintax is resolved to one URL and schema matches img."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
        <script type="application/ld+json">
        {"@type":"ImageObject","@id":"http://site.com/wp-content/uploads/https://1.bp.blogspot.com/imgA.jpg|https://1.bp.blogspot.com/imgB.jpg","url":"http://site.com/wp-content/uploads/https://1.bp.blogspot.com/imgA.jpg|https://1.bp.blogspot.com/imgB.jpg"}
        </script>
        </head>
        <body>
        <img width="1" height="1" src="/wp-content/uploads/https://1.bp.blogspot.com/imgA.jpg|https://1.bp.blogspot.com/imgB.jpg" class="attachment-large wp-post-image" alt="Test">
        </body>
        </html>
        '''
        fixed, count = resolve_broken_images_in_html(html, "sample-page.html")
        self.assertGreater(count, 0)
        self.assertNotIn("wp-content/uploads/https://", fixed)
        self.assertNotIn("|", fixed)
        self.assertNotIn('width="1"', fixed)
        self.assertNotIn('height="1"', fixed)

        # Confirm that either imgA.jpg or imgB.jpg was chosen, and both Schema and img use the EXACT same choice
        chosen = "https://1.bp.blogspot.com/imgA.jpg" if "imgA.jpg" in fixed else "https://1.bp.blogspot.com/imgB.jpg"
        self.assertIn(f'src="{chosen}"', fixed)
        self.assertIn(f'"url":"{chosen}"', fixed)
        self.assertIn(f'"@id":"{chosen}"', fixed)

    def test_single_external_url_with_upload_prefix(self):
        """Tests stripping /wp-content/uploads/ prefix in front of a single external URL."""
        html = '''
        <img width="1024" height="683" src="/wp-content/uploads/https://images.unsplash.com/photo-12345?w=1080">
        <script type="application/ld+json">
        {"@id":"https://dutakoi.com/wp-content/uploads/https://images.unsplash.com/photo-12345?w=1080"}
        </script>
        '''
        fixed, count = resolve_broken_images_in_html(html, "sample-unsplash.html")
        self.assertGreater(count, 0)
        self.assertIn('src="https://images.unsplash.com/photo-12345?w=1080"', fixed)
        self.assertIn('{"@id":"https://images.unsplash.com/photo-12345?w=1080"}', fixed)
        # Real dimensions preserved
        self.assertIn('width="1024"', fixed)
        self.assertIn('height="683"', fixed)

    def test_idempotency(self):
        """Tests that running the engine on already healed content makes zero changes."""
        healed_html = '''
        <img src="https://1.bp.blogspot.com/imgA.jpg" class="wp-post-image" alt="Clean">
        <script type="application/ld+json">
        {"url":"https://1.bp.blogspot.com/imgA.jpg"}
        </script>
        '''
        second_run, count = resolve_broken_images_in_html(healed_html, "sample-clean.html")
        self.assertEqual(count, 0)
        self.assertEqual(second_run, healed_html)

    def test_valid_local_uploads_untouched(self):
        """Tests that normal local /wp-content/uploads/ images without http are left untouched."""
        normal_html = '''
        <img src="/wp-content/uploads/2021/05/real-logo.png" width="200" height="50" alt="Logo">
        '''
        result, count = resolve_broken_images_in_html(normal_html, "sample-normal.html")
        self.assertEqual(count, 0)
        self.assertEqual(result, normal_html)


if __name__ == "__main__":
    unittest.main()
