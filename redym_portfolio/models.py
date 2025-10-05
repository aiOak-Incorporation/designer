from django.db import models
from django.utils.text import slugify


# ---------------- Base Timestamp ----------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------- Brand ----------------
class Brand(TimeStampedModel):
    name = models.CharField(max_length=100, default="redym")
    tagline = models.CharField(max_length=160, blank=True)
    logo = models.ImageField(upload_to="brand/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#000000")  # black
    secondary_color = models.CharField(max_length=7, default="#FFFFFF")  # white
    accent_color = models.CharField(max_length=7, default="#9CA3AF")    # neutral gray
    primary_font = models.CharField(max_length=100, default="Playfair Display")
    secondary_font = models.CharField(max_length=100, default="Inter")

    def __str__(self):
        return self.name


from django.db import models
from django.utils.text import slugify
class Collection(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    year = models.PositiveIntegerField(default=2024)
    season = models.CharField(max_length=100, blank=True, null=True)
    cover_image = models.ImageField(upload_to="collections/covers/", blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    #designer fields
    designer = models.CharField(max_length=100, blank=True, null=True)  # ✅ Add this
    cover_image = models.ImageField(upload_to='collection_covers/', blank=True, null=True)


    class Meta:
        ordering = ["-year", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.name}-{self.year}")
            slug = base_slug
            counter = 1
            while Collection.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} – {self.year}"


class CollectionImage(models.Model):
    collection = models.ForeignKey(Collection, related_name="gallery", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="collections/gallery/")
    caption = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Image for {self.collection.name} ({self.collection.year})"

class Look(models.Model):
    collection = models.ForeignKey(Collection, related_name="looks", on_delete=models.CASCADE)
    look_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="collections/looks/", blank=True, null=True)
    fabric = models.CharField(max_length=200, blank=True, null=True)
    measurements = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["look_number"]
        unique_together = [("collection", "look_number")]

    def __str__(self):
        return f"{self.collection.name} – Look {self.look_number}"


# ---------------- Design ----------------
class Design(TimeStampedModel):
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    season = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(default=2025)
    cover_image = models.ImageField(upload_to="designs/covers/", blank=True, null=True)
    description = models.TextField(blank=True)
    published = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.title}-{self.year}")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.year})"


# ---------------- Techpack ----------------
class Techpack(TimeStampedModel):
    design = models.OneToOneField(Design, related_name="techpack", on_delete=models.CASCADE)
    fabric = models.CharField(max_length=255, blank=True)
    trims = models.TextField(blank=True)
    measurements = models.TextField(blank=True)
    bom_file = models.FileField(upload_to="techpacks/bom/", blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Techpack for {self.design.title}"


# ---------------- Design Images ----------------
class DesignImage(TimeStampedModel):
    design = models.ForeignKey(Design, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="designs/gallery/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"Image for {self.design.title}"


# ---------------- Event ----------------
class Event(TimeStampedModel):
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="events/covers/", blank=True, null=True)
    event_date = models.DateField(blank=True, null=True)
    is_popup = models.BooleanField(default=False)  # popup event toggle
    popup_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-event_date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# ---------------- Event Images ----------------
class EventImage(TimeStampedModel):
    event = models.ForeignKey(Event, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="events/images/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"Image for {self.event.title}"

# redym_portfolio/models.py

from django.db import models

class RejectedDesigner(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    reason = models.TextField(blank=True, null=True)
    rejected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} (Rejected on {self.rejected_at:%Y-%m-%d})"
