from django.contrib import admin
from django.utils.html import format_html
from . import models as m


# ---------------- Brand ----------------
@admin.register(m.Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "tagline", "primary_color", "updated_at")
    search_fields = ("name", "tagline")


# ---------------- Techpack (inline for Design) ----------------
class TechpackInline(admin.StackedInline):
    model = m.Techpack
    extra = 0
    min_num = 1
    max_num = 1  # Only one techpack per design


# ---------------- Design Images ----------------
class DesignImageInline(admin.TabularInline):
    model = m.DesignImage
    extra = 1
    fields = ("preview", "image", "caption", "order")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px; height:80px; object-fit:cover; border-radius:6px;" />',
                obj.image.url,
            )
        return "-"
    preview.short_description = "Preview"


# ---------------- Design ----------------
@admin.register(m.Design)
class DesignAdmin(admin.ModelAdmin):
    list_display = ("title", "year", "season", "published", "cover_preview", "created_at")
    list_filter = ("published", "year", "season")
    search_fields = ("title", "description", "season")
    prepopulated_fields = {"slug": ("title", "year")}
    inlines = [TechpackInline, DesignImageInline]

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="width:80px; height:80px; object-fit:cover; border-radius:6px;" />',
                obj.cover_image.url,
            )
        return "-"
    cover_preview.short_description = "Cover"


# ---------------- Event Images ----------------
class EventImageInline(admin.TabularInline):
    model = m.EventImage
    extra = 1
    fields = ("preview", "image", "caption", "order")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px; height:80px; object-fit:cover; border-radius:6px;" />',
                obj.image.url,
            )
        return "-"
    preview.short_description = "Preview"


# ---------------- Event ----------------
@admin.register(m.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_date", "is_popup", "popup_order", "cover_preview", "created_at")
    list_filter = ("is_popup", "event_date")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [EventImageInline]

    def cover_preview(self, obj):
        if obj.cover:
            return format_html(
                '<img src="{}" style="width:80px; height:80px; object-fit:cover; border-radius:6px;" />',
                obj.cover.url,
            )
        return "-"
    cover_preview.short_description = "Cover"
