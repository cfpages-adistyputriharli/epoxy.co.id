#!/usr/bin/env python3
"""Regression test suite for canonical fix_broken_spintax_images.py engine."""

import unittest
import sys
from pathlib import Path

# Add both canonical scripts directory and current directory to sys.path
here = Path(__file__).resolve().parent
canonical_scripts = here.parent / "canonical" / "scripts"
for d in [here, canonical_scripts]:
    if d.exists() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

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

    def test_google_fonts_pipe_not_treated_as_spintax(self):
        """Tests that Google Fonts link tags containing %7C and pipe are never truncated."""
        html = '''
        <link rel="stylesheet" id="astra-google-fonts-css" href="https://fonts.googleapis.com/css?family=Karla%3A400%2C%7CBebas+Neue%3A400%2C%7CLato%3A700&#038;display=fallback&#038;ver=3.6.2" media="all">
        <link rel="stylesheet" id="google-fonts-1-css" href="https://fonts.googleapis.com/css?family=Roboto%3A400%7CRoboto+Slab%3A400%7CBebas+Neue%3A400&#038;display=auto&#038;ver=5.7.2" media="all">
        '''
        result, count = resolve_broken_images_in_html(html, "cat-epoxy-balikpapan.html")
        self.assertEqual(count, 0)
        self.assertEqual(result, html)
        self.assertIn("Bebas+Neue", result)
        self.assertIn("Karla%3A400", result)
        self.assertIn("Lato%3A700", result)
        self.assertIn("Roboto+Slab", result)

    def test_spintax_image_resolved_while_google_fonts_intact(self):
        """Tests resolving image spintax in an HTML document while keeping Google Fonts 100% intact."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
        <link rel="stylesheet" id="astra-google-fonts-css" href="https://fonts.googleapis.com/css?family=Karla%3A400%2C%7CBebas+Neue%3A400%2C%7CLato%3A700&#038;display=fallback&#038;ver=3.6.2" media="all">
        <script type="application/ld+json">
        {"@type":"ImageObject","url":"/wp-content/uploads/https://1.bp.blogspot.com/img1.jpg|https://1.bp.blogspot.com/img2.jpg"}
        </script>
        </head>
        <body>
        <img width="1" height="1" src="/wp-content/uploads/https://1.bp.blogspot.com/img1.jpg|https://1.bp.blogspot.com/img2.jpg" class="attachment-large wp-post-image">
        </body>
        </html>
        '''
        result, count = resolve_broken_images_in_html(html, "cat-epoxy-balikpapan.html")
        self.assertGreater(count, 0)
        # Font link must be completely intact
        self.assertIn('href="https://fonts.googleapis.com/css?family=Karla%3A400%2C%7CBebas+Neue%3A400%2C%7CLato%3A700&#038;display=fallback&#038;ver=3.6.2"', result)
        self.assertIn("Bebas+Neue", result)
        # Image spintax and broken upload prefixes must be resolved
        self.assertNotIn("wp-content/uploads/https:", result)
        self.assertNotIn("|", result.split("<body>")[1])
        self.assertNotIn('width="1"', result)

    def test_heal_truncated_astra_google_fonts_karla(self):
        """Tests auto-healing previously truncated Astra Karla fonts in epoxy.co.id."""
        truncated_html = '''
        <link rel="stylesheet" id="astra-google-fonts-css" href="https://fonts.googleapis.com/css?family=Karla%3A400%2C" media="all">
        '''
        result, count = resolve_broken_images_in_html(truncated_html, "sample-truncated.html")
        self.assertEqual(count, 1)
        self.assertIn("Bebas+Neue%3A400", result)
        self.assertIn("Lato%3A700", result)

    def test_heal_truncated_astra_google_fonts_poppins(self):
        """Tests auto-healing previously truncated Astra Poppins fonts in DutaKoi.com."""
        truncated_html = '''
        <link rel="stylesheet" id="astra-google-fonts-css" href="https://fonts.googleapis.com/css?family=Poppins%3A400%2C" media="all">
        '''
        result, count = resolve_broken_images_in_html(truncated_html, "sample-poppins.html")
        self.assertEqual(count, 1)
        self.assertIn("Bebas+Neue%3A400", result)
        self.assertIn("Montserrat%3A600", result)

    def test_heal_truncated_elementor_fonts_epoxy(self):
        """Tests auto-healing previously truncated Elementor fonts in epoxy.co.id."""
        truncated_html = '''
        <link rel="stylesheet" id="google-fonts-1-css" href="https://fonts.googleapis.com/css?family=Roboto%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic" media="all">
        '''
        result, count = resolve_broken_images_in_html(truncated_html, "cat-epoxy-balikpapan.html")
        self.assertEqual(count, 1)
        self.assertIn("Roboto+Slab%3A100", result)
        self.assertIn("Bebas+Neue%3A100", result)
        self.assertIn("Karla%3A100", result)
        self.assertIn("ver=5.7.2", result)

    def test_heal_truncated_elementor_fonts_dutakoi(self):
        """Tests auto-healing previously truncated Elementor fonts in DutaKoi.com."""
        truncated_html = '''
        <link rel="stylesheet" id="google-fonts-1-css" href="https://fonts.googleapis.com/css?family=Roboto%3A100%2C100italic%2C200%2C200italic%2C300%2C300italic%2C400%2C400italic%2C500%2C500italic%2C600%2C600italic%2C700%2C700italic%2C800%2C800italic%2C900%2C900italic" media="all">
        <link rel="stylesheet" id="astra-google-fonts-css" href="https://fonts.googleapis.com/css?family=Poppins%3A400%2C%7CBebas+Neue%3A400%2C%7CMontserrat%3A600&#038;display=fallback&#038;ver=3.7.9" media="all">
        '''
        result, count = resolve_broken_images_in_html(truncated_html, "cara-merawat-koi.html")
        self.assertEqual(count, 1)
        self.assertIn("Roboto+Slab%3A100", result)
        self.assertIn("Poppins%3A100", result)
        self.assertIn("ver=5.9.2", result)


if __name__ == "__main__":
    unittest.main()
