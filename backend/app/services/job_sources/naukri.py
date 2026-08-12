"""Dedicated Naukri job source (public-search discovery).

Naukri does not expose a public full-text job API for this product; this source
discovers real indexed Naukri listings via Google Custom Search scoped to
``site:naukri.com/job-listings``.
"""

from __future__ import annotations

from app.services.job_sources.google_cse import GoogleCsePortalSource


class NaukriJobSource(GoogleCsePortalSource):
    name = "naukri"
    display_name = "Naukri"
    portal = "Naukri"
    site_operator = "site:naukri.com/job-listings"
