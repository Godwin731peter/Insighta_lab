import logging
import time

logger = logging.getLogger("insighta.requests")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = (time.time() - start) * 1000

        user = getattr(request, "user", None)
        username = (
            user.username if user and user.is_authenticated else "anonymous"
        )

        logger.info(
            f"{request.method} {request.path} | "
            f"status={response.status_code} | "
            f"user={username} | "
            f"duration={duration:.2f}ms | "
            f"ip={request.META.get('REMOTE_ADDR')}"
        )
        return response