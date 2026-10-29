"""Sprint 13 — Sliding-Window Behavioral Feature Store.

Maintains temporal event histories for DIDs and client IPs to extract
sliding-window velocity, device divergence, and geolocation jump indicators
per Master Implementation Plan Section 14.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


class SlidingWindowFeatureStore:
    """Thread-safe in-memory sliding-window feature store for fraud detection."""

    def __init__(
        self,
        window_retention_sec: float = 3600.0,
        *,
        max_tracked_dids: int = 10000,
        max_events_per_did: int = 500,
        max_devices_per_did: int = 50,
    ) -> None:
        self.retention_sec = window_retention_sec
        self.max_tracked_dids = max_tracked_dids
        self.max_events_per_did = max_events_per_did
        self.max_devices_per_did = max_devices_per_did
        # The process-local HMAC key lets the heuristic compare devices without
        # retaining raw device fingerprints. It intentionally cannot correlate
        # a fingerprint across service restarts.
        self._fingerprint_key = secrets.token_bytes(32)
        self._lock = Lock()
        # did -> bounded deque of (timestamp, event_type); raw event payloads
        # are not retained after the derived signals have been calculated.
        self._did_events: Dict[str, deque] = defaultdict(deque)
        # did -> set of process-local HMAC fingerprints
        self._known_devices: Dict[str, set] = defaultdict(set)
        # did -> last action timestamp
        self._last_action_time: Dict[str, float] = {}
        # did -> last known coordinates; source IP is not retained.
        self._last_known_geo: Dict[str, Tuple[float, float]] = {}

    def _fingerprint_digest(self, fingerprint: str) -> str:
        return hmac.new(
            self._fingerprint_key,
            fingerprint.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _forget_did(self, did: str) -> None:
        self._did_events.pop(did, None)
        self._known_devices.pop(did, None)
        self._last_action_time.pop(did, None)
        self._last_known_geo.pop(did, None)

    def ingest_event(
        self,
        *,
        event_id: str,
        event_type: str,
        did: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Mozilla/5.0",
        device_fingerprint: str = "default-device",
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingests a platform security event and updates sliding-window metrics."""
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp()
        meta = metadata or {}

        with self._lock:
            # Purge expired events
            self._purge_expired(ts)

            if did not in self._did_events:
                while len(self._did_events) >= self.max_tracked_dids:
                    oldest_did = next(iter(self._did_events))
                    self._forget_did(oldest_did)
                self._did_events[did] = deque(maxlen=self.max_events_per_did)

            # Only the fields needed for window counts survive ingestion.
            self._did_events[did].append({"event_type": event_type, "timestamp": ts})
            fingerprint_digest = self._fingerprint_digest(device_fingerprint)

            # Update device baseline
            if event_type in {"LOGIN", "WALLET_CREATED"} and not meta.get("suspicious", False):
                devices = self._known_devices[did]
                if fingerprint_digest in devices or len(devices) < self.max_devices_per_did:
                    devices.add(fingerprint_digest)

            # Calculate metrics
            summary = self._compute_summary_locked(did, ts, client_ip, device_fingerprint, meta)
            self._last_action_time[did] = ts

            # Update coordinates if provided in metadata
            lat = meta.get("latitude")
            lon = meta.get("longitude")
            if lat is not None and lon is not None:
                # Retain a coarse ~10 km cell only; precise coordinates are
                # used for the current distance calculation but not persisted.
                self._last_known_geo[did] = (
                    round(float(lat), 1),
                    round(float(lon), 1),
                )

            return summary

    def get_features(
        self,
        did: str,
        *,
        client_ip: str = "127.0.0.1",
        device_fingerprint: str = "default-device",
        current_timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extracts normalized behavioral features for real-time model evaluation."""
        ts = current_timestamp if current_timestamp is not None else datetime.now(timezone.utc).timestamp()
        meta = metadata or {}

        with self._lock:
            self._purge_expired(ts)
            return self._compute_summary_locked(did, ts, client_ip, device_fingerprint, meta)

    def _compute_summary_locked(
        self,
        did: str,
        current_ts: float,
        client_ip: str,
        device_fingerprint: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        events = self._did_events.get(did, ())
        cutoff_10m = current_ts - 600.0

        # 1. Failed attempts in last 10m
        failed_attempts_10m = sum(
            1 for e in events
            if e["timestamp"] >= cutoff_10m and e["event_type"] in {"LOGIN_FAILED", "VERIFICATION_FAILED"}
        )

        # 2. Presentation frequency in last 10m
        presentation_frequency_10m = sum(
            1 for e in events
            if e["timestamp"] >= cutoff_10m and e["event_type"] == "CREDENTIAL_PRESENTED"
        )

        # 3. Time since last action
        last_ts = self._last_action_time.get(did)
        time_since_last_sec = max(current_ts - last_ts, 0.0) if last_ts is not None else 300.0

        # 4. Device match
        known = self._known_devices.get(did, set())
        device_match = (self._fingerprint_digest(device_fingerprint) in known) if known else True

        # 5. Impossible Travel Geo distance
        geo_distance_km = 0.0
        cur_lat = metadata.get("latitude")
        cur_lon = metadata.get("longitude")
        if cur_lat is not None and cur_lon is not None and did in self._last_known_geo:
            prev_lat, prev_lon = self._last_known_geo[did]
            geo_distance_km = self._haversine_distance(prev_lat, prev_lon, float(cur_lat), float(cur_lon))
        elif metadata.get("geo_distance_km") is not None:
            geo_distance_km = float(metadata["geo_distance_km"])

        # 6. Tor / Proxy detection heuristic
        is_tor_or_proxy = self._is_tor_or_proxy(client_ip) or metadata.get("is_tor_or_proxy", False)

        return {
            "did": did,
            "failed_attempts": failed_attempts_10m,
            "presentation_frequency_10m": max(presentation_frequency_10m, 1),
            "time_since_last_action_sec": time_since_last_sec,
            "geo_distance_km": geo_distance_km,
            "device_fingerprint": device_fingerprint,
            "device_fingerprint_match": device_match,
            "is_tor_or_proxy": bool(is_tor_or_proxy),
            "total_events_in_window": len(events),
        }

    def _purge_expired(self, current_ts: float) -> None:
        cutoff = current_ts - self.retention_sec
        for did in list(self._did_events.keys()):
            q = self._did_events[did]
            while q and q[0]["timestamp"] < cutoff:
                q.popleft()
            if not q:
                self._forget_did(did)

    @staticmethod
    def _is_tor_or_proxy(ip: str) -> bool:
        parts = [int(p) for p in ip.split(".") if p.isdigit()]
        if len(parts) == 4 and parts[0] in [185, 194, 45, 91] and parts[1] in [220, 154, 101, 255]:
            return True
        return False

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0  # Earth radius in kilometers
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2.0) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c


# Global singleton instance
feature_store = SlidingWindowFeatureStore()
