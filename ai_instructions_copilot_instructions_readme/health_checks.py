"""
Tech-IT Solutions - System Health Checks
Monitoring endpoints for system health, database, cache, and external services
"""

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import psutil
import time
from datetime import datetime


class HealthCheckView(View):
    """
    Basic health check endpoint
    Returns 200 if system is operational
    """

    def get(self, request):
        return HttpResponse("OK", status=200)


class DetailedHealthCheckView(View):
    """
    Detailed health check with component status
    Checks: Database, Cache, Disk, Memory, CPU
    """

    def get(self, request):
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        # Check database
        db_status = self._check_database()
        health_status["checks"]["database"] = db_status

        # Check cache
        cache_status = self._check_cache()
        health_status["checks"]["cache"] = cache_status

        # Check disk space
        disk_status = self._check_disk()
        health_status["checks"]["disk"] = disk_status

        # Check memory
        memory_status = self._check_memory()
        health_status["checks"]["memory"] = memory_status

        # Check CPU
        cpu_status = self._check_cpu()
        health_status["checks"]["cpu"] = cpu_status

        # Determine overall status
        if any(
            check["status"] == "unhealthy" for check in health_status["checks"].values()
        ):
            health_status["status"] = "unhealthy"
            status_code = 503
        elif any(
            check["status"] == "degraded" for check in health_status["checks"].values()
        ):
            health_status["status"] = "degraded"
            status_code = 200
        else:
            status_code = 200

        return JsonResponse(health_status, status=status_code)

    def _check_database(self):
        """Check database connectivity and response time"""
        try:
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            response_time = (time.time() - start) * 1000  # Convert to ms

            return {
                "status": "healthy" if response_time < 100 else "degraded",
                "response_time_ms": round(response_time, 2),
                "message": "Database is responding",
            }
        except Exception as e:
            return {"status": "unhealthy", "message": f"Database error: {str(e)}"}

    def _check_cache(self):
        """Check cache connectivity"""
        try:
            test_key = "health_check_test"
            test_value = "test"
            cache.set(test_key, test_value, 10)
            retrieved = cache.get(test_key)

            if retrieved == test_value:
                return {"status": "healthy", "message": "Cache is working"}
            else:
                return {"status": "degraded", "message": "Cache read/write mismatch"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Cache error: {str(e)}"}

    def _check_disk(self):
        """Check disk space"""
        try:
            disk = psutil.disk_usage("/")
            percent_used = disk.percent

            if percent_used < 80:
                status = "healthy"
            elif percent_used < 90:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "percent_used": percent_used,
                "free_gb": round(disk.free / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            }
        except Exception as e:
            return {"status": "unknown", "message": f"Disk check error: {str(e)}"}

    def _check_memory(self):
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            percent_used = memory.percent

            if percent_used < 80:
                status = "healthy"
            elif percent_used < 90:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "percent_used": percent_used,
                "available_gb": round(memory.available / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2),
            }
        except Exception as e:
            return {"status": "unknown", "message": f"Memory check error: {str(e)}"}

    def _check_cpu(self):
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)

            if cpu_percent < 70:
                status = "healthy"
            elif cpu_percent < 85:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "percent_used": cpu_percent,
                "cpu_count": psutil.cpu_count(),
            }
        except Exception as e:
            return {"status": "unknown", "message": f"CPU check error: {str(e)}"}


class ReadinessCheckView(View):
    """
    Readiness check - is the application ready to serve traffic?
    Used by load balancers and orchestration tools
    """

    def get(self, request):
        try:
            # Check if database migrations are up to date
            from django.db.migrations.executor import MigrationExecutor
            from django.db import connections

            executor = MigrationExecutor(connections["default"])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

            if plan:
                return JsonResponse(
                    {"status": "not_ready", "message": "Pending database migrations"},
                    status=503,
                )

            # Check database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            return JsonResponse(
                {"status": "ready", "message": "Application is ready"}, status=200
            )

        except Exception as e:
            return JsonResponse({"status": "not_ready", "message": str(e)}, status=503)


class LivenessCheckView(View):
    """
    Liveness check - is the application alive?
    Used to detect if the application needs to be restarted
    """

    def get(self, request):
        # Simple check that the application is running
        return HttpResponse("OK", status=200)


class MetricsView(View):
    """
    Prometheus-compatible metrics endpoint
    """

    def get(self, request):
        metrics = []

        # Database connection count
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )
                db_connections = cursor.fetchone()[0]
                metrics.append(f"db_connections_total {db_connections}")
        except:
            pass

        # System metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            metrics.append(f"system_cpu_percent {cpu_percent}")
            metrics.append(f"system_memory_percent {memory.percent}")
            metrics.append(f"system_disk_percent {disk.percent}")
        except:
            pass

        return HttpResponse("\n".join(metrics), content_type="text/plain")
