"""
Client for the ClinicalTrials.gov API v2.

The API does not require authentication but implements rate limiting.
Configuration is handled via environment variables (base URL, rate limits).
"""

import os
import time
from typing import Any

import requests

_BASE_URL = os.environ.get("CLINICALTRIALS_API_BASE_URL", "https://clinicaltrials.gov/api/v2")
_DEFAULT_TIMEOUT = 30
_DEFAULT_PAGE_SIZE = 100  # ClinicalTrials.gov API supports up to 1000 per page


class HealthClient:
    """Thin wrapper around the ClinicalTrials.gov API v2 with pagination support."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        rate_limit_delay: float = 0.5,  # Delay between requests to respect rate limits
    ):
        self.base_url = (base_url or _BASE_URL).rstrip("/")
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limiting by sleeping if needed between requests."""
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a GET request with rate limiting."""
        self._rate_limit()
        resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def search_studies(
        self,
        query: str | None = None,
        filter_expr: str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        page_token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict:
        """
        Search for clinical studies using the v2 API.
        
        Args:
            query: Free-text search query (searches across all study fields)
            filter_expr: API filter expression (e.g., "AREA[ConditionSearch]women's health")
            page_size: Number of results per page (max 1000)
            page_token: Token for pagination (from previous response's nextPageToken)
            fields: List of fields to return (e.g., ["NCTId", "BriefTitle", "Condition"])
                   If None, returns default fields. Use get_study_fields() to see available fields.
        
        Returns:
            API response dict with:
            - studies: List of study records
            - nextPageToken: Token for next page (if more results exist)
            - totalCount: Total number of matching studies
        """
        params: dict[str, Any] = {}
        
        if query:
            params["query.term"] = query
        
        if filter_expr:
            params["filter.advanced"] = filter_expr
        
        if page_size:
            params["pageSize"] = min(page_size, 1000)  # API max is 1000
        
        if page_token:
            params["pageToken"] = page_token
        
        if fields:
            params["fields"] = "|".join(fields)
        
        return self.get("/studies", params=params)

    def get_study(
        self,
        nct_id: str,
        fields: list[str] | None = None,
    ) -> dict:
        """
        Fetch a single study by NCT ID.
        
        Args:
            nct_id: NCT ID (e.g., "NCT12345678")
            fields: List of fields to return (same as search_studies)
        
        Returns:
            Study record dict
        """
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = "|".join(fields)
        
        return self.get(f"/studies/{nct_id}", params=params)

    def paginated_search(
        self,
        query: str | None = None,
        filter_expr: str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        fields: list[str] | None = None,
        max_results: int | None = None,
    ):
        """
        Generator that yields individual study records across all pages.
        
        Args:
            query: Free-text search query
            filter_expr: API filter expression
            page_size: Results per page
            fields: Fields to return
            max_results: Maximum total results to return (None = unlimited)
        
        Yields:
            Individual study record dicts
        """
        page_token = None
        total_yielded = 0
        
        while True:
            response = self.search_studies(
                query=query,
                filter_expr=filter_expr,
                page_size=page_size,
                page_token=page_token,
                fields=fields,
            )
            
            studies = response.get("studies", [])
            for study in studies:
                yield study
                total_yielded += 1
                if max_results and total_yielded >= max_results:
                    return
            
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def get_womens_health_studies(
        self,
        additional_conditions: list[str] | None = None,
        max_results: int | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ):
        """
        Fetch women's health clinical trials.
        
        Searches for studies related to women's health conditions including:
        - Reproductive health (PCOS, endometriosis, infertility)
        - Pregnancy and maternal health
        - Menopause
        - Breast and gynecological cancers
        - Plus any additional conditions specified
        
        Args:
            additional_conditions: Additional condition terms to include in search
            max_results: Maximum number of studies to return (None = all)
            page_size: Results per API page
        
        Yields:
            Individual study record dicts with full protocol section
        """
        # Build comprehensive women's health condition search
        base_conditions = [
            "women's health",
            "women health",
            "PCOS",
            "polycystic ovary",
            "endometriosis",
            "uterine fibroids",
            "infertility female",
            "pregnancy",
            "maternal health",
            "menopause",
            "breast cancer",
            "ovarian cancer",
            "cervical cancer",
            "gynecologic",
            "prenatal",
            "postpartum",
        ]
        
        if additional_conditions:
            base_conditions.extend(additional_conditions)
        
        # Use AREA[ConditionSearch] to search in condition fields
        # OR together all conditions
        filter_parts = [f'AREA[ConditionSearch]{cond}' for cond in base_conditions]
        filter_expr = " OR ".join(filter_parts)
        
        # Request comprehensive fields for downstream processing
        fields = [
            "NCTId",
            "BriefTitle",
            "OfficialTitle",
            "BriefSummary",
            "DetailedDescription",
            "Condition",
            "OverallStatus",
            "Sex",
            "MinimumAge",
            "MaximumAge",
            "LeadSponsorName",
            "LocationCity",
            "LocationState",
            "LocationCountry",
            "StudyFirstPostDate",
            "LastUpdatePostDate",
        ]
        
        yield from self.paginated_search(
            filter_expr=filter_expr,
            page_size=page_size,
            fields=fields,
            max_results=max_results,
        )

    def get_study_fields(self) -> list[dict]:
        """
        Get list of all available study fields from the API.
        
        Returns:
            List of field definition dicts with name, type, description
        """
        response = self.get("/studies/metadata")
        return response.get("fields", [])

    def get_study_details(self, nct_id: str) -> dict | None:
        """
        Fetch detailed information for a single study by NCT ID.
        
        This is a convenience wrapper around get_study() that formats
        the response for the FemLens app frontend.
        
        Args:
            nct_id: NCT ID (e.g., "NCT12345678")
        
        Returns:
            Formatted study dict or None if not found
        """
        try:
            # Request comprehensive fields
            fields = [
                "NCTId",
                "BriefTitle",
                "OfficialTitle",
                "BriefSummary",
                "DetailedDescription",
                "Condition",
                "OverallStatus",
                "Sex",
                "MinimumAge",
                "MaximumAge",
                "LeadSponsorName",
                "LocationCity",
                "LocationState",
                "LocationCountry",
                "StudyFirstPostDate",
                "LastUpdatePostDate",
                "Phase",
                "EnrollmentCount",
                "StudyType",
            ]
            
            response = self.get_study(nct_id, fields=fields)
            
            # The API returns a single study dict
            if not response:
                return None
            
            # Extract protocol section (where most data lives)
            protocol = response.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            description = protocol.get("descriptionModule", {})
            status = protocol.get("statusModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            eligibility = protocol.get("eligibilityModule", {})
            design = protocol.get("designModule", {})
            contacts = protocol.get("contactsLocationsModule", {})
            
            # Format for frontend
            return {
                "nct_id": identification.get("nctId", nct_id),
                "title": identification.get("briefTitle", ""),
                "official_title": identification.get("officialTitle", ""),
                "summary": description.get("briefSummary", ""),
                "detailed_description": description.get("detailedDescription", ""),
                "conditions": identification.get("conditions", []),
                "status": status.get("overallStatus", ""),
                "sex": eligibility.get("sex", ""),
                "minimum_age": eligibility.get("minimumAge", ""),
                "maximum_age": eligibility.get("maximumAge", ""),
                "sponsor": sponsor.get("leadSponsor", {}).get("name", ""),
                "phase": design.get("phases", []),
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "study_type": design.get("studyType", ""),
                "first_posted": status.get("studyFirstPostDateStruct", {}).get("date", ""),
                "last_updated": status.get("lastUpdatePostDateStruct", {}).get("date", ""),
                "locations": [
                    f"{loc.get('city', '')}, {loc.get('state', '')} {loc.get('country', '')}"
                    for loc in contacts.get("locations", [])
                ],
                "url": f"https://clinicaltrials.gov/study/{nct_id}"
            }
            
        except Exception as e:
            # Log but don't crash - return None to indicate study not found
            return None

