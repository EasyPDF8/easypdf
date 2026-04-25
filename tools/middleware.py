from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from django.shortcuts import redirect

class RateLimitMiddleware(MiddlewareMixin):
    """Automatically rate limit all POST requests"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method == 'POST':
            # Skip rate limiting for these specific views
            skip_views = ['contact_submit', 'save_todos', 'load_todos']
            
            if view_func.__name__ in skip_views:
                return None
            
            # Check if request was rate limited
            limited = getattr(request, 'limited', False)
            
            if limited:
                messages.error(request, "Too many requests. Please try again later.")
                raise PermissionDenied("Rate limit exceeded")
        
        return None


class FileCleanupMiddleware(MiddlewareMixin):
    """Clean up old files on each request"""
    
    def process_request(self, request):
        from .views import cleanup_old_files
        cleanup_old_files()
        return None