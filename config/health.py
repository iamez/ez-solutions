from health_check.views import HealthCheckView


class AppHealthCheckView(HealthCheckView):
    checks = (
        "health_check.checks.Cache",
        "health_check.checks.Database",
    )
