import gzip


class DecompressGZipMiddleware:
    """
    Decompresses request body if Content-Encoding: gzip is set,
    so JSONParser can parse it normally.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get('HTTP_CONTENT_ENCODING', '').lower() == 'gzip':
            try:
                request._body = gzip.decompress(request.body)
                request.META['HTTP_CONTENT_ENCODING'] = ''  # Prevent DRF confusion
            except Exception:
                # Let parser raise JSON error later if invalid
                pass
        return self.get_response(request)
