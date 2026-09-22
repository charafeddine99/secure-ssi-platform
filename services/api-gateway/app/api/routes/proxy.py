import json
import uuid
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Request, Response, status
from app.core.config import IDENTITY_SERVICE_URL, FRAUD_SERVICE_URL, RECOVERY_SERVICE_URL

router = APIRouter(prefix="/api/v1", tags=["API Gateway Facade & Proxy"])

MAX_PAYLOAD_BYTES = 1024 * 1024  # 1 MB

async def forward_request(target_url: str, request: Request) -> Response:
    """
    Forwards client request to target microservice with context propagation,
    payload size validation, and consistent error formatting.
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
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            media_type="application/json",
            headers={"X-Correlation-ID": correlation_id}
        )

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
            return Response(
                content=json.dumps({
                    "error": {
                        "code": "BAD_GATEWAY",
                        "message": f"Proxy forwarding error: {str(exc)}",
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
    Identity, Fraud ve Recovery servislerinin anlık durumunu sorgular.
    """
    services_status = {}
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

    all_healthy = all(v == "HEALTHY" for v in services_status.values())
    return {
        "gateway_status": "ONLINE",
        "system_health": "OPTIMAL" if all_healthy else "PARTIAL",
        "services": services_status
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
    target = f"{RECOVERY_SERVICE_URL}/api/v1/recovery/{normalized}"
    resp = await forward_request(target, request)
    if resp.status_code == 404:
        fallback_target = f"{RECOVERY_SERVICE_URL}/api/{normalized}"
        fallback_resp = await forward_request(fallback_target, request)
        if fallback_resp.status_code != 404:
            return fallback_resp
    return resp
