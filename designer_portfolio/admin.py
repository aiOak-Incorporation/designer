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


# ---------------- Designer Profile ----------------
@admin.register(m.DesignerProfile)
class DesignerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialization",
        "location",
        "portfolio_template",
        "created_at",
    )
    list_filter = ("portfolio_template", "available_for_collaborations")
    search_fields = (
        "user__username",
        "user__email",
        "specialization",
        "location",
    )
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "user",
        "bio",
        "profile_image",
        "portfolio_website",
        "instagram_handle",
        "linkedin_profile",
        "years_of_experience",
        "specialization",
        "education",
        "location",
        "available_for_collaborations",
        "contact_email",
        "portfolio_template",
        "created_at",
        "updated_at",
    )


@admin.register(m.DesignerConversation)
class DesignerConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "participant_a",
        "participant_b",
        "created_at",
        "updated_at",
        "message_count",
    )
    search_fields = (
        "participant_a__username",
        "participant_a__email",
        "participant_b__username",
        "participant_b__email",
    )
    readonly_fields = ("created_at", "updated_at")

    def message_count(self, obj):
        return obj.messages.count()


@admin.register(m.DesignerMessage)
class DesignerMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "short_content", "created_at", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("content", "sender__username", "sender__email")
    readonly_fields = ("created_at", "updated_at")

    def short_content(self, obj):
        return obj.content[:75] + ("..." if len(obj.content) > 75 else "")
    short_content.short_description = "Content"
