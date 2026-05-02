import logging

logger = logging.getLogger("requests")

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if request.user.is_authenticated else "Anonymous"
        logger.info(f"{user} -> {request.method} {request.path}")
        return self.get_response(request)