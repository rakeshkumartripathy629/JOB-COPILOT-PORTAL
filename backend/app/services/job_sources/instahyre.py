"""Dedicated Instahyre job source (public-search discovery).

Instahyre does not expose a public full-text job API for this product; this source
discovers real indexed Instahyre listings via Google Custom Search scoped to
``site:instahyre.com/job``.
"""

from __future__ import annotations

from app.services.job_sources.google_cse import GoogleCsePortalSource


class InstahyreJobSource(GoogleCsePortalSource):
    name = "instahyre"
    display_name = "Instahyre"
    portal = "Instahyre"
    site_operator = "site:instahyre.com/job"
