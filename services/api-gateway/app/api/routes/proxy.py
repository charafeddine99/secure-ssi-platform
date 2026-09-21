import httpx
from fastapi import APIRouter, Request, Response, status
from app.core.config import IDENTITY_SERVICE_URL, FRAUD_SERVICE_URL, RECOVERY_SERVICE_URL

router = APIRouter(prefix="/api/v1", tags=["API Gateway Facade & Proxy"])

async def forward_request(target_url: str, request: Request) -> Response:
    """
    İstemciden gelen isteği hedef mikroservise yönlendirir ve cevabı döner.
    """
    body = await request.body()
    headers = dict(request.headers)
    # Host header'ı hedef servis için temizle
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=headers
            )
            # Response header'larını filtrele
            excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
            forward_headers = {
                k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers
            }
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=forward_headers,
                media_type=resp.headers.get("content-type")
            )
        except httpx.ConnectError:
            return Response(
                content=b'{"error": "Hedef mikroservise baglanilamadi"}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json"
            )
        except Exception as exc:
            return Response(
                content=f'{{"error": "Yonlendirme hatasi: {str(exc)}"}}'.encode(),
                status_code=status.HTTP_502_BAD_GATEWAY,
                media_type="application/json"
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
    target = f"{IDENTITY_SERVICE_URL}/api/v1/{path}"
    return await forward_request(target, request)

# 2. Fraud Service Proxy
@router.api_route("/fraud/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_fraud(path: str, request: Request):
    target = f"{FRAUD_SERVICE_URL}/api/v1/fraud/{path}"
    return await forward_request(target, request)

# 3. Recovery Service Proxy
@router.api_route("/recovery/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_recovery(path: str, request: Request):
    target = f"{RECOVERY_SERVICE_URL}/api/v1/recovery/{path}"
    return await forward_request(target, request)
