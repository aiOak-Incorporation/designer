import re
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Brand, Design, Techpack, Event, RejectedDesigner, Collection
from .serializers import BrandSerializer, EventSerializer, DesignSerializer, CollectionSerializer
from .forms import DesignerSignUpForm


# ---------- Helpers ----------
def natural_key(file):
    """If you use static folder listings elsewhere."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", file["name"])]
class AboutView(TemplateView):
    template_name = "redym_portfolio/about.html"

# ---------- API Permissions ----------
class ReadOnlyOrAuthWrite(permissions.BasePermission):
    """Allow reads for everyone; writes only for authenticated users."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

# ---------- API ViewSets ----------
class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [ReadOnlyOrAuthWrite]

import os
from django.views.generic import TemplateView
from django.templatetags.static import static
from .constants import COLLECTION_DETAILS
class CollectionsPageView(TemplateView):
    template_name = "redym_portfolio/collections.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ✅ Cover images mapping based on folder names from constants
        covers = {
            "collection1": "images/collection/covers/1.png",
            "collection2": "images/collection/covers/2.png",
            "collection3": "images/collection/covers/3.png",
            "collection4": "images/collection/covers/4.png",
            "collection5": "images/collection/covers/5.png",
            "collection6": "images/collection/covers/6.png",
        }

        collections = []
        for slug, details in COLLECTION_DETAILS.items():
            folder_name = details.get('folder', slug)  # Use folder mapping from constants
            collections.append({
                "slug": slug,
                "title": details["title"],
                "year": details["year"],
                "cover": covers.get(folder_name, "images/placehold.png"),
            })

        # Sort by year ascending
        collections = sorted(collections, key=lambda x: x["year"])
        ctx["collections"] = collections
        return ctx

# redym_portfolio/views.py
import os
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views import View
from .constants import COLLECTION_DETAILS  # ✅ import your constants


class CollectionDetailView(View):
    template_name = "redym_portfolio/collection_detail.html"

    def get(self, request, slug):
        # 1. Lookup metadata from constants
        collection = COLLECTION_DETAILS.get(slug)
        if not collection:
            raise Http404("Collection not found")

        # ✅ 2. Use folder mapping from constants
        folder_name = collection.get('folder', slug)  # Fallback to slug if no folder mapping
        rel_folder = f"images/collection/{folder_name}/"
        abs_folder = os.path.join(settings.BASE_DIR, "redym_portfolio", "static", rel_folder)

        if not os.path.isdir(abs_folder):
            raise Http404(f"Folder not found: {abs_folder}")

        # 3. Collect media files (sorted numerically if filenames are numbers)
        media = []
        for fname in sorted(os.listdir(abs_folder), key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else x.lower()):
            lower = fname.lower()
            url = f"/static/{rel_folder}{fname}".replace("\\", "/")
            if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                media.append({"url": url, "type": "image", "name": fname})
            elif lower.endswith((".mp4", ".webm", ".mov")):
                media.append({"url": url, "type": "video", "name": fname})

        return render(request, self.template_name, {
            "collection": collection,
            "media": media,
        })

from rest_framework import filters
class CollectionViewSet(viewsets.ModelViewSet):
    queryset = Collection.objects.filter(published=True)
    serializer_class = CollectionSerializer
    lookup_field = "slug"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "year"]
    ordering_fields = ["year", "title"]

    
class DesignViewSet(viewsets.ModelViewSet):
    queryset = Design.objects.filter(published=True)
    serializer_class = DesignSerializer
    permission_classes = [ReadOnlyOrAuthWrite]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "season", "description"]
    ordering_fields = ["year", "title", "created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [ReadOnlyOrAuthWrite]
    lookup_field = "slug"

import os
from django.conf import settings
from django.views.generic import TemplateView
from .models import Brand, Event


# ---------- Helper ----------
def list_static_media(folder_name):
    """
    Safely count files in your static/images subfolder.
    Example: list_static_media("images/tekpak")
    """
    base_path = os.path.join(settings.BASE_DIR, "redym_portfolio", "static", folder_name)
    if os.path.exists(base_path) and os.path.isdir(base_path):
        return [f for f in os.listdir(base_path) if not f.startswith(".")]
    return []


# ---------- Homepage ----------
class HomePageView(TemplateView):
    template_name = "redym_portfolio/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # First brand
        ctx["brand"] = Brand.objects.first()

        # Popup events
        ctx["popup_events"] = Event.objects.filter(is_popup=True)

        # Stats from static media folders
        ctx["stats"] = {
            "tekpaks": len(list_static_media("images/tekpak")),
            "events": len(list_static_media("images/event")),
            "designs": len(list_static_media("images/design")),
        }
        return ctx



class DesignListView(TemplateView):
    template_name = "redym_portfolio/designs.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["designs"] = Design.objects.filter(published=True)
        return ctx

class DesignDetailView(DetailView):
    model = Design
    template_name = "redym_portfolio/design_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

class EventListView(TemplateView):
    template_name = "redym_portfolio/events.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["events"] = Event.objects.all()
        return ctx

class EventDetailView(DetailView):
    model = Event
    template_name = "redym_portfolio/event_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

# ---------- Upload Design ----------
class DesignForm(forms.ModelForm):
    class Meta:
        model = Design
        fields = ["title", "season", "year", "cover_image", "description", "published"]

class TechpackForm(forms.ModelForm):
    class Meta:
        model = Techpack
        fields = ["fabric", "trims", "measurements", "bom_file", "notes"]

@login_required
def upload_design(request):
    if request.method == "POST":
        d_form = DesignForm(request.POST, request.FILES)
        t_form = TechpackForm(request.POST, request.FILES)
        if d_form.is_valid() and t_form.is_valid():
            design = d_form.save(commit=False)
            design.created_by = request.user
            design.save()

            techpack = t_form.save(commit=False)
            techpack.design = design
            techpack.save()

            messages.success(request, "Design & Techpack uploaded successfully.")
            return redirect("design_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        d_form = DesignForm()
        t_form = TechpackForm()
    return render(request, "redym_portfolio/upload_design.html", {"design_form": d_form, "techpack_form": t_form})

# ---------- Signup ----------
def signup_view(request):
    if request.method == "POST":
        form = DesignerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Enhanced admin notification email
            send_mail(
                subject="🎨 New Designer Signup - Approval Required | REDYM",
                message=f"""
A new designer has signed up for REDYM and is awaiting approval:

Designer Details:
• Username: {user.username}
• Email: {user.email}
• Registration Date: {user.date_joined.strftime('%B %d, %Y at %I:%M %p')}

Please review and approve this designer account in the admin panel:
{request.build_absolute_uri('/admin/pending-designers/')}

Best regards,
REDYM Platform
                """.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )

            messages.success(request, "🎉 Welcome to REDYM! Your account has been created successfully. An admin will review and approve it shortly.")
            return redirect("registration/login.html")
    else:
        form = DesignerSignUpForm()
    return render(request, "registration/signup.html", {"form": form})

# ---------- Designer Dashboard ----------
class DesignerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "redym_portfolio/designer_dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's designs
        user_designs = Design.objects.filter(published=True).order_by('-created_at')[:5]
        total_designs = Design.objects.filter(published=True).count()
        
        # Get recent collections
        recent_collections = Collection.objects.filter(published=True).order_by('-created_at')[:3]
        total_collections = Collection.objects.filter(published=True).count()
        
        # Get recent events
        recent_events = Event.objects.all().order_by('-created_at')[:3]
        total_events = Event.objects.count()
        
        context.update({
            'user_designs': user_designs,
            'total_designs': total_designs,
            'recent_collections': recent_collections,
            'total_collections': total_collections,
            'recent_events': recent_events,
            'total_events': total_events,
            'user': user,
        })
        return context

@login_required
def designer_designs_view(request):
    """View all designs for the logged-in designer"""
    designs = Design.objects.filter(published=True).order_by('-created_at')
    return render(request, 'redym_portfolio/designer_designs.html', {'designs': designs})

@login_required
def designer_design_create_view(request):
    """Create a new design"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        season = request.POST.get('season')
        year = request.POST.get('year', 2025)
        cover_image = request.FILES.get('cover_image')
        
        design = Design.objects.create(
            title=title,
            description=description,
            season=season,
            year=year,
            cover_image=cover_image,
            published=True
        )
        
        messages.success(request, f'Design "{title}" created successfully!')
        return redirect('designer_designs')
    
    return render(request, 'redym_portfolio/designer_design_form.html')

@login_required
def designer_design_edit_view(request, slug):
    """Edit an existing design"""
    design = get_object_or_404(Design, slug=slug)
    
    if request.method == 'POST':
        design.title = request.POST.get('title', design.title)
        design.description = request.POST.get('description', design.description)
        design.season = request.POST.get('season', design.season)
        design.year = request.POST.get('year', design.year)
        
        if request.FILES.get('cover_image'):
            design.cover_image = request.FILES.get('cover_image')
        
        design.save()
        messages.success(request, f'Design "{design.title}" updated successfully!')
        return redirect('designer_designs')
    
    return render(request, 'redym_portfolio/designer_design_form.html', {'design': design})

@login_required
def designer_design_delete_view(request, slug):
    """Delete a design"""
    design = get_object_or_404(Design, slug=slug)
    
    if request.method == 'POST':
        design_title = design.title
        design.delete()
        messages.success(request, f'Design "{design_title}" deleted successfully!')
        return redirect('designer_designs')
    
    return render(request, 'redym_portfolio/designer_design_confirm_delete.html', {'design': design})

# ---------- Designer Approval Flow ----------
@method_decorator([login_required, user_passes_test(lambda u: u.is_staff)], name="dispatch")
class PendingDesignersView(ListView):
    model = User
    template_name = "redym_portfolio/pending_designers.html"
    context_object_name = "pending_designers"

    def get_queryset(self):
        return User.objects.filter(is_active=False).order_by("-date_joined")

@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_designer(request, user_id):
    user = get_object_or_404(User, id=user_id, is_active=False)
    user.is_active = True
    user.save()
    messages.success(request, f"Designer {user.username} has been approved.")
    return redirect("pending_designers")

@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_designer(request, user_id):
    user = get_object_or_404(User, id=user_id, is_active=False)
    RejectedDesigner.objects.create(
        username=user.username,
        email=user.email,
        reason=request.GET.get("reason", "No reason provided")
    )
    email = user.email
    username = user.username
    user.delete()

    if email:
        send_mail(
            subject="Redym Designer Account Application",
            message=(
                f"Hello {username},\n\n"
                "We’re sorry, but your application for a Redym designer account has been declined.\n"
                "If you believe this is a mistake or would like to appeal, please contact our team.\n\n"
                "Best regards,\nTeam Redym"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )

    messages.warning(request, f"Designer {username} has been rejected and recorded.")
    return redirect("pending_designers")

@login_required
@user_passes_test(lambda u: u.is_staff)
def reinstate_designer(request, designer_id):
    rejected = get_object_or_404(RejectedDesigner, id=designer_id)

    if not User.objects.filter(username=rejected.username).exists():
        user = User.objects.create_user(
            username=rejected.username,
            email=rejected.email,
            password=User.objects.make_random_password()
        )
        user.is_active = False
        user.save()
        rejected.delete()

        messages.success(request, f"Designer {user.username} has been reinstated. You can now approve them.")
    else:
        messages.error(request, f"Cannot reinstate {rejected.username}: username already exists.")

    return redirect("pending_designers")

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
)
from io import BytesIO
import os
from django.conf import settings
from .models import Collection, Look


def generate_techpack(request, slug):
    # 1️⃣ Get collection and looks
    collection = get_object_or_404(Collection, slug=slug)
    looks = collection.looks.all()

    # 2️⃣ Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(
    buffer,
    pagesize=A4,
    topMargin=1 * inch,
    bottomMargin=0.8 * inch,
    leftMargin=0.7 * inch,
    rightMargin=0.7 * inch,
)

    styles = getSampleStyleSheet()
    story = []

    # 3️⃣ Logo path
    logo_path = os.path.join(settings.BASE_DIR, "redym_portfolio", "static", "images", "logo.png")

    # --- COVER PAGE ---
    if os.path.exists(logo_path):
        story.append(Image(logo_path, width=2.5 * inch, height=2.5 * inch))
        story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph(f"<b>{collection.name}</b>", styles["Title"]))
    story.append(Paragraph(f"Season: {collection.season or 'N/A'}", styles["Heading3"]))
    story.append(Paragraph(f"Year: {getattr(collection, 'year', 'N/A')}", styles["Normal"]))
    story.append(Paragraph(f"Total Looks: {looks.count()}", styles["Normal"]))

    if hasattr(collection, "designer") and collection.designer:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"<b>Designer:</b> {collection.designer}", styles["Normal"]))

    story.append(Spacer(1, 0.5 * inch))

    if getattr(collection, "cover_image", None):
        try:
            story.append(Image(collection.cover_image.path, width=5 * inch, height=5 * inch))
        except Exception:
            story.append(Paragraph("(Cover image unavailable)", styles["Italic"]))

    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Generated by Redym Portfolio — AIOak Inc.", styles["Italic"]))
    story.append(PageBreak())

    # --- LOOK DETAIL PAGES ---
    for i, look in enumerate(looks, start=1):
        story.append(Paragraph(f"<b>Look {i}: {look.title or f'Look {i}'}</b>", styles["Heading2"]))
        story.append(Spacer(1, 0.2 * inch))

        if getattr(look, "image", None):
            try:
                story.append(Image(look.image.path, width=4 * inch, height=4 * inch))
            except Exception:
                story.append(Paragraph("(Image not available)", styles["Italic"]))
        story.append(Spacer(1, 0.3 * inch))

        data = [
            ["Description", getattr(look, "description", "—")],
            ["Fabric", getattr(look, "fabric", "—")],
            ["Measurements", getattr(look, "measurements", "—")],
            ["Notes", getattr(look, "notes", "—")],
        ]
        table = Table(data, colWidths=[1.5 * inch, 4.5 * inch])
        table.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5 * inch))
        story.append(PageBreak())

    # --- SUMMARY PAGE ---
    story.append(Paragraph("<b>Fabric & Measurement Summary</b>", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    if looks.exists():
        summary_data = [["Look", "Fabric", "Swatch", "Measurements"]]

        # Fabric color mapping
        fabric_colors = {
            "cotton": colors.lightblue,
            "silk": colors.beige,
            "denim": colors.lightgrey,
            "linen": colors.whitesmoke,
            "wool": colors.azure,
            "satin": colors.mistyrose,
        }

        # Optional swatch image directory
        swatch_dir = os.path.join(settings.BASE_DIR, "redym_portfolio", "static", "swatches")

        for look in looks:
            fabric_name = (look.fabric or "—")
            # Check for a fabric swatch image
            swatch_img = None
            if fabric_name and fabric_name.strip() != "—":
                for key in fabric_colors.keys():
                    if key in fabric_name.lower():
                        candidate = os.path.join(swatch_dir, f"{key}.png")
                        if os.path.exists(candidate):
                            swatch_img = candidate
                            break

            # Prepare swatch cell
            if swatch_img:
                swatch_cell = Image(swatch_img, width=0.4 * inch, height=0.4 * inch)
            else:
                swatch_cell = "—"

            summary_data.append([
                look.title or f"Look {look.look_number}",
                fabric_name,
                swatch_cell,
                look.measurements or "—",
            ])

        summary_table = Table(summary_data, colWidths=[1.8 * inch, 2.2 * inch, 0.7 * inch, 2.3 * inch])

        # Base table style
        base_style = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.darkgrey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ])

        # Apply fabric background color for fabric cells
        for i, look in enumerate(looks, start=1):
            fabric = (look.fabric or "").lower()
            for key, color in fabric_colors.items():
                if key in fabric:
                    base_style.add("BACKGROUND", (1, i), (1, i), color)
                    break

        summary_table.setStyle(base_style)
        story.append(summary_table)
    else:
        story.append(Paragraph("No looks available to summarize.", styles["Normal"]))

    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("<i>End of Techpack</i>", styles["Italic"]))

    doc.build(
    story,
    onFirstPage=lambda canvas, doc: draw_header_footer(canvas, doc, collection),
    onLaterPages=lambda canvas, doc: draw_header_footer(canvas, doc, collection),
)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{collection.slug}_techpack.pdf"'
    return response

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

def draw_header_footer(canvas, doc, collection):
    """
    Draw header and footer for each page.
    """
    canvas.saveState()

    page_width, page_height = A4

    # --- HEADER ---
    header_y = page_height - 0.6 * inch

    # Line under header
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(0.7 * inch, header_y - 4, page_width - 0.7 * inch, header_y - 4)

    # Header text: Collection info
    canvas.setFont("Helvetica-Bold", 10)
    header_text = f"{collection.name} — {collection.season or 'Season'} {getattr(collection, 'year', '')}"
    canvas.setFillColor(colors.black)
    canvas.drawString(0.7 * inch, header_y + 2, header_text)

    # --- FOOTER ---
    footer_y = 0.5 * inch
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(0.7 * inch, footer_y + 8, page_width - 0.7 * inch, footer_y + 8)

    # Left footer: brand
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(0.7 * inch, footer_y - 2, "Redym Tech Pack")

    # Right footer: page number
    page_text = f"Page {doc.page}"
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(page_width - 0.7 * inch, footer_y - 2, page_text)

    canvas.restoreState()

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import os
from django.conf import settings


def draw_header_footer(canvas, doc, collection):
    """
    Draw header (with logo + collection info) and footer (brand + page number)
    for each page in the Tech Pack.
    """
    canvas.saveState()
    page_width, page_height = A4

    # --- HEADER ---
    header_y = page_height - 0.6 * inch
    logo_path = os.path.join(settings.BASE_DIR, "redym_portfolio", "static", "images", "logo.png")

    # Draw logo if exists
    if os.path.exists(logo_path):
        try:
            canvas.drawImage(logo_path, 0.7 * inch, header_y - 10, width=0.5 * inch, height=0.5 * inch, mask="auto")
        except Exception:
            pass

    # Header text (collection name + season/year)
    header_text = f"{collection.name} — {collection.season or 'Season'} {getattr(collection, 'year', '')}"
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(colors.black)
    canvas.drawString(1.4 * inch, header_y + 2, header_text)

    # Thin line below header
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(0.7 * inch, header_y - 4, page_width - 0.7 * inch, header_y - 4)

    # --- FOOTER ---
    footer_y = 0.5 * inch
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(0.7 * inch, footer_y + 8, page_width - 0.7 * inch, footer_y + 8)

    # Left footer: Brand
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(0.7 * inch, footer_y - 2, "Redym Tech Pack")

    # Right footer: Page number
    page_text = f"Page {doc.page}"
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(page_width - 0.7 * inch, footer_y - 2, page_text)

    canvas.restoreState()
