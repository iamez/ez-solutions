"""Sitemaps for SEO — referenced by robots.txt."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    """Sitemap for static public pages."""

    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home:index", "home:about"]

    def location(self, item):
        return reverse(item)


class PricingSitemap(Sitemap):
    """Sitemap for the pricing page."""

    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return ["services:pricing"]

    def location(self, item):
        return reverse(item)
