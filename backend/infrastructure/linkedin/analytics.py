from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.analytics.models import (
    LINKEDIN_MEMBER_METRICS_V1,
    AnalyticsCapabilityV1,
    MetricAvailability,
    MetricValueV1,
    NormalizedMetric,
    canonical_sha256,
)


class AnalyticsSafeFailure(RuntimeError):
    """Analytics collection cannot proceed, but no side effect is uncertain."""


class AnalyticsRetryableFailure(RuntimeError):
    """Side-effect-free provider read may be retried under bounded policy."""


@dataclass(frozen=True)
class AnalyticsObservation:
    provider_api_version: str
    observed_at: datetime
    raw_available_metrics: dict[str, int]
    normalized_metrics: dict[str, int]
    unavailable_metrics: tuple[str, ...]
    raw_digest: str


class LinkedInAnalyticsAdapter:
    API_BASE = "https://api.linkedin.com"
    REQUIRED_SCOPE = "r_member_postAnalytics"
    PROVIDER_METRICS = LINKEDIN_MEMBER_METRICS_V1
    NORMALIZED = {
        "IMPRESSION": NormalizedMetric.VIEWS_OR_IMPRESSIONS,
        "RESHARE": NormalizedMetric.SHARES,
        "REACTION": NormalizedMetric.LIKES_OR_REACTIONS,
        "COMMENT": NormalizedMetric.COMMENTS,
    }

    def __init__(
        self,
        *,
        settings: LinkedInOAuthSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings
        self.client = client
        self._cipher_instance: LinkedInTokenCipher | None = None

    def _resolved_settings(self) -> LinkedInOAuthSettings:
        if self.settings is None:
            self.settings = LinkedInOAuthSettings.from_env()
        return self.settings

    def _cipher(self) -> LinkedInTokenCipher:
        if self._cipher_instance is None:
            self._cipher_instance = LinkedInTokenCipher(self._resolved_settings().token_key)
        return self._cipher_instance

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(method, url, **kwargs)

    def _token(self, connection: dict[str, Any]) -> str:
        encrypted = str(connection.get("encrypted_access_token") or "")
        if not encrypted:
            raise AnalyticsSafeFailure("LinkedIn connection has no encrypted token authority")
        try:
            return self._cipher().decrypt(encrypted)
        except Exception as exc:
            raise AnalyticsSafeFailure("LinkedIn connection cannot be decrypted; reconnect LinkedIn") from exc

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Linkedin-Version": self._resolved_settings().api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    async def capabilities(
        self,
        connection: dict[str, Any] | None,
        *,
        last_success_at: datetime | None = None,
    ) -> AnalyticsCapabilityV1:
        now = datetime.now(timezone.utc)
        if not connection:
            return AnalyticsCapabilityV1(
                connected=False,
                analytics_available=False,
                analytics_scope_granted=False,
                supported_provider_metrics=self.PROVIDER_METRICS,
                observed_at=now,
                last_success_at=last_success_at,
                reason="LinkedIn is not connected",
            )
        try:
            settings = self._resolved_settings()
        except Exception as exc:
            return AnalyticsCapabilityV1(
                connected=False,
                analytics_available=False,
                analytics_scope_granted=False,
                supported_provider_metrics=self.PROVIDER_METRICS,
                external_identity=connection.get("external_identity"),
                observed_at=now,
                last_success_at=last_success_at,
                reason=f"LinkedIn provider configuration unavailable: {exc}",
            )

        expires_at = connection.get("expires_at")
        if isinstance(expires_at, datetime) and (expires_at.tzinfo is None or expires_at.utcoffset() is None):
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        scopes = set(connection.get("scopes") or [])
        analytics_scope_granted = self.REQUIRED_SCOPE in scopes
        reason = None
        if connection.get("status") != "CONNECTED":
            reason = "LinkedIn connection is not connected"
        elif not isinstance(expires_at, datetime) or expires_at <= now:
            reason = "LinkedIn connection expired; reconnect LinkedIn"
        elif not analytics_scope_granted:
            reason = "LinkedIn analytics permission is not granted"
        else:
            try:
                self._token(connection)
            except AnalyticsSafeFailure as exc:
                reason = str(exc)

        connected = (
            connection.get("status") == "CONNECTED"
            and isinstance(expires_at, datetime)
            and expires_at > now
        )
        return AnalyticsCapabilityV1(
            connected=connected,
            analytics_available=reason is None,
            analytics_scope_granted=analytics_scope_granted,
            supported_provider_metrics=self.PROVIDER_METRICS,
            external_identity=connection.get("external_identity"),
            api_version=settings.api_version,
            observed_at=now,
            last_success_at=last_success_at,
            reason=reason,
        )

    @staticmethod
    def _restli_entity(external_post_id: str) -> str:
        if external_post_id.startswith("urn:li:share:"):
            entity_type = "share"
        elif external_post_id.startswith("urn:li:ugcPost:"):
            entity_type = "ugc"
        else:
            raise AnalyticsSafeFailure("LinkedIn analytics requires a share or ugcPost URN")
        return f"({entity_type}:{quote(external_post_id, safe='')})"

    @staticmethod
    def _metric_type(element: dict[str, Any]) -> str | None:
        value = element.get("metricType")
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and value:
            nested = next(iter(value.values()))
            return nested if isinstance(nested, str) else None
        return None

    async def _collect_metric(
        self,
        *,
        token: str,
        external_post_id: str,
        provider_metric: str,
    ) -> MetricValueV1:
        entity = self._restli_entity(external_post_id)
        url = (
            f"{self.API_BASE}/rest/memberCreatorPostAnalytics"
            f"?q=entity&entity={entity}&queryType={provider_metric}&aggregation=TOTAL"
        )
        try:
            response = await self._request("GET", url, headers=self._headers(token))
        except httpx.RequestError as exc:
            raise AnalyticsRetryableFailure("LinkedIn analytics request failed in transport") from exc

        if response.status_code == 429 or response.status_code >= 500 or response.status_code == 408:
            raise AnalyticsRetryableFailure(
                f"LinkedIn analytics returned retryable HTTP {response.status_code}"
            )
        if response.status_code in {401, 403}:
            raise AnalyticsSafeFailure(
                f"LinkedIn analytics authorization unavailable (HTTP {response.status_code})"
            )
        if response.status_code != 200:
            raise AnalyticsSafeFailure(
                f"LinkedIn analytics request rejected with HTTP {response.status_code}"
            )

        try:
            payload = response.json()
            elements = payload.get("elements")
        except (TypeError, ValueError) as exc:
            raise AnalyticsSafeFailure("LinkedIn analytics returned invalid JSON evidence") from exc
        if not isinstance(elements, list):
            raise AnalyticsSafeFailure("LinkedIn analytics response has no elements list")
        normalized = self.NORMALIZED.get(provider_metric)
        if not elements:
            return MetricValueV1(
                normalized_metric=normalized,
                provider_metric=provider_metric,
                availability=MetricAvailability.UNAVAILABLE,
                reason="provider returned no metric observation",
            )
        if len(elements) != 1 or not isinstance(elements[0], dict):
            raise AnalyticsSafeFailure("LinkedIn TOTAL analytics returned unexpected cardinality")
        element = elements[0]
        returned_metric = self._metric_type(element)
        count = element.get("count")
        if returned_metric != provider_metric or not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AnalyticsSafeFailure("LinkedIn analytics returned invalid metric evidence")
        return MetricValueV1(
            normalized_metric=normalized,
            provider_metric=provider_metric,
            availability=MetricAvailability.AVAILABLE,
            value=count,
        )

    async def collect(
        self,
        *,
        external_post_id: str,
        connection: dict[str, Any],
    ) -> AnalyticsObservation:
        capability = await self.capabilities(connection)
        if not capability.analytics_available:
            raise AnalyticsSafeFailure(capability.reason or "LinkedIn analytics unavailable")
        token = self._token(connection)
        raw_available: dict[str, int] = {}
        normalized: dict[str, int] = {}
        unavailable: list[str] = []
        for provider_metric in self.PROVIDER_METRICS:
            metric = await self._collect_metric(
                token=token,
                external_post_id=external_post_id,
                provider_metric=provider_metric,
            )
            if metric.availability is MetricAvailability.AVAILABLE and metric.value is not None:
                raw_available[provider_metric] = metric.value
                if metric.normalized_metric is not None:
                    normalized[metric.normalized_metric.value] = metric.value
            else:
                unavailable.append(provider_metric)

        if not raw_available:
            raise AnalyticsSafeFailure("LinkedIn returned no observed metric evidence")
        observed_at = datetime.now(timezone.utc)
        return AnalyticsObservation(
            provider_api_version=self._resolved_settings().api_version,
            observed_at=observed_at,
            raw_available_metrics=raw_available,
            normalized_metrics=normalized,
            unavailable_metrics=tuple(unavailable),
            raw_digest=canonical_sha256(raw_available),
        )
