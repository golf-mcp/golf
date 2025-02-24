import logging
from datetime import datetime, timezone
from typing import Dict, Any
import psutil
import os

from ..core.config import get_settings
from ..db.session import check_database_health
from ..db.redis import check_redis_health

logger = logging.getLogger(__name__)

class HealthCheck:
    def __init__(self):
        self.settings = get_settings()
        self.version = "1.0.0"
        self.process = psutil.Process(os.getpid())

    async def check_process_health(self) -> Dict[str, Any]:
        """Check process-level health metrics"""
        try:
            memory = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()
            
            memory_percent = (memory.rss / psutil.virtual_memory().total) * 100
            
            is_healthy = (
                memory_percent < self.settings.HEALTH_MEMORY_THRESHOLD and 
                cpu_percent < self.settings.HEALTH_CPU_THRESHOLD and 
                self.process.is_running()
            )
            
            return {
                "healthy": is_healthy,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "memory_percent": round(memory_percent, 2),
                    "cpu_percent": round(cpu_percent, 2),
                    "thresholds": {
                        "memory": self.settings.HEALTH_MEMORY_THRESHOLD,
                        "cpu": self.settings.HEALTH_CPU_THRESHOLD
                    }
                }
            }
        except Exception as e:
            logger.error(f"Process health check failed: {str(e)}")
            return {
                "healthy": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks"""
        db_health = await check_database_health()
        redis_health = await check_redis_health()
        
        overall_status = "healthy"
        if db_health["status"] != "healthy" or redis_health["status"] != "healthy":
            overall_status = "unhealthy"
            
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self.version,
            "components": {
                "database": db_health,
                "redis": redis_health
            }
        } 