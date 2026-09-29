import json
import uuid
from typing import Any
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Request, Response, status
from app.core.config import IDENTITY_SERVICE_URL, FRAUD_SERVICE_URL, RECOVERY_SERVICE_URL

router = APIRouter(prefix="/api/v1", tags=["API Gateway Facade & Proxy"])

MAX_PAYLOAD_BYTES = 1024 * 1024  # 1 MB
MAX_JSON_DEPTH = 16
HTTP_413 = status.HTTP_413_CONTENT_TOO_LARGE


def compute_json_depth(val: Any, current_depth: int = 1) -> int:
    """Recursively computes the maximum nesting depth of a parsed JSON structure."""
    if isinstance(val, dict):
        if not val:
            return current_depth
        return max(compute_json_depth(v, current_depth + 1) for v in val.values())
    elif isinstance(val, (list, tuple)):
        if not val:
            return current_depth
        return max(compute_json_depth(item, current_depth + 1) for item in val)
    return current_depth


async def forward_request(target_url: str, request: Request) -> Response:
    """
    Forwards client request to target microservice with context propagation,
    payload size validation, JSON depth defense, and consistent error formatting.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    body = await request.body()

    # 1. Payload size validation
    if len(body) > MAX_PAYLOAD_BYTES:
        return Response(
            content=json.dumps({
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Request payload exceeds maximum allowed size of 1MB.",
                    "correlation_id": correlation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }).encode(),
            status_code=HTTP_413,
            media_type="application/json",
            headers={"X-Correlation-ID": correlation_id}
        )

    # 1.5. JSON Depth & UTF-8 Bomb Defense
    content_type = request.headers.get("content-type", "")
    if body and ("application/json" in content_type or "application/ld+json" in content_type):
        try:
            body_str = body.decode("utf-8")
            parsed_json = json.loads(body_str)
            depth = compute_json_depth(parsed_json)
            if depth > MAX_JSON_DEPTH:
                return Response(
                    content=json.dumps({
                        "error": {
                            "code": "JSON_DEPTH_EXCEEDED",
                            "message": f"JSON nesting depth of {depth} exceeds maximum allowable threshold ({MAX_JSON_DEPTH}).",
                            "correlation_id": correlation_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    }).encode(),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    media_type="application/json",
                    headers={"X-Correlation-ID": correlation_id}
                )
        except UnicodeDecodeError:
            return Response(
                content=json.dumps({
                    "error": {
                        "code": "INVALID_ENCODING",
                        "message": "Request body contains invalid UTF-8 byte sequences.",
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }).encode(),
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json",
                headers={"X-Correlation-ID": correlation_id}
            )
        except json.JSONDecodeError:
            # Let downstream microservice validation provide standard schema errors
            pass

    # 2. Context propagation headers
    headers = dict(request.headers)
    headers.pop("host", None)
    headers["x-correlation-id"] = correlation_id

    # Propagate authorization and identity context if present
    user_did = request.headers.get("x-user-did")
    if user_did:
        headers["x-user-did"] = user_did

    user_role = request.headers.get("x-user-role")
    if user_role:
        headers["x-user-role"] = user_role

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=headers
            )
            # Filter response headers
            excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
            forward_headers = {
                k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers
            }
            forward_headers["X-Correlation-ID"] = correlation_id

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=forward_headers,
                media_type=resp.headers.get("content-type")
            )
        except httpx.ConnectError:
            return Response(
                content=json.dumps({
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Target downstream microservice is unavailable or unreachable.",
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }).encode(),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
                headers={"X-Correlation-ID": correlation_id}
            )
        except Exception as exc:
            safe_msg = str(exc)
            if "://" in safe_msg and "@" in safe_msg:
                import re
                safe_msg = re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***REDACTED***@", safe_msg)
            return Response(
                content=json.dumps({
                    "error": {
                        "code": "BAD_GATEWAY",
                        "message": f"Proxy forwarding error: {safe_msg}",
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }).encode(),
                status_code=status.HTTP_502_BAD_GATEWAY,
                media_type="application/json",
                headers={"X-Correlation-ID": correlation_id}
            )

@router.get("/system/status", summary="Tüm mikroservislerin birleşik sağlık ve çalışma durumunu döner")
async def get_system_status():
    """
    Identity, Fraud, Recovery, Blockchain EVM Node ve Veritabanı durumunu sorgular.
    """
    services_status = {}
    blockchain_info = {"connected": False}
    database_info = {}

    async with httpx.AsyncClient(timeout=3.0) as client:
        # 1. Identity Service Check
        try:
            r = await client.get(f"{IDENTITY_SERVICE_URL}/health")
            services_status["identity_service"] = "HEALTHY" if r.status_code == 200 else "DEGRADED"
        except Exception:
            services_status["identity_service"] = "UNREACHABLE"

        # 2. Fraud Service Check
        try:
            r = await client.get(f"{FRAUD_SERVICE_URL}/health")
            services_status["fraud_service"] = "HEALTHY" if r.status_code == 200 else "DEGRADED"
        except Exception:
            services_status["fraud_service"] = "UNREACHABLE"

        # 3. Recovery Service Check
        try:
            r = await client.get(f"{RECOVERY_SERVICE_URL}/health")
            services_status["recovery_service"] = "HEALTHY" if r.status_code == 200 else "DEGRADED"
        except Exception:
            services_status["recovery_service"] = "UNREACHABLE"

        # 4. Blockchain Telemetry Check
        try:
            r = await client.get(f"{IDENTITY_SERVICE_URL}/api/v1/blockchain/status")
            if r.status_code == 200:
                blockchain_info = r.json()
                services_status["blockchain_node"] = "HEALTHY" if blockchain_info.get("connected") else "DEGRADED"
            else:
                r2 = await client.get(f"{IDENTITY_SERVICE_URL}/api/blockchain/status")
                if r2.status_code == 200:
                    blockchain_info = r2.json()
                    services_status["blockchain_node"] = "HEALTHY" if blockchain_info.get("connected") else "DEGRADED"
                else:
                    services_status["blockchain_node"] = "DEGRADED"
        except Exception:
            services_status["blockchain_node"] = "UNREACHABLE"

        # 5. Database Persistence Stats Check
        try:
            r = await client.get(f"{IDENTITY_SERVICE_URL}/api/database/stats")
            if r.status_code == 200:
                database_info = r.json()
        except Exception:
            pass

    all_healthy = all(v == "HEALTHY" for v in services_status.values())
    return {
        "gateway_status": "ONLINE",
        "system_health": "OPTIMAL" if all_healthy else "PARTIAL",
        "services": services_status,
        "blockchain": blockchain_info,
        "database": database_info
    }

# 1. Identity Service Proxy
@router.api_route("/identity/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_identity(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{IDENTITY_SERVICE_URL}/api/v1/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404 and not normalized.startswith("v1/"):
        fallback_target = f"{IDENTITY_SERVICE_URL}/api/{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp

# 1.05 Direct Audit Logs Proxy
@router.api_route("/audit/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_audit(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{IDENTITY_SERVICE_URL}/api/v1/audit/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404:
        fallback_target = f"{IDENTITY_SERVICE_URL}/api/database/audit_{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp

# 1.1 Direct OID4VCI & OID4VP Proxies
@router.api_route("/oid4vci/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_oid4vci(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{IDENTITY_SERVICE_URL}/api/v1/oid4vci/{normalized}"
    return await forward_request(target, request)

@router.api_route("/oid4vp/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_oid4vp(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{IDENTITY_SERVICE_URL}/api/v1/oid4vp/{normalized}"
    return await forward_request(target, request)

# 1.2 Direct Blockchain Anchoring Proxy
@router.api_route("/blockchain/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_blockchain(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{IDENTITY_SERVICE_URL}/api/v1/blockchain/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404:
        fallback_target = f"{IDENTITY_SERVICE_URL}/api/blockchain/{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp

# 2. Fraud Service Proxy
@router.api_route("/fraud/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_fraud(path: str, request: Request):
    normalized = path.lstrip("/")
    target = f"{FRAUD_SERVICE_URL}/api/v1/fraud/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404:
        fallback_target = f"{FRAUD_SERVICE_URL}/api/{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp

# 3. Recovery Service Proxy
@router.api_route("/recovery/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_recovery(path: str, request: Request):
    normalized = path.lstrip("/")
    # Handle /recovery/guardians routing directly to recovery service /api/v1/guardians
    if normalized.startswith("guardians"):
        target = f"{RECOVERY_SERVICE_URL}/api/v1/{normalized}"
    else:
        target = f"{RECOVERY_SERVICE_URL}/api/v1/recovery/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404:
        fallback_target = f"{RECOVERY_SERVICE_URL}/api/{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp

# 3.1 Direct Guardians Proxy
@router.api_route("/guardians", methods=["GET", "POST"])
@router.api_route("/guardians/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_guardians(request: Request, path: str = ""):
    normalized = path.lstrip("/")
    if normalized:
        target = f"{RECOVERY_SERVICE_URL}/api/v1/guardians/{normalized}"
    else:
        target = f"{RECOVERY_SERVICE_URL}/api/v1/guardians"
    return await forward_request(target, request)

