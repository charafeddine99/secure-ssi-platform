import json
import uuid
from typing import Any
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Request, Response, status
from app.core.config import CORS_ORIGINS, IDENTITY_SERVICE_URL, FRAUD_SERVICE_URL, RECOVERY_SERVICE_URL
from app.core.session import (
    CLIENT_HEADER,
    clear_session_cookie,
    csrf_rejection,
    is_web_client,
    session_token,
    set_session_cookie,
)

router = APIRouter(prefix="/api/v1", tags=["API Gateway Facade & Proxy"])

MAX_PAYLOAD_BYTES = 1024 * 1024  # 1 MB
MAX_JSON_DEPTH = 16
HTTP_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", getattr(status, "HTTP_413_REQUEST_ENTITY_TOO_LARGE", 413))


def error_response(code: str, message: str, status_code: int, correlation_id: str) -> Response:
    return Response(
        content=json.dumps({
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }).encode(),
        status_code=status_code,
        media_type="application/json",
        headers={"X-Correlation-ID": correlation_id}
    )


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
    # These headers are never trusted as identity assertions. Downstream
    # services authenticate the forwarded Bearer token with Identity Service.
    forbidden_context_headers = (
        "x-user-",
        "x-role",
        "x-organization-",
        "x-org-",
        "x-issuer-",
        "x-tenant-",
        "x-authenticated",
        "x-internal-",
    )
    # The browser session cookie never leaves the gateway; it becomes a Bearer
    # header only when the client did not send its own Authorization header.
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in {"host", "content-length", "cookie", CLIENT_HEADER}
        and not name.lower().startswith(forbidden_context_headers)
    }
    headers["x-correlation-id"] = correlation_id
    cookie_token = session_token(request)
    used_cookie = False
    if cookie_token and "authorization" not in {name.lower() for name in headers}:
        reason = csrf_rejection(request, CORS_ORIGINS)
        if reason:
            return error_response("CSRF_REJECTED", reason, status.HTTP_403_FORBIDDEN, correlation_id)
        headers["authorization"] = f"Bearer {cookie_token}"
        used_cookie = True

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

            response = Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=forward_headers,
                media_type=resp.headers.get("content-type")
            )
            if used_cookie and resp.status_code == status.HTTP_401_UNAUTHORIZED:
                clear_session_cookie(response)
            return response
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
        except Exception:
            # Never echo exception text: it can carry internal hostnames or URLs.
            return error_response(
                "BAD_GATEWAY",
                "The gateway could not forward the request.",
                status.HTTP_502_BAD_GATEWAY,
                correlation_id,
            )


def move_token_to_cookie(resp: Response) -> Response:
    """Sign-in for the web app: the token goes into the HttpOnly cookie only."""
    try:
        data = json.loads(resp.body)
    except (ValueError, TypeError):
        return resp
    if not isinstance(data, dict):
        return resp
    token = data.pop("accessToken", None) or data.pop("access_token", None)
    data.pop("access_token", None)
    if not isinstance(token, str) or not token:
        return resp
    expires_in = data.get("expiresIn", data.get("expires_in"))
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in {"content-length", "content-type"}}
    response = Response(
        content=json.dumps(data).encode(),
        status_code=resp.status_code,
        headers=headers,
        media_type="application/json",
    )
    response.headers["Cache-Control"] = "no-store"
    set_session_cookie(response, token, expires_in)
    return response


@router.get("/system/status", summary="Tüm mikroservislerin birleşik sağlık ve çalışma durumunu döner")
async def get_system_status():
    """
    Identity, Fraud, Recovery, Blockchain EVM Node ve Veritabanı durumunu sorgular.
    """
    services_status = {}
    blockchain_info = {"connected": False}
    database_info = {}
    database_healthy = False

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
            r = await client.get(f"{IDENTITY_SERVICE_URL}/api/v1/database/stats")
            if r.status_code == 200:
                database_info = r.json()
                database_healthy = database_info.get("status") == "SUCCESS"
            else:
                database_info = {"status": "UNAVAILABLE"}
        except Exception:
            database_info = {"status": "UNREACHABLE"}

    all_healthy = (
        all(v == "HEALTHY" for v in services_status.values())
        and database_healthy
    )
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
    if request.method == "POST" and is_web_client(request):
        if normalized == "auth/token" and resp.status_code == status.HTTP_200_OK:
            return move_token_to_cookie(resp)
        if normalized == "auth/revoke":
            clear_session_cookie(resp)
            return resp
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

