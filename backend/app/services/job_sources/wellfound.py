"""Dedicated Wellfound job source (public-search discovery).

Wellfound has no keyless public API for full-text job search; this source discovers
real indexed Wellfound listings via Google Custom Search scoped to ``site:wellfound.com/jobs``.
"""

from __future__ import annotations

from app.services.job_sources.google_cse import GoogleCsePortalSource


class WellfoundJobSource(GoogleCsePortalSource):
    name = "wellfound"
    display_name = "Wellfound"
    portal = "Wellfound"
    site_operator = "site:wellfound.com/jobs"
