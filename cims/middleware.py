print("DEBUG: middleware.py loaded")  # diagnostic print

class RemoteUserHeaderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print("DEBUG: RemoteUserHeaderMiddleware __call__ triggered")  # optional
        if 'HTTP_REMOTE_USER' in request.META:
            request.META['REMOTE_USER'] = request.META['HTTP_REMOTE_USER']
        return self.get_response(request)
