from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ...core.health import HealthCheck

router = APIRouter(prefix="/health", tags=["health"])
health_checker = HealthCheck()

@router.get("", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy"}

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness():
    """Kubernetes liveness probe - checks process health"""
    health_status = await health_checker.check_process_health()
    if not health_status["healthy"]:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "details": health_status}
        )
    return health_status

@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness():
    """Kubernetes readiness probe - checks all components"""
    health_status = await health_checker.check_all()
    if health_status["status"] != "healthy":
        return {"status": "unhealthy", "details": health_status}, status.HTTP_503_SERVICE_UNAVAILABLE
    return health_status 