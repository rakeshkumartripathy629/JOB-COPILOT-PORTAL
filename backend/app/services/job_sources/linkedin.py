"""Dedicated LinkedIn job source (public-search discovery).

LinkedIn exposes no permissive job-search API for this product, so this source
discovers real indexed LinkedIn job postings through Google Custom Search scoped to
``site:linkedin.com/jobs``. It is honest about the acquisition method: results are
PUBLIC_SEARCH_DISCOVERY, never claimed to be an official LinkedIn API response.
"""

from __future__ import annotations

from app.services.job_sources.google_cse import GoogleCsePortalSource


class LinkedInJobSource(GoogleCsePortalSource):
    name = "linkedin"
    display_name = "LinkedIn"
    portal = "LinkedIn"
    site_operator = "site:linkedin.com/jobs"
