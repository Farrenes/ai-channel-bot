from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlparse, urlunparse

try:  # pragma: no cover - optional dependency
    import feedparser
except ImportError:  # pragma: no cover - fallback path
    feedparser = None

try:  # pragma: no cover - optional dependency
    import httpx
except ImportError:  # pragma: no cover - fallback path
    httpx = None

try:  # pragma: no cover - optional dependency
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - fallback path
    BeautifulSoup = None

import database


BLOCKED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "t.me",
    "telegram.me",
    "docs.google.com",
}

SUSPICIOUS_HOSTS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.su",
    "rebrand.ly",
}

BLOCKED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".rtf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
}

MARKETPLACE_HINTS = {
    "marketplace",
    "amazon",
    "ebay",
    "etsy",
    "aliexpress",
    "shop",
    "store",
    "checkout",
    "cart",
}


class SourceFetcher(Protocol):
    async def get(self, url: str) -> Any:  # pragma: no cover - protocol
        ...


class HTTPXSourceFetcher:
    async def get(self, url: str) -> httpx.Response:
        if httpx is None:
            raise RuntimeError("httpx is not installed")
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            return await client.get(url, headers={"User-Agent": "BotTG-SourceValidation/1.0"})


@dataclass
class SourceInspection:
    url: str
    normalized_url: str
    domain: str
    name: str
    source_type: str
    access_mode: str
    parser_strategy: str
    classification: str
    trust_level: str
    supported_level: str
    content_type: str
    http_status: int | None
    title: str | None
    description: str | None
    items: list[dict[str, Any]]
    items_seen: int
    authority: int
    requires_confirmation: bool
    reason: str
    content_hash: str
    details: dict[str, Any]


class SourceValidationRepository:
    async def upsert_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            INSERT INTO content_sources (
                topic_profile_id,
                topic_config_id,
                name,
                url,
                normalized_url,
                domain,
                description,
                topic,
                source_type,
                access_mode,
                verification_status,
                authority,
                language_code,
                is_user_added,
                is_active,
                priority,
                rss_url,
                last_checked_at,
                last_success_at,
                last_error,
                metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
            ON CONFLICT (normalized_url) DO UPDATE SET
                topic_profile_id = EXCLUDED.topic_profile_id,
                topic_config_id = EXCLUDED.topic_config_id,
                name = EXCLUDED.name,
                url = EXCLUDED.url,
                domain = EXCLUDED.domain,
                description = EXCLUDED.description,
                topic = EXCLUDED.topic,
                source_type = EXCLUDED.source_type,
                access_mode = EXCLUDED.access_mode,
                verification_status = EXCLUDED.verification_status,
                authority = EXCLUDED.authority,
                language_code = EXCLUDED.language_code,
                is_user_added = EXCLUDED.is_user_added,
                is_active = EXCLUDED.is_active,
                priority = EXCLUDED.priority,
                rss_url = EXCLUDED.rss_url,
                last_checked_at = EXCLUDED.last_checked_at,
                last_success_at = EXCLUDED.last_success_at,
                last_error = EXCLUDED.last_error,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
        """

        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload.get("topic_profile_id"),
                payload.get("topic_config_id"),
                payload.get("name"),
                payload["url"],
                payload["normalized_url"],
                payload["domain"],
                payload.get("description"),
                payload.get("topic"),
                payload.get("source_type", "other"),
                payload.get("access_mode", "html"),
                payload.get("verification_status", "new"),
                payload.get("authority", 0),
                payload.get("language_code", "ru"),
                payload.get("is_user_added", True),
                payload.get("is_active", True),
                payload.get("priority", 100),
                payload.get("rss_url"),
                payload.get("last_checked_at"),
                payload.get("last_success_at"),
                payload.get("last_error"),
                payload.get("metadata", {}),
            )
            return dict(row) if row else {}

    async def insert_validation_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            INSERT INTO source_validation_runs (
                source_id,
                topic_profile_id,
                topic_config_id,
                run_status,
                result_status,
                request_source,
                idempotency_key,
                checked_url,
                fetch_mode,
                http_status,
                authority,
                error_message,
                details,
                started_at,
                completed_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            RETURNING id
        """

        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["source_id"],
                payload.get("topic_profile_id"),
                payload.get("topic_config_id"),
                payload.get("run_status", "succeeded"),
                payload.get("result_status"),
                payload.get("request_source", "api"),
                payload.get("idempotency_key"),
                payload.get("checked_url"),
                payload.get("fetch_mode"),
                payload.get("http_status"),
                payload.get("authority"),
                payload.get("error_message"),
                payload.get("details", {}),
                payload.get("started_at"),
                payload.get("completed_at"),
            )
            return dict(row) if row else {}

    async def insert_fetch_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            INSERT INTO source_fetch_runs (
                source_id,
                topic_profile_id,
                topic_config_id,
                validation_run_id,
                run_status,
                idempotency_key,
                fetch_mode,
                http_status,
                items_seen,
                items_saved,
                content_hash,
                error_message,
                details,
                started_at,
                completed_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            RETURNING id
        """

        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["source_id"],
                payload.get("topic_profile_id"),
                payload.get("topic_config_id"),
                payload.get("validation_run_id"),
                payload.get("run_status", "succeeded"),
                payload.get("idempotency_key"),
                payload.get("fetch_mode"),
                payload.get("http_status"),
                payload.get("items_seen", 0),
                payload.get("items_saved", 0),
                payload.get("content_hash"),
                payload.get("error_message"),
                payload.get("details", {}),
                payload.get("started_at"),
                payload.get("completed_at"),
            )
            return dict(row) if row else {}


class SourceValidationService:
    def __init__(
        self,
        repo: SourceValidationRepository | None = None,
        fetcher: SourceFetcher | None = None,
        llm_client: Any | None = None,
    ):
        self.repo = repo or SourceValidationRepository()
        self.fetcher = fetcher or HTTPXSourceFetcher()
        self.llm_client = llm_client

    async def validate_source(self, request: dict[str, Any] | str, **kwargs: Any) -> dict[str, Any]:
        inspection = await self._inspect(request, **kwargs)
        source_row = await self.repo.upsert_source(self._source_payload(inspection, kwargs))
        validation_row = await self.repo.insert_validation_run(
            self._validation_payload(inspection, kwargs, source_row.get("id"))
        )
        return self._build_response(inspection, source_row.get("id"), validation_row.get("id"), None)

    async def fetch_source(self, request: dict[str, Any] | str, **kwargs: Any) -> dict[str, Any]:
        inspection = await self._inspect(request, **kwargs)
        source_row = await self.repo.upsert_source(self._source_payload(inspection, kwargs))
        validation_row = await self.repo.insert_validation_run(
            self._validation_payload(inspection, kwargs, source_row.get("id"))
        )
        fetch_row = await self.repo.insert_fetch_run(
            self._fetch_payload(inspection, kwargs, source_row.get("id"), validation_row.get("id"))
        )
        return self._build_response(
            inspection,
            source_row.get("id"),
            validation_row.get("id"),
            fetch_row.get("id"),
        )

    async def _inspect(self, request: dict[str, Any] | str, **kwargs: Any) -> SourceInspection:
        payload = self._coerce_request(request, **kwargs)
        url = payload["url"]
        normalized_url = self._normalize_url(url)
        parsed = urlparse(normalized_url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        preflight = self._preflight_classification(domain, path, normalized_url)
        if preflight["classification"] in {"blocked", "suspicious", "high_risk", "unsupported"}:
            return self._build_inspection(
                url=url,
                normalized_url=normalized_url,
                domain=domain,
                response=None,
                parser_strategy="blocked",
                classification=preflight["classification"],
                trust_level=preflight["trust_level"],
                supported_level=preflight["classification"],
                title=None,
                description=preflight["reason"],
                items=[],
                reason=preflight["reason"],
            )

        response = await self.fetcher.get(normalized_url)
        http_status = getattr(response, "status_code", None)
        content_type = (getattr(response, "headers", {}) or {}).get("content-type", "").lower()
        body = getattr(response, "text", "") or ""

        if http_status and http_status >= 400:
            classification = "unsupported"
            parser_strategy = "blocked"
            trust_level = "low"
            title = None
            description = f"http_{http_status}"
            items: list[dict[str, Any]] = []
        else:
            feed = self._try_parse_feed(body, content_type)
            if feed is not None:
                classification = "supported"
                parser_strategy = "rss"
                trust_level = "trusted" if feed["items_seen"] else "mixed"
                title = feed["title"]
                description = feed["description"]
                items = feed["items"]
            else:
                html = self._try_parse_html(body, content_type)
                if html is not None:
                    classification = html["classification"]
                    parser_strategy = "html"
                    trust_level = html["trust_level"]
                    title = html["title"]
                    description = html["description"]
                    items = html["items"]
                else:
                    classification = "unsupported"
                    parser_strategy = "blocked"
                    trust_level = "low"
                    title = None
                    description = "unsupported_content"
                    items = []

        source_type = self._infer_source_type(domain, path, parser_strategy, title)
        supported_level = classification
        authority = self._authority_score(classification, trust_level)
        requires_confirmation = classification in {"suspicious", "high_risk", "partially_supported"}

        return self._build_inspection(
            url=url,
            normalized_url=normalized_url,
            domain=domain,
            response=response,
            parser_strategy=parser_strategy,
            classification=classification,
            trust_level=trust_level,
            supported_level=supported_level,
            title=title,
            description=description,
            items=items,
            reason=description or classification,
            source_type=source_type,
            authority=authority,
            requires_confirmation=requires_confirmation,
        )

    def _coerce_request(self, request: dict[str, Any] | str, **kwargs: Any) -> dict[str, Any]:
        if isinstance(request, str):
            payload = {"url": request}
        else:
            payload = dict(request)
        payload.update(kwargs)
        if not payload.get("url"):
            raise ValueError("url is required")
        return payload

    def _normalize_url(self, url: str) -> str:
        clean = url.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", clean):
            clean = f"https://{clean}"
        parsed = urlparse(clean)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        query_items = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}
        ]
        query = "&".join(f"{key}={value}" for key, value in sorted(query_items))
        return urlunparse((scheme, netloc, path, "", query, ""))

    def _preflight_classification(self, domain: str, path: str, normalized_url: str) -> dict[str, str]:
        host = domain.lower()
        full_url = normalized_url.lower()

        if any(host == item or host.endswith(f".{item}") for item in BLOCKED_HOSTS):
            return {"classification": "blocked", "trust_level": "blocked", "reason": "blocked_host"}

        if any(item in host for item in SUSPICIOUS_HOSTS):
            return {"classification": "suspicious", "trust_level": "low", "reason": "suspicious_shortener"}

        if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS) or any(ext in full_url for ext in BLOCKED_EXTENSIONS):
            return {"classification": "blocked", "trust_level": "blocked", "reason": "blocked_document"}

        if any(hint in host or hint in path for hint in MARKETPLACE_HINTS):
            return {"classification": "high_risk", "trust_level": "low", "reason": "high_risk_marketplace"}

        if "login" in path or "auth" in path or "redirect" in path:
            return {"classification": "suspicious", "trust_level": "low", "reason": "suspicious_path"}

        return {"classification": "partially_supported", "trust_level": "mixed", "reason": "needs_fetch"}

    def _try_parse_feed(self, body: str, content_type: str) -> dict[str, Any] | None:
        lowered = content_type.lower()
        if not body or not (("rss" in lowered) or ("xml" in lowered) or body.lstrip().startswith("<?xml") or "<rss" in body.lower()):
            return None

        if feedparser is not None:
            parsed = feedparser.parse(body)
            if not getattr(parsed, "feed", None) and not getattr(parsed, "entries", None):
                return None

            title = getattr(parsed.feed, "title", None) or self._extract_tag_text(body, "title")
            description = getattr(parsed.feed, "subtitle", None) or getattr(parsed.feed, "description", None)
            items = []
            for entry in list(getattr(parsed, "entries", []))[:5]:
                items.append(
                    {
                        "title": entry.get("title"),
                        "url": entry.get("link"),
                        "summary": entry.get("summary", ""),
                    }
                )
        else:
            title = self._extract_tag_text(body, "title")
            description = self._extract_tag_text(body, "description")
            items = []
            for match in re.finditer(r"<item>(.*?)</item>", body, re.IGNORECASE | re.DOTALL):
                item_body = match.group(1)
                items.append(
                    {
                        "title": self._extract_tag_text(item_body, "title"),
                        "url": self._extract_tag_text(item_body, "link"),
                        "summary": self._extract_tag_text(item_body, "description") or "",
                    }
                )
        return {
            "title": title,
            "description": description,
            "items": items,
            "items_seen": len(items),
        }

    def _try_parse_html(self, body: str, content_type: str) -> dict[str, Any] | None:
        lowered = content_type.lower()
        if not body or ("html" not in lowered and "<html" not in body.lower()):
            return None

        if BeautifulSoup is not None:
            soup = BeautifulSoup(body, "html.parser")
            title = self._clean_text(soup.title.get_text(" ", strip=True) if soup.title else None)
            h1 = self._clean_text(soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else None)
            paragraphs = [
                self._clean_text(p.get_text(" ", strip=True))
                for p in soup.find_all("p")
            ]
            paragraphs = [p for p in paragraphs if p]
        else:
            title = self._extract_tag_text(body, "title")
            h1 = self._extract_tag_text(body, "h1")
            paragraphs = [
                self._clean_text(match.group(1))
                for match in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.IGNORECASE | re.DOTALL)
            ]
            paragraphs = [p for p in paragraphs if p]
        article_text = " ".join(paragraphs[:3]).strip()

        if not title and not h1 and not article_text:
            return {
                "classification": "partially_supported",
                "trust_level": "low",
                "title": None,
                "description": "html_without_article_signals",
                "items": [],
            }

        if title and (h1 or article_text):
            summary = article_text[:280] if article_text else h1
            return {
                "classification": "supported",
                "trust_level": "mixed",
                "title": h1 or title,
                "description": summary,
                "items": [
                    {
                        "title": h1 or title,
                        "url": None,
                        "summary": summary,
                    }
                ],
            }

        return {
            "classification": "partially_supported",
            "trust_level": "low",
            "title": title or h1,
            "description": article_text[:180] if article_text else "html_minimal",
            "items": [
                {
                    "title": title or h1,
                    "url": None,
                    "summary": article_text[:180] if article_text else "",
                }
            ]
            if (title or h1 or article_text)
            else [],
        }

    def _infer_source_type(self, domain: str, path: str, parser_strategy: str, title: str | None) -> str:
        haystack = f"{domain} {path} {title or ''}".lower()
        if parser_strategy == "rss":
            return "news"
        if "docs" in haystack or "documentation" in haystack:
            return "docs"
        if "blog" in haystack:
            return "blog"
        if "news" in haystack:
            return "news"
        if "forum" in haystack or "community" in haystack:
            return "forum"
        if "official" in haystack:
            return "official"
        if any(term in haystack for term in {"youtube", "tiktok", "instagram", "x.com", "twitter"}):
            return "social"
        return "other"

    def _authority_score(self, classification: str, trust_level: str) -> int:
        if classification == "supported" and trust_level == "trusted":
            return 85
        if classification == "supported":
            return 65
        if classification == "partially_supported":
            return 35
        if classification == "high_risk":
            return 20
        if classification == "suspicious":
            return 15
        return 0

    def _build_inspection(
        self,
        *,
        url: str,
        normalized_url: str,
        domain: str,
        response: Any | None,
        parser_strategy: str,
        classification: str,
        trust_level: str,
        supported_level: str,
        title: str | None,
        description: str | None,
        items: list[dict[str, Any]],
        reason: str,
        source_type: str | None = None,
        authority: int | None = None,
        requires_confirmation: bool | None = None,
    ) -> SourceInspection:
        content_type = ""
        http_status = None
        fetched_url = normalized_url
        if response is not None:
            content_type = (getattr(response, "headers", {}) or {}).get("content-type", "")
            http_status = getattr(response, "status_code", None)
            fetched_url = getattr(response, "url", normalized_url)

        name = title or domain
        description = description or ""
        items_seen = len(items)
        content_hash = self._hash_payload(normalized_url, title, description, classification, parser_strategy)
        language_code = self._detect_language(f"{title or ''} {description}")
        details = {
            "classification": classification,
            "parser_strategy": parser_strategy,
            "trust_level": trust_level,
            "supported_level": supported_level,
            "content_type": content_type,
            "fetched_url": fetched_url,
            "items": items,
            "reason": reason,
            "source_type": source_type or self._infer_source_type(domain, urlparse(normalized_url).path.lower(), parser_strategy, title),
        }
        return SourceInspection(
            url=url,
            normalized_url=normalized_url,
            domain=domain,
            name=name,
            source_type=source_type or self._infer_source_type(domain, urlparse(normalized_url).path.lower(), parser_strategy, title),
            access_mode=parser_strategy if parser_strategy in {"rss", "html"} else "html",
            parser_strategy=parser_strategy,
            classification=classification,
            trust_level=trust_level,
            supported_level=supported_level,
            content_type=content_type,
            http_status=http_status,
            title=title,
            description=description,
            items=items,
            items_seen=items_seen,
            authority=authority if authority is not None else self._authority_score(classification, trust_level),
            requires_confirmation=bool(requires_confirmation),
            reason=reason,
            content_hash=content_hash,
            details={**details, "language_code": language_code},
        )

    def _source_payload(self, inspection: SourceInspection, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "topic_profile_id": request.get("topic_profile_id"),
            "topic_config_id": request.get("topic_config_id"),
            "name": request.get("name") or inspection.name,
            "url": inspection.url,
            "normalized_url": inspection.normalized_url,
            "domain": inspection.domain,
            "description": inspection.description,
            "topic": request.get("topic"),
            "source_type": inspection.source_type,
            "access_mode": inspection.access_mode,
            "verification_status": self._verification_status(inspection.classification),
            "authority": inspection.authority,
            "language_code": inspection.details["language_code"],
            "is_user_added": request.get("is_user_added", True),
            "is_active": request.get("is_active", True),
            "priority": request.get("priority", 100),
            "rss_url": inspection.url if inspection.parser_strategy == "rss" else None,
            "last_checked_at": datetime.utcnow(),
            "last_success_at": datetime.utcnow() if inspection.classification in {"supported", "partially_supported"} else None,
            "last_error": None if inspection.classification in {"supported", "partially_supported"} else inspection.reason,
            "metadata": {
                **inspection.details,
                "trust_level": inspection.trust_level,
                "supported_level": inspection.supported_level,
                "parser_strategy": inspection.parser_strategy,
                "classification": inspection.classification,
                "items_seen": inspection.items_seen,
                "content_hash": inspection.content_hash,
            },
        }

    def _validation_payload(self, inspection: SourceInspection, request: dict[str, Any], source_id: Any) -> dict[str, Any]:
        status = self._workflow_status(inspection.classification)
        return {
            "source_id": source_id,
            "topic_profile_id": request.get("topic_profile_id"),
            "topic_config_id": request.get("topic_config_id"),
            "run_status": status,
            "result_status": self._verification_status(inspection.classification),
            "request_source": request.get("request_source", "api"),
            "idempotency_key": request.get("idempotency_key"),
            "checked_url": inspection.normalized_url,
            "fetch_mode": inspection.access_mode,
            "http_status": inspection.http_status,
            "authority": inspection.authority,
            "error_message": None if inspection.classification in {"supported", "partially_supported"} else inspection.reason,
            "details": {
                **inspection.details,
                "items_seen": inspection.items_seen,
                "support_level": inspection.supported_level,
                "trust_level": inspection.trust_level,
                "classification": inspection.classification,
                "content_hash": inspection.content_hash,
            },
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        }

    def _fetch_payload(
        self,
        inspection: SourceInspection,
        request: dict[str, Any],
        source_id: Any,
        validation_run_id: Any,
    ) -> dict[str, Any]:
        run_status = "succeeded" if inspection.classification in {"supported", "partially_supported"} else "skipped"
        items_saved = inspection.items_seen if run_status == "succeeded" else 0
        return {
            "source_id": source_id,
            "topic_profile_id": request.get("topic_profile_id"),
            "topic_config_id": request.get("topic_config_id"),
            "validation_run_id": validation_run_id,
            "run_status": run_status,
            "idempotency_key": request.get("idempotency_key"),
            "fetch_mode": inspection.access_mode,
            "http_status": inspection.http_status,
            "items_seen": inspection.items_seen if run_status == "succeeded" else 0,
            "items_saved": items_saved,
            "content_hash": inspection.content_hash,
            "error_message": None if run_status == "succeeded" else inspection.reason,
            "details": {
                **inspection.details,
                "classification": inspection.classification,
                "trust_level": inspection.trust_level,
            },
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        }

    def _build_response(
        self,
        inspection: SourceInspection,
        source_id: Any,
        validation_run_id: Any,
        fetch_run_id: Any,
    ) -> dict[str, Any]:
        data = {
            "source_id": source_id,
            "validation_run_id": validation_run_id,
            "fetch_run_id": fetch_run_id,
            "url": inspection.url,
            "normalized_url": inspection.normalized_url,
            "domain": inspection.domain,
            "classification": inspection.classification,
            "parser_strategy": inspection.parser_strategy,
            "trust_level": inspection.trust_level,
            "supported_level": inspection.supported_level,
            "source_type": inspection.source_type,
            "access_mode": inspection.access_mode,
            "content_type": inspection.content_type,
            "http_status": inspection.http_status,
            "title": inspection.title,
            "description": inspection.description,
            "items_seen": inspection.items_seen,
            "items": inspection.items,
            "requires_confirmation": inspection.requires_confirmation,
            "reason": inspection.reason,
        }
        return data

    def _verification_status(self, classification: str) -> str:
        return {
            "supported": "verified",
            "partially_supported": "verified_low_confidence",
            "suspicious": "needs_user_confirmation",
            "high_risk": "low_authority",
            "unsupported": "unsupported_access",
            "blocked": "blocked",
        }.get(classification, "needs_user_confirmation")

    def _workflow_status(self, classification: str) -> str:
        return "succeeded" if classification in {"supported", "partially_supported"} else "skipped"

    def _hash_payload(self, *parts: str | None) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update((part or "").encode("utf-8"))
            digest.update(b"|")
        return digest.hexdigest()

    def _detect_language(self, text: str) -> str:
        return "ru" if re.search(r"[А-Яа-яЁё]", text) else "en"

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = unescape(re.sub(r"\s+", " ", value)).strip()
        return cleaned or None

    def _extract_tag_text(self, body: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", body, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return self._clean_text(match.group(1))
