from django.contrib import admin

# Register your models here.
from .models import Blog

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    prepopulated_fields = {"slug": ("title",)}