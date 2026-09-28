"""Sprint 13 — Sliding-Window Behavioral Feature Store.

Maintains temporal event histories for DIDs and client IPs to extract
sliding-window velocity, device divergence, and geolocation jump indicators
per Master Implementation Plan Section 14.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


class SlidingWindowFeatureStore:
    """Thread-safe in-memory sliding-window feature store for fraud detection."""

    def __init__(self, window_retention_sec: float = 3600.0) -> None:
        self.retention_sec = window_retention_sec
        self._lock = Lock()
        # did -> deque of (timestamp, event_type, ip, device, metadata)
        self._did_events: Dict[str, deque] = defaultdict(deque)
        # did -> set of known device fingerprints
        self._known_devices: Dict[str, set] = defaultdict(set)
        # did -> last action timestamp
        self._last_action_time: Dict[str, float] = {}
        # did -> last known (lat, lon, ip)
        self._last_known_geo: Dict[str, Tuple[float, float, str]] = {}

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

            # Record event
            event_record = {
                "event_id": event_id,
                "event_type": event_type,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "device_fingerprint": device_fingerprint,
                "timestamp": ts,
                "metadata": meta,
            }
            self._did_events[did].append(event_record)

            # Update device baseline
            if event_type in {"LOGIN", "WALLET_CREATED"} and not meta.get("suspicious", False):
                self._known_devices[did].add(device_fingerprint)

            # Calculate metrics
            summary = self._compute_summary_locked(did, ts, client_ip, device_fingerprint, meta)
            self._last_action_time[did] = ts

            # Update coordinates if provided in metadata
            lat = meta.get("latitude")
            lon = meta.get("longitude")
            if lat is not None and lon is not None:
                self._last_known_geo[did] = (float(lat), float(lon), client_ip)

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
        events = self._did_events[did]
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
        device_match = (device_fingerprint in known) if known else True

        # 5. Impossible Travel Geo distance
        geo_distance_km = 0.0
        cur_lat = metadata.get("latitude")
        cur_lon = metadata.get("longitude")
        if cur_lat is not None and cur_lon is not None and did in self._last_known_geo:
            prev_lat, prev_lon, _ = self._last_known_geo[did]
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
                del self._did_events[did]

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
