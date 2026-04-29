# ===============================
# ALL IMPORTS FOR EasyPDF
# ===============================

# Standard Library
import os
import re
import time
import uuid
import json
import zipfile
import base64
import math
import warnings
from datetime import date, datetime, timedelta
from io import BytesIO

# Third Party
from PIL import Image, ImageDraw, ImageFont, ExifTags
from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = 50_000_000

# PDF Processing
from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF
from pdf2image import convert_from_path

# PDF Generation (ReportLab)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, 
    Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# Django Core
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from django.http import HttpResponse


import mimetypes
import re



def is_total_size_safe(files, max_mb=300):
    if not files:
        return True
    total_size = sum(f.size for f in files)
    return total_size <= max_mb * 1024 * 1024

MAX_FILES_PER_REQUEST = 50  # you can adjust (20 is safe)

def validate_file_count(files, limit=MAX_FILES_PER_REQUEST):
    if len(files) > limit:
        return False, f"You can upload maximum {limit} files at a time."
    return True, ""

def validate_image_size(img):
    try:
        img.seek(0)
        image = Image.open(img)

        if image.width < 10 or image.height < 10:
            return False

        if image.width > 8000 or image.height > 8000:
            return False

        ratio = max(image.width, image.height) / min(image.width, image.height)
        if ratio > 100:
            return False

        return True
    except:
        return False

from django.utils.text import get_valid_filename

def secure_filename(name):
    name = get_valid_filename(name)
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    return name[:100]  # limit length

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/gif', 'image/tiff']

def is_safe_image(file):
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)
        return file.content_type in ALLOWED_IMAGE_TYPES
    except:
        return False

# Rate Limiting
from django_ratelimit.decorators import ratelimit

# Document Conversion (Optional - with error handling)
try:
    from docx import Document
except ImportError:
    Document = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import tabula
except ImportError:
    tabula = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

# QR Code Generation (Optional)
try:
    import qrcode
except ImportError:
    qrcode = None


MAX_PDF_PAGES = 100

def validate_pdf_pages(file_path):
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        if total_pages > MAX_PDF_PAGES:
            return False, total_pages

        return True, total_pages

    except:
        return False, 0
    

def is_valid_pdf(file):
    try:
        file.seek(0)

        if file.read(5) != b'%PDF-':
            return False

        file.seek(0)

        # try parsing
        PdfReader(file)

        file.seek(0)
        return True

    except:
        return False
# ===============================
# RATE LIMIT DECORATOR (CUSTOM)
# ===============================

from functools import wraps

def rate_limit(rate='100/h'):
    """Custom rate limit decorator for upload views"""
    def decorator(view_func):
        @ratelimit(key='ip', rate=rate, method='POST')
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if getattr(request, 'limited', False):
                messages.error(request, f"Rate limit exceeded ({rate}). Please try again later.")
                return redirect(request.META.get('HTTP_REFERER') or 'home')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ===============================
# SIMPLE CLOUD LIMITS
# ===============================

MAX_FILE_SIZE = 300 * 1024 * 1024   # 300MB
MAX_FILES_PER_DAY = 100

def check_limit(request, file_size):
    today = datetime.now().date()

    usage = request.session.get('usage', {
        'date': str(today),
        'files': 0,
        'size': 0
    })

    # Reset daily usage
    if usage['date'] != str(today):
        usage = {
            'date': str(today),
            'files': 0,
            'size': 0
        }

    # File size check (200MB)
    if file_size > MAX_FILE_SIZE:
        return False, "File too large. Max allowed is 200MB."

    # Daily file count check (100 files)
    if usage['files'] >= MAX_FILES_PER_DAY:
        return False, "Daily limit reached (100 files per day)."

    return True, ""


def update_usage(request, file_size, file_count=1):
    today = datetime.now().date()

    usage = request.session.get('usage', {
        'date': str(today),
        'files': 0,
        'size': 0
    })

    # Reset if new day
    if usage['date'] != str(today):
        usage = {
            'date': str(today),
            'files': 0,
            'size': 0
        }

    usage['files'] += file_count
    usage['size'] += file_size

    request.session['usage'] = usage
    request.session.modified = True


# ===============================
# CLEANUP & HOME
# ===============================

def cleanup_old_files():
    """Delete files older than CLEANUP_MINUTES minutes"""
    cleanup_minutes = getattr(settings, 'CLEANUP_MINUTES', 5)
    cleanup_seconds = cleanup_minutes * 60
    now = time.time()
    
    if not os.path.exists(settings.MEDIA_ROOT):
        return

    for f in os.listdir(settings.MEDIA_ROOT):
        path = os.path.join(settings.MEDIA_ROOT, f)
        try:
            if os.path.isfile(path) and os.stat(path).st_mtime < now - cleanup_seconds:
                os.remove(path)
        except Exception as e:
            print("Cleanup error:", e)


def home(request):
    if 'my_files' not in request.session:
        request.session['my_files'] = []
    
    cleanup_old_files()
    return render(request, 'index.html')


# ===============================
# SECURE DOWNLOAD
# ===============================

def download_file(request, filename):

    # 🔐 Filename validation
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise Http404("Invalid filename")

    # 🔐 Session authorization
    allowed_files = request.session.get('my_files', [])
    if filename not in allowed_files:
        raise Http404("Unauthorized access")

    # 🔐 Secure path
    full_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, filename))

    if not full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404("Invalid file path")

    # 🔐 File exists
    if not os.path.exists(full_path):
        raise Http404("File expired or not found")

    # ✅ SAFE FILE HANDLING (FIX)
    file = open(full_path, 'rb')
    response = FileResponse(file, as_attachment=True)

    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response

# ===============================
# PDF TOOLS
# ===============================

# 1.1 MERGE PDF
@rate_limit('100/h')
def merge_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    if request.method == 'POST' and request.FILES.getlist('pdfs'):
        pdf_files = request.FILES.getlist('pdfs')

        if not pdf_files:
            messages.error(request, "No PDFs uploaded")
            return redirect('merge_pdf')

        if not is_total_size_safe(pdf_files):
            messages.error(request, "Total upload size too large")
            return redirect('merge_pdf')

        total_size = sum(pdf.size for pdf in pdf_files)

        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'merge_pdf.html')

        fs = FileSystemStorage()
        writer = PdfWriter()
        merged_files = []
        session_id = str(uuid.uuid4())[:8]

        try:
            for pdf in pdf_files:
                if not pdf.name.lower().endswith('.pdf'):
                    messages.error(request, f"{pdf.name} is not a PDF file")
                    raise Exception("Invalid file type")

                safe_name = secure_filename(pdf.name)
                temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
                temp_path = fs.save(temp_name, pdf)
                merged_files.append(temp_path)

                is_valid, total_pages = validate_pdf_pages(fs.path(temp_path))
                if not is_valid:
                    messages.error(request, f"{pdf.name} has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
                    raise Exception("Page limit exceeded")
                
                reader = PdfReader(fs.path(temp_path))


                if len(writer.pages) + len(reader.pages) > 500:
                    messages.error(request, "Total pages cannot exceed 500")
                    raise Exception("Page limit exceeded")

                for page in reader.pages:
                    writer.add_page(page)

            timestamp = int(time.time())
            output_filename = f"easypdf_merged_{timestamp}.pdf"
            output_path = fs.path(output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, len(pdf_files))

            return render(request, 'merge_result.html', {
                'filename': output_filename,
                'page_count': len(writer.pages)
            })

        except Exception as e:
            messages.error(request, f"Merge failed: {str(e)[:200]}")
            return render(request, 'merge_pdf.html')

        finally:
            for f in merged_files:
                try:
                    os.remove(fs.path(f))
                except:
                    pass

    return render(request, 'merge_pdf.html')

@rate_limit('100/h')
def split_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')

        if not pdf_file:
            return render(request, 'split_pdf.html', {'error': 'Please select a PDF file first'})

        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF is too large (max 300MB)")
            return redirect('split_pdf')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF file")
            return render(request, 'split_pdf.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            return render(request, 'split_pdf.html', {'error': msg})

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        filename = f"{session_id}_{int(time.time())}_{safe_name}"

        saved_path = fs.save(filename, pdf_file)
        filepath = fs.path(saved_path)

        try:
            is_valid, total_pages = validate_pdf_pages(filepath)

            if not is_valid:
                messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
                return render(request, 'split_pdf.html')
            reader = PdfReader(filepath)

            mode = request.POST.get('mode')
            output_files = []

            if mode == 'fixed':
                step = request.POST.get('fixed_pages')

                if not step:
                    return render(request, 'split_pdf.html', {'error': 'Enter pages per split'})

                try:
                    step = int(step)
                except:
                    return render(request, 'split_pdf.html', {'error': 'Invalid number'})

                if step < 1:
                    return render(request, 'split_pdf.html', {'error': 'Minimum is 1 page'})

                step = min(step, total_pages)

                split_counter = 1
                for i in range(0, total_pages, step):
                    writer = PdfWriter()
                    end_page = min(i + step, total_pages)

                    for j in range(i, end_page):
                        writer.add_page(reader.pages[j])

                    name = f"easypdf_split_{session_id}_{split_counter}_{int(time.time())}.pdf"
                    path = os.path.join(settings.MEDIA_ROOT, name)

                    with open(path, 'wb') as f:
                        writer.write(f)

                    output_files.append({
                        'filename': name,
                        'pages': f"{i+1}-{end_page}"
                    })

                    split_counter += 1

            else:
                ranges_raw = request.POST.get('ranges', '').strip()

                if not ranges_raw:
                    return render(request, 'split_pdf.html', {'error': 'Enter page ranges'})

                ranges = []

                for part in ranges_raw.split(','):
                    part = part.strip()

                    if '-' in part:
                        try:
                            start, end = map(int, part.split('-'))
                            if start < 1 or end > total_pages or start > end:
                                return render(request, 'split_pdf.html', {'error': f'Invalid range: {part}'})
                            ranges.append((start - 1, end))
                        except:
                            return render(request, 'split_pdf.html', {'error': f'Invalid format: {part}'})
                    else:
                        try:
                            page = int(part)
                            if page < 1 or page > total_pages:
                                return render(request, 'split_pdf.html', {'error': f'Invalid page: {part}'})
                            ranges.append((page - 1, page))
                        except:
                            return render(request, 'split_pdf.html', {'error': f'Invalid page: {part}'})

                for idx, (start, end) in enumerate(ranges):
                    writer = PdfWriter()

                    for i in range(start, end):
                        writer.add_page(reader.pages[i])

                    name = f"easypdf_split_{session_id}_range_{idx+1}_{int(time.time())}.pdf"
                    path = os.path.join(settings.MEDIA_ROOT, name)

                    with open(path, 'wb') as f:
                        writer.write(f)

                    output_files.append({
                        'filename': name,
                        'pages': f"{start+1}-{end}"
                    })

            if not output_files:
                return render(request, 'split_pdf.html', {'error': 'No files created'})

            request.session['my_files'] = request.session.get('my_files', [])
            for f in output_files:
                request.session['my_files'].append(f['filename'])

            request.session['split_result'] = {
                'files': output_files,
                'total_splits': len(output_files),
                'original_pages': total_pages
            }

            request.session.modified = True

            total_output_size = sum(os.path.getsize(fs.path(f['filename'])) for f in output_files)
            update_usage(request, total_output_size, len(output_files))

            return redirect('split_result')

        except Exception as e:
            return render(request, 'split_pdf.html', {
                'error': f'Error: {str(e)[:200]}'
            })

        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass

    return render(request, 'split_pdf.html')


def split_result(request):
    data = request.session.get('split_result')

    if not data:
        return redirect('split_pdf')

    return render(request, 'split_result.html', {
        'files': data.get('files', []),
        'total_splits': data.get('total_splits', 0),
        'original_pages': data.get('original_pages', 0),
    })


@rate_limit('100/h')
def rotate_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf')

        if not pdf_file:
            messages.error(request, "No file uploaded")
            return render(request, 'rotate_pdf.html')

        rotation = request.POST.get('angle', '90')

        # Safe rotation validation
        try:
            rotation_angle = int(rotation)
            if rotation_angle not in [90, 180, 270]:
                raise ValueError()
        except:
            messages.error(request, "Invalid rotation value")
            return render(request, 'rotate_pdf.html')

        # Size check
        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF is too large (max 300MB)")
            return redirect('rotate_pdf')

        # Validate PDF
        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF file")
            return render(request, 'rotate_pdf.html')

        # Usage check
        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'rotate_pdf.html')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"

        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        is_valid, total_pages = validate_pdf_pages(pdf_path)

        if not is_valid:
            messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
            return render(request, 'rotate_pdf.html')
        
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            for page in reader.pages:
                page.rotate(rotation_angle)
                writer.add_page(page)
            
            timestamp = int(time.time())
            output_filename = f"easypdf_rotated_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            # Save file to session
            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            update_usage(request, pdf_file.size, 1)

            return render(request, 'rotate_pdf_result.html', {
                'filename': output_filename,
                'rotation': rotation_angle
            })

        except Exception as e:
            messages.error(request, f"Rotation failed: {str(e)[:200]}")
            return render(request, 'rotate_pdf.html')

        finally:
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except:
                pass

    return render(request, 'rotate_pdf.html')

def rotate_pdf_result(request):
    data = request.session.get('rotate_pdf_result')

    if not data:
        messages.warning(request, "No file found. Please try again.")
        return redirect('rotate_pdf')

    return render(request, 'rotate_pdf_result.html', data)


# 1.5 PDF TO JPG
@rate_limit('50/h')
def convert_to_jpg(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']

        # ✅ Size check
        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF is too large (max 300MB)")
            return redirect('convert_to_jpg')

        # ✅ Validate PDF
        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF file")
            return render(request, 'pdf_to_jpg.html')

        # ✅ Usage check
        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'pdf_to_jpg.html')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]
        timestamp = int(time.time())

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{timestamp}_{safe_name}"
        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        try:
            # ✅ Page validation (ONLY THIS is needed)
            is_valid, total_pages = validate_pdf_pages(pdf_path)
            if not is_valid:
                messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
                return render(request, 'pdf_to_jpg.html')

            # ✅ Convert PDF to images
            images = convert_from_path(pdf_path, dpi=150)

            img_files_paths = []
            img_filenames = []

            for i, img in enumerate(images):
                img_name = f"easypdf_page_{i+1}_{session_id}_{timestamp}.jpg"
                img_path = fs.path(img_name)

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                img.save(img_path, "JPEG", quality=85, optimize=True)

                img_files_paths.append(img_path)
                img_filenames.append(img_name)

            # ✅ ZIP creation
            zip_filename = f"easypdf_pdf_to_jpg_{session_id}_{timestamp}.zip"
            zip_path = fs.path(zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f_path, f_name in zip(img_files_paths, img_filenames):
                    zipf.write(f_path, arcname=f_name)

            # ✅ Session save
            request.session['my_files'] = request.session.get('my_files', []) + [zip_filename]
            request.session.modified = True

            request.session['jpg_result'] = {
                'zip_file': zip_filename,
                'page_count': total_pages,
                'zip_size': round(os.path.getsize(zip_path) / (1024 * 1024), 2)
            }

            # ✅ Usage update
            update_usage(request, os.path.getsize(zip_path), 1)

            return redirect('pdf_to_jpg_result')

        except Exception as e:
            print("PDF to JPG error:", e)
            messages.error(request, "Failed to process PDF")
            return render(request, 'pdf_to_jpg.html')

        finally:
            # ✅ Cleanup
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            for img_p in img_files_paths:
                if os.path.exists(img_p):
                    os.remove(img_p)

    return render(request, 'pdf_to_jpg.html')


def pdf_to_jpg_result(request):
    context = request.session.get('jpg_result')

    if not context:
        return redirect('convert_to_jpg')

    return render(request, 'pdf_to_jpg_result.html', context)


# 1.6 JPG TO PDF
@rate_limit('100/h')
def jpg_to_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST' and request.FILES.getlist('images'):
        images = request.FILES.getlist('images')

        # ✅ File count validation
        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('jpg_to_pdf')

        # ✅ Total size validation
        if not is_total_size_safe(images):
            messages.error(request, "Total upload size too large")
            return redirect('jpg_to_pdf')

        total_size = sum(img.size for img in images)

        # ✅ Usage limit check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'jpg_to_pdf.html')

        image_list = []
        valid_count = 0

        try:
            # ✅ Process images (NO temp files, fast)
            for img in images:
                if not is_safe_image(img):
                    continue

                if not validate_image_size(img):
                    continue

                img.seek(0)
                pil_image = Image.open(img)

                # Convert to RGB (important for PDF)
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                image_list.append(pil_image)
                valid_count += 1

            if valid_count == 0:
                messages.error(request, "No valid images uploaded")
                return render(request, 'jpg_to_pdf.html')

            # ✅ Timestamp filename
            timestamp = int(time.time())
            output_filename = f"easypdf_jpg_to_pdf_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            # ✅ Save all images into single PDF
            image_list[0].save(
                output_path,
                save_all=True,
                append_images=image_list[1:]
            )

            # ✅ Save to session
            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            request.session['jpg_to_pdf_result'] = {
                'filename': output_filename,
                'page_count': valid_count
            }

            update_usage(request, os.path.getsize(output_path), valid_count)

            return redirect('jpg_to_pdf_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return render(request, 'jpg_to_pdf.html')

    return render(request, 'jpg_to_pdf.html')


def jpg_to_pdf_result(request):
    data = request.session.get('jpg_to_pdf_result')

    if not data:
        return redirect('jpg_to_pdf')

    return render(request, 'jpg_to_pdf_result.html', data)


# 1.7 PROTECT PDF
@rate_limit('100/h')
def protect_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']
        password = request.POST.get('password', '')

        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF too large")
            return redirect('protect_pdf')

        if not password:
            messages.error(request, "Enter password")
            return render(request, 'protect_pdf.html')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF")
            return render(request, 'protect_pdf.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'protect_pdf.html')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        is_valid, total_pages = validate_pdf_pages(pdf_path)

        if not is_valid:
            messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
            return render(request, 'protect_pdf.html')

        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            writer.encrypt(password)

            timestamp = int(time.time())
            output_filename = f"easypdf_protected_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            request.session['protect_pdf_result'] = {
                'filename': output_filename
            }

            update_usage(request, pdf_file.size, 1)

            return redirect('protect_pdf_result')

        except Exception as e:
            messages.error(request, f"Protection failed: {str(e)[:200]}")
            return render(request, 'protect_pdf.html')

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, 'protect_pdf.html')


def protect_pdf_result(request):
    data = request.session.get('protect_pdf_result')

    if not data:
        return redirect('protect_pdf')

    return render(request, 'protect_pdf_result.html', data)


# 1.8 PDF TO TEXT
@rate_limit('100/h')
def pdf_to_text(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']

        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF too large")
            return redirect('pdf_to_text')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF")
            return render(request, 'pdf_to_text.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'pdf_to_text.html')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        is_valid, total_pages = validate_pdf_pages(pdf_path)

        if not is_valid:
            messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
            return render(request, 'pdf_to_text.html')

        try:
            reader = PdfReader(pdf_path)
            extracted_text = ""

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n\n"

            timestamp = int(time.time())
            output_filename = f"easypdf_pdf_to_text_{timestamp}.txt"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            request.session['pdf_to_text_result'] = {
                'filename': output_filename,
                'text_preview': extracted_text[:500]
            }

            update_usage(request, os.path.getsize(output_path), 1)

            return redirect('pdf_to_text_result')

        except Exception as e:
            messages.error(request, f"Error: {str(e)[:200]}")
            return redirect('pdf_to_text')

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, 'pdf_to_text.html')


def pdf_to_text_result(request):
    data = request.session.get('pdf_to_text_result')

    if not data:
        return redirect('pdf_to_text')

    return render(request, 'pdf_to_text_result.html', data)


# 1.9 REMOVE PAGES
@rate_limit('100/h')
def remove_pages(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    if request.method == "POST":
        pdf_file = request.FILES.get('pdf')
        pages_to_remove_raw = request.POST.get('pages_to_remove')

        if not pdf_file or not pages_to_remove_raw:
            return render(request, 'remove_pages.html', {"error": "Missing data"})

        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF too large (max 300MB)")
            return redirect('remove_pages')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF")
            return render(request, 'remove_pages.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'remove_pages.html')

        try:
            pages_to_remove = sorted(set(int(p.strip()) for p in pages_to_remove_raw.split(',')))
        except:
            return render(request, 'remove_pages.html', {"error": "Invalid page numbers format"})

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        is_valid, total_pages = validate_pdf_pages(pdf_path)

        if not is_valid:
            messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
            return render(request, 'remove_pages.html')

        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            pages_to_remove = [p - 1 for p in pages_to_remove if 1 <= p <= total_pages]

            for i in range(total_pages):
                if i not in pages_to_remove:
                    writer.add_page(reader.pages[i])

            timestamp = int(time.time())
            output_filename = f"easypdf_removed_pages_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            request.session['remove_pages_result'] = {
                'file': output_filename
            }

            update_usage(request, os.path.getsize(output_path), 1)

            return redirect('remove_pages_result')

        except Exception as e:
            messages.error(request, f"Error: {str(e)[:200]}")
            return render(request, 'remove_pages.html')

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, 'remove_pages.html')


def remove_pages_result(request):
    result = request.session.get('remove_pages_result')

    if not result:
        return redirect('remove_pages')

    return render(request, 'remove_pages_result.html', {
        'file': result['file']
    })


# 1.10 ADD PAGE NUMBERS
@rate_limit('100/h')
def add_page_numbers(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        pdf_file = request.FILES.get('pdf')

        if not pdf_file:
            return HttpResponseBadRequest("No PDF uploaded")

        if pdf_file.size > 300 * 1024 * 1024:
            messages.error(request, "PDF too large")
            return redirect('add_page_numbers')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF")
            return render(request, 'add_page_numbers.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, 'add_page_numbers.html')

        try:
            start_number = int(request.POST.get('start_number') or 1)
        except:
            start_number = 1

        position = request.POST.get('position') or "bottom-center"

        try:
            from_page = int(request.POST.get('from_page') or 1)
        except:
            from_page = 1

        try:
            to_page = int(request.POST.get('to_page') or 999999)
        except:
            to_page = 999999

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, pdf_file)
        pdf_path = fs.path(saved_path)

        is_valid, total_pages = validate_pdf_pages(pdf_path)
        if not is_valid:
            messages.error(request, f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}.")
            return render(request, 'add_page_numbers.html')

        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            for i, page in enumerate(reader.pages):
                page_index = i + 1

                if page_index < from_page or page_index > to_page:
                    writer.add_page(page)
                    continue

                packet = BytesIO()

                width = float(page.mediabox.width)
                height = float(page.mediabox.height)

                can = canvas.Canvas(packet, pagesize=(width, height))
                can.setFont("Helvetica", 12)

                page_number = str(start_number + (page_index - from_page))

                if position == "top-left":
                    x, y = 30, height - 30
                elif position == "top-center":
                    x, y = width / 2, height - 30
                elif position == "top-right":
                    x, y = width - 60, height - 30
                elif position == "bottom-left":
                    x, y = 30, 20
                elif position == "bottom-center":
                    x, y = width / 2, 20
                elif position == "bottom-right":
                    x, y = width - 60, 20
                else:
                    x, y = width / 2, 20

                can.drawString(x, y, page_number)
                can.save()

                packet.seek(0)
                overlay = PdfReader(packet)
                page.merge_page(overlay.pages[0])

                writer.add_page(page)

            timestamp = int(time.time())
            output_filename = f"easypdf_page_numbers_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, "wb") as f:
                writer.write(f)

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            request.session['add_page_numbers_result'] = {
                'filename': output_filename
            }

            update_usage(request, os.path.getsize(output_path), 1)

            return redirect('add_page_numbers_result')

        except Exception as e:
            messages.error(request, f"Error: {str(e)[:200]}")
            return render(request, 'add_page_numbers.html')

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, "add_page_numbers.html")


def add_page_numbers_result(request):
    data = request.session.get('add_page_numbers_result')

    if not data:
        return redirect('add_page_numbers')

    return render(request, 'add_page_numbers_result.html', data)

# ===============================
# IMAGE TOOLS
# ===============================

# ===============================
# COMPRESS PAGE
# ===============================
def compress_page(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    return render(request, 'compress_page.html')


@rate_limit('100/h')
def compress_preview(request):
    if request.method == 'POST' and request.FILES.getlist('images'):
        images = request.FILES.getlist('images')

        # File count validation
        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('compress_page')

        # Total size validation
        if not is_total_size_safe(images):
            messages.error(request, "Total upload size too large")
            return redirect('compress_page')

        total_size = sum(img.size for img in images)

        # Usage check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('compress_page')

        fs = FileSystemStorage()
        uploaded_files = []
        session_id = str(uuid.uuid4())[:8]

        for img in images:
            if not is_safe_image(img):
                continue

            if not validate_image_size(img):
                continue

            try:
                image = Image.open(img)
                image.verify()
                img.seek(0)   # IMPORTANT FIX
            except:
                continue

            safe_name = secure_filename(img.name)
            unique_name = f"{session_id}_{int(time.time())}_{safe_name}"

            saved_name = fs.save(unique_name, img)
            uploaded_files.append(saved_name)

        if not uploaded_files:
            messages.error(request, "No valid images uploaded")
            return redirect('compress_page')

        request.session['uploaded_files'] = uploaded_files
        request.session.modified = True

        update_usage(request, total_size, len(uploaded_files))

        return render(request, 'compress_preview.html', {
            'files': uploaded_files,
            'MEDIA_URL': settings.MEDIA_URL
        })

    return redirect('compress_page')

@rate_limit('100/h')
def compress_images(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    files = request.session.get('uploaded_files', [])

    if not files:
        messages.error(request, "No files found")
        return redirect('compress_page')

    fs = FileSystemStorage()
    compressed_files = []
    total_original = 0
    total_compressed = 0

    try:
        quality = int(request.POST.get('quality', 85))
        quality = max(65, min(quality, 95))
    except:
        quality = 85

    quality_map = {
            95: {'jpeg': 88, 'max_dim': 2048},
            85: {'jpeg': 78, 'max_dim': 1920},
            75: {'jpeg': 68, 'max_dim': 1680},
            65: {'jpeg': 58, 'max_dim': 1440},
        }

    settings_q = quality_map.get(quality, quality_map[85])

    for f in files:
        try:
            path = fs.path(f)

            if not os.path.exists(path):
                continue

            original_size = os.path.getsize(path)
            total_original += original_size

            with Image.open(path) as img:

                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # ✅ Resize if too large
                if img.width > settings_q['max_dim'] or img.height > settings_q['max_dim']:
                    ratio = min(
                        settings_q['max_dim'] / img.width,
                        settings_q['max_dim'] / img.height
                    )
                    img = img.resize(
                        (int(img.width * ratio), int(img.height * ratio)),
                        Image.Resampling.LANCZOS
                    )

                timestamp = int(time.time())
                output_name = f"easypdf_compressed_{timestamp}.jpg"
                output_path = fs.path(output_name)

                img.save(
                output_path,
                'JPEG',
                quality=settings_q['jpeg'],
                optimize=True,
                progressive=True
            )

            compressed_size = os.path.getsize(output_path)

            # If compressed file is bigger than original, keep original
            if compressed_size >= original_size:
                os.remove(output_path)   # delete bigger compressed file
                total_compressed += original_size
                compressed_files.append(f)   # keep original uploaded file
            else:
                total_compressed += compressed_size
                compressed_files.append(output_name)

        except:
            continue

    if not compressed_files:
        messages.error(request, "Compression failed")
        return redirect('compress_page')

    request.session['my_files'] = request.session.get('my_files', []) + compressed_files
    request.session.modified = True

    saved_percentage = int(((total_original - total_compressed) / total_original) * 100) if total_original else 0

    # ✅ ZIP if multiple files
    if len(compressed_files) > 1:
        zip_name = f"compressed_{uuid.uuid4().hex}.zip"
        zip_path = fs.path(zip_name)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in compressed_files:
                zipf.write(fs.path(file), arcname=file)

        request.session['my_files'].append(zip_name)

        context = {
            'zip_file': zip_name,
            'is_single': False
        }
    else:
        context = {
            'single_file': compressed_files[0],
            'is_single': True
        }

    context.update({
        'saved': saved_percentage,
        'original_mb': round(total_original / (1024 * 1024), 2),
        'compressed_mb': round(total_compressed / (1024 * 1024), 2),
    })

    update_usage(request, total_original, len(compressed_files))

    return render(request, 'compress_result.html', context)

# ===============================
# IMAGE FORMAT CONVERSION
# ===============================

def convert_image_format(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    return render(request, 'convert_image_format.html')


@rate_limit('100/h')
def process_image_conversion(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method != 'POST':
        return redirect('convert_image_format')

    images = request.FILES.getlist('images')

    if not images:
        messages.error(request, "No images selected")
        return redirect('convert_image_format')

    # ✅ File count validation (use your common function)
    is_valid, msg = validate_file_count(images)
    if not is_valid:
        messages.error(request, msg)
        return redirect('convert_image_format')

    # ✅ Total size validation
    if not is_total_size_safe(images):
        messages.error(request, "Total upload too large")
        return redirect('convert_image_format')

    total_size = sum(img.size for img in images)

    # ✅ Usage check
    allowed, msg = check_limit(request, total_size)
    if not allowed:
        messages.error(request, msg)
        return redirect('convert_image_format')

    target_format = request.POST.get('format', 'png').lower()

    # ✅ Fix: define allowed formats
    allowed_formats = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff']
    if target_format not in allowed_formats:
        messages.error(request, "Unsupported format selected")
        return redirect('convert_image_format')

    fs = FileSystemStorage()
    output_files = []
    session_id = str(uuid.uuid4())[:8]

    for img in images:
        if not is_safe_image(img):
            continue

        if not validate_image_size(img):
            continue

        try:
            image = Image.open(img)
            image.verify()
        except:
            continue

        safe_name = secure_filename(img.name)

        temp = fs.save(f"tmp_{uuid.uuid4().hex}_{safe_name}", img)
        temp_path = fs.path(temp)

        try:
            with Image.open(temp_path) as im:

                # ✅ JPG needs RGB
                if target_format in ['jpg', 'jpeg']:
                    im = im.convert('RGB')

                timestamp = int(time.time())

                # ❗ FIX: you used wrong variable (output_format ❌)
                output_name = f"easypdf_converted_{session_id}_{timestamp}.{target_format}"
                output_path = fs.path(output_name)

                format_map = {
                    "jpg": "JPEG",
                    "jpeg": "JPEG",
                    "png": "PNG",
                    "webp": "WEBP",
                    "bmp": "BMP",
                    "tiff": "TIFF"
                }

                save_format = format_map.get(target_format, "PNG")
                im.save(output_path, save_format, optimize=True)

                output_files.append(output_name)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    if not output_files:
        messages.error(request, "Conversion failed")
        return redirect('convert_image_format')

    # ✅ ZIP handling
    if len(output_files) > 1:
        zip_name = f"converted_{uuid.uuid4().hex}.zip"
        zip_path = fs.path(zip_name)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in output_files:
                zipf.write(fs.path(f), arcname=f)

        result = {"is_zip": True, "zip_file": zip_name}
    else:
        result = {"is_zip": False, "single_file": output_files[0]}

    # ✅ Save session
    request.session['my_files'] = request.session.get('my_files', [])
    if result.get("is_zip"):
        request.session['my_files'].append(result["zip_file"])
    else:
        request.session['my_files'].append(result["single_file"])

    request.session['convert_result'] = result
    request.session.modified = True

    # ✅ Usage update
    output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
    update_usage(request, output_size, len(output_files))

    return redirect('convert_image_format_result')


def convert_image_format_result(request):
    data = request.session.get('convert_result')
    if not data:
        return redirect('convert_image_format')

    return render(request, 'convert_image_format_result.html', data)


# ===============================
# RESIZE IMAGES
# ===============================
@rate_limit('100/h')
def resize_images(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST' and request.FILES.getlist('images'):
        images = request.FILES.getlist('images')

        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('resize_images')

        if not is_total_size_safe(images):
            messages.error(request, "Total upload too large")
            return redirect('resize_images')

        total_size = sum(img.size for img in images)

        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('resize_images')

        try:
            resize_data = json.loads(request.POST.get('resize_data', '[]'))
        except:
            messages.error(request, "Invalid resize data")
            return redirect('resize_images')

        # FIX: allow auto-fill instead of blocking
        if len(resize_data) < len(images):
            for i in range(len(images) - len(resize_data)):
                resize_data.append(None)

        fs = FileSystemStorage()
        output_files = []
        session_id = str(uuid.uuid4())[:8]

        format_map = {
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "png": "PNG",
            "webp": "WEBP",
            "bmp": "BMP",
            "tiff": "TIFF"
        }

        for i, img in enumerate(images):
            try:
                if not is_safe_image(img) or not validate_image_size(img):
                    continue
                
                # SAVE FIRST (IMPORTANT FIX)
                temp = fs.save(f"tmp_{uuid.uuid4().hex}", img)
                path = fs.path(temp)
        
                data = resize_data[i] if i < len(resize_data) else None
        
                # FIX: fallback uses correct path now
                if not data or not data.get('width') or not data.get('height'):
                    with Image.open(path) as im:
                        data = {
                            "width": im.width,
                            "height": im.height
                        }
        
                w = int(data.get('width', 0))
                h = int(data.get('height', 0))
        
                if w < 10 or h < 10 or w > 8000 or h > 8000:
                    if os.path.exists(path):
                        os.remove(path)
                    continue
                
                with Image.open(path) as im:
                    im = im.convert('RGB')
                    im = im.resize((w, h), Image.Resampling.LANCZOS)
        
                    ext = img.name.split('.')[-1].lower()
                    fmt = format_map.get(ext, "JPEG")
        
                    filename = f"easypdf_resized_{session_id}_{i}.{ext}"
                    output_path = fs.path(filename)
        
                    im.save(output_path, fmt, quality=90)
        
                    output_files.append(filename)
        
                if os.path.exists(path):
                    os.remove(path)
        
            except Exception as e:
                print("Resize error:", e)

        if not output_files:
            messages.error(request, "Resize failed")
            return redirect('resize_images')

        request.session['my_files'] = request.session.get('my_files', []) + output_files

        request.session['resize_result'] = {
            'files': output_files,
            'file_count': len(output_files),
            'zip_file': None,
            'single_file': output_files[0] if len(output_files) == 1 else None
        }

        request.session.modified = True

        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('resize_images_result')

    return render(request, 'resize_images.html')

def resize_images_result(request):
    data = request.session.get('resize_result')

    if not data:
        return redirect('resize_images')

    files = data.get('files', [])

    return render(request, 'resize_images_result.html', {
        'zip_file': data.get('zip_file', ''),
        'single_file': data.get('single_file', ''),
        'file_count': len(files)
    })

# ===============================
# CROP IMAGES
# ===============================
@rate_limit('100/h')
def crop_images(request):
    try:
        cleanup_old_files()
    except:
        pass

    if request.method == 'POST' and request.FILES.getlist('images'):

        images = request.FILES.getlist('images')

        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('crop_images')

        if not is_total_size_safe(images):
            messages.error(request, "Total upload too large")
            return redirect('crop_images')

        total_size = sum(img.size for img in images)

        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('crop_images')

        try:
            crop_data = json.loads(request.POST.get('crop_data', '[]'))
        except:
            messages.error(request, "Invalid crop data")
            return redirect('crop_images')

        fs = FileSystemStorage()
        output_files = []
        session_id = uuid.uuid4().hex[:8]

        for i, img in enumerate(images):

            try:
                if i >= len(crop_data):
                    continue

                data = crop_data[i]

                x = int(data.get('x', 0))
                y = int(data.get('y', 0))
                w = int(data.get('width', 0))
                h = int(data.get('height', 0))

                if w <= 0 or h <= 0:
                    continue

                image = Image.open(img)

                if image.mode != "RGB":
                    image = image.convert("RGB")

                if x < 0 or y < 0:
                    continue

                if x + w > image.width:
                    w = image.width - x

                if y + h > image.height:
                    h = image.height - y

                cropped = image.crop((x, y, x + w, y + h))

                output_name = f"cropped_{session_id}_{i}.jpg"
                output_path = fs.path(output_name)

                cropped.save(
                    output_path,
                    "JPEG",
                    quality=90,
                    optimize=True
                )

                output_files.append(output_name)

            except Exception as e:
                print("Crop Error:", e)
                continue

        if not output_files:
            messages.error(request, "Cropping failed")
            return redirect('crop_images')

        request.session['my_files'] = request.session.get('my_files', []) + output_files

        if len(output_files) > 1:

            zip_name = f"cropped_{uuid.uuid4().hex}.zip"
            zip_path = fs.path(zip_name)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in output_files:
                    zipf.write(fs.path(file), arcname=file)

            request.session['my_files'].append(zip_name)

            request.session['crop_result'] = {
                'files': output_files,
                'count': len(output_files),
                'file_url': zip_name,
                'is_zip': True
            }

        else:
            request.session['crop_result'] = {
                'files': output_files,
                'count': 1,
                'file_url': output_files[0],
                'is_zip': False
            }

        request.session.modified = True

        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('crop_images_result')

    return render(request, 'crop_images.html')

def crop_images_result(request):
    data = request.session.get('crop_result')

    if not data:
        return redirect('crop_images')

    return render(request, 'crop_images_result.html', data)



# ===============================
# 2.5 ROTATE IMAGES
# ===============================
@rate_limit('100/h')
def rotate_images(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        files = request.FILES.getlist('images')

        if not files:
            messages.error(request, "No images uploaded")
            return redirect('rotate_images')

        # ✅ File count validation
        is_valid, msg = validate_file_count(files)
        if not is_valid:
            messages.error(request, msg)
            return redirect('rotate_images')

        # ✅ Total size validation
        if not is_total_size_safe(files):
            messages.error(request, "Total upload too large")
            return redirect('rotate_images')

        total_size = sum(f.size for f in files)

        # ✅ Usage check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('rotate_images')

        # ✅ Angle validation
        try:
            angle = int(request.POST.get('angle', 90))
            if angle not in [90, 180, 270]:
                angle = 90
        except:
            angle = 90

        fs = FileSystemStorage()
        output_files = []
        session_id = str(uuid.uuid4())[:8]

        for i, file in enumerate(files):
            try:
                if not is_safe_image(file):
                    continue

                if not validate_image_size(file):
                    continue

                with Image.open(file) as img:

                    if angle == 90:
                        img = img.rotate(-90, expand=True)
                    elif angle == 180:
                        img = img.rotate(180, expand=True)
                    elif angle == 270:
                        img = img.rotate(-270, expand=True)

                    img = img.convert("RGB")

                    timestamp = int(time.time())
                    filename = f"easypdf_rotated_{session_id}_{timestamp}_{i}.jpg"
                    path = fs.path(filename)

                    img.save(path, "JPEG", quality=90, optimize=True)

                    output_files.append(filename)

            except:
                continue

        if not output_files:
            messages.error(request, "Processing failed")
            return redirect('rotate_images')

        # ✅ Save files to session
        request.session['my_files'] = request.session.get('my_files', []) + output_files

        # ✅ ZIP if multiple files
        if len(output_files) > 1:
            zip_name = f"rotated_{uuid.uuid4().hex}.zip"
            zip_path = fs.path(zip_name)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in output_files:
                    zipf.write(fs.path(f), arcname=f)

            request.session['my_files'].append(zip_name)

            result = {
                'zip_file': zip_name,
                'file_count': len(output_files),
                'is_zip': True
            }
        else:
            result = {
                'single_file': output_files[0],
                'file_count': 1,
                'is_zip': False
            }

        request.session['rotate_result'] = result
        request.session.modified = True

        # ✅ Usage update
        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('rotate_images_result')

    return render(request, "rotate_images.html")


def rotate_images_result(request):
    data = request.session.get('rotate_result')
    if not data:
        return redirect('rotate_images')

    return render(request, 'rotate_images_result.html', data)


# ===============================
# 2.6 FLIP IMAGES
# ===============================
@rate_limit('100/h')
def flip_images(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST':
        files = request.FILES.getlist('images')

        if not files:
            messages.error(request, "No files selected")
            return redirect('flip_images')

        # ✅ File count validation
        is_valid, msg = validate_file_count(files)
        if not is_valid:
            messages.error(request, msg)
            return redirect('flip_images')

        # ✅ Total size validation
        if not is_total_size_safe(files):
            messages.error(request, "Total upload too large")
            return redirect('flip_images')

        total_size = sum(f.size for f in files)

        # ✅ Usage check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('flip_images')

        # ✅ Direction validation
        direction = request.POST.get('direction', 'horizontal')
        if direction not in ['horizontal', 'vertical']:
            direction = 'horizontal'

        fs = FileSystemStorage()
        output_files = []
        session_id = str(uuid.uuid4())[:8]

        for i, file in enumerate(files):
            try:
                if not is_safe_image(file):
                    continue

                if not validate_image_size(file):
                    continue

                with Image.open(file) as img:

                    if direction == 'horizontal':
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    else:
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)

                    img = img.convert("RGB")

                    timestamp = int(time.time())
                    filename = f"easypdf_flip_{session_id}_{timestamp}_{i}.jpg"
                    path = fs.path(filename)

                    img.save(path, "JPEG", quality=90, optimize=True)
                    output_files.append(filename)

            except:
                continue

        if not output_files:
            messages.error(request, "Processing failed")
            return redirect('flip_images')

        # ✅ Save files to session
        request.session['my_files'] = request.session.get('my_files', []) + output_files

        # ✅ ZIP if multiple files
        if len(output_files) > 1:
            zip_name = f"flip_{uuid.uuid4().hex}.zip"
            zip_path = fs.path(zip_name)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in output_files:
                    zipf.write(fs.path(f), arcname=f)

            request.session['my_files'].append(zip_name)

            result = {
                'zip_file': zip_name,
                'file_count': len(output_files),
                'is_zip': True
            }
        else:
            result = {
                'single_file': output_files[0],
                'file_count': 1,
                'is_zip': False
            }

        request.session['flip_result'] = result
        request.session.modified = True

        # ✅ Usage update
        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('flip_images_result')

    return render(request, 'flip_images.html')


def flip_images_result(request):
    data = request.session.get('flip_result')
    if not data:
        return redirect('flip_images')

    return render(request, 'flip_images_result.html', data)


# ===============================
# 2.7 ADD BORDER
# ===============================
@rate_limit('100/h')
def add_border(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST':
        images = request.FILES.getlist('images')

        if not images:
            messages.error(request, "No images uploaded")
            return redirect('add_border')

        # ✅ File count validation
        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('add_border')

        # ✅ Total size validation
        if not is_total_size_safe(images):
            messages.error(request, "Total upload too large")
            return redirect('add_border')

        total_size = sum(img.size for img in images)

        # ✅ Usage check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('add_border')

        # ✅ Border size validation
        try:
            border_size = int(request.POST.get('border_size', 10))
            if border_size < 1 or border_size > 500:
                border_size = 10
        except:
            border_size = 10

        # ✅ Color validation
        color = request.POST.get('border_color', '#000000')
        try:
            rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        except:
            rgb = (0, 0, 0)

        fs = FileSystemStorage()
        output_files = []
        session_id = str(uuid.uuid4())[:8]

        for i, img_file in enumerate(images):
            try:
                if not is_safe_image(img_file):
                    continue

                if not validate_image_size(img_file):
                    continue

                with Image.open(img_file) as img:
                    img = img.convert("RGB")

                    new_img = Image.new(
                        "RGB",
                        (img.width + border_size * 2, img.height + border_size * 2),
                        rgb
                    )
                    new_img.paste(img, (border_size, border_size))

                    timestamp = int(time.time())
                    filename = f"easypdf_border_{session_id}_{timestamp}_{i}.jpg"
                    output_path = fs.path(filename)

                    new_img.save(output_path, "JPEG", quality=90, optimize=True)

                    output_files.append(filename)

            except:
                continue

        if not output_files:
            messages.error(request, "Processing failed")
            return redirect('add_border')

        # ✅ Save files to session
        request.session['my_files'] = request.session.get('my_files', []) + output_files

        # ✅ ZIP if multiple files
        if len(output_files) > 1:
            zip_name = f"border_{uuid.uuid4().hex}.zip"
            zip_path = fs.path(zip_name)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in output_files:
                    zipf.write(fs.path(f), arcname=f)

            request.session['my_files'].append(zip_name)

            result = {
                'zip_file': zip_name,
                'file_count': len(output_files),
                'is_zip': True
            }
        else:
            result = {
                'single_file': output_files[0],
                'file_count': 1,
                'is_zip': False
            }

        request.session['add_border_result'] = result
        request.session.modified = True

        # ✅ Usage update
        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('add_border_result')

    return render(request, 'add_border.html')


def add_border_result(request):
    data = request.session.get('add_border_result')
    if not data:
        return redirect('add_border')

    return render(request, 'add_border_result.html', data)


# ===============================
# 2.8 GRAYSCALE
# ===============================
@rate_limit('100/h')
def image_to_grayscale(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST':
        images = request.FILES.getlist('images')

        if not images:
            messages.error(request, "No images uploaded")
            return redirect('image_to_grayscale')

        # ✅ File count validation
        is_valid, msg = validate_file_count(images)
        if not is_valid:
            messages.error(request, msg)
            return redirect('image_to_grayscale')

        # ✅ Total size validation
        if not is_total_size_safe(images):
            messages.error(request, "Total upload too large")
            return redirect('image_to_grayscale')

        total_size = sum(img.size for img in images)

        # ✅ Usage check
        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('image_to_grayscale')

        fs = FileSystemStorage()
        output_files = []
        session_id = str(uuid.uuid4())[:8]

        for i, img_file in enumerate(images):
            try:
                if not is_safe_image(img_file):
                    continue

                if not validate_image_size(img_file):
                    continue

                with Image.open(img_file) as img:
                    img = img.convert("L")  # grayscale

                    timestamp = int(time.time())
                    filename = f"easypdf_grayscale_{session_id}_{timestamp}_{i}.jpg"
                    output_path = fs.path(filename)

                    img.save(output_path, "JPEG", quality=90, optimize=True)

                    output_files.append(filename)

            except:
                continue

        if not output_files:
            messages.error(request, "Processing failed")
            return redirect('image_to_grayscale')

        # ✅ Save files to session
        request.session['my_files'] = request.session.get('my_files', []) + output_files

        # ✅ ZIP if multiple files
        if len(output_files) > 1:
            zip_filename = f"grayscale_{uuid.uuid4().hex}.zip"
            zip_path = fs.path(zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in output_files:
                    zipf.write(fs.path(f), arcname=f)

            request.session['my_files'].append(zip_filename)

            result = {
                'zip_file': zip_filename,
                'file_count': len(output_files),
                'is_zip': True
            }
        else:
            result = {
                'single_file': output_files[0],
                'file_count': 1,
                'is_zip': False
            }

        request.session['grayscale_result'] = result
        request.session.modified = True

        # ✅ Usage update
        output_size = sum(os.path.getsize(fs.path(f)) for f in output_files)
        update_usage(request, output_size, len(output_files))

        return redirect('image_to_grayscale_result')

    return render(request, 'image_to_grayscale.html')


def image_to_grayscale_result(request):
    data = request.session.get('grayscale_result')
    if not data:
        return redirect('image_to_grayscale')

    return render(request, 'image_to_grayscale_result.html', data)

# ===============================
# CONVERSION TOOLS
# ===============================

# ===============================
# 3.1 WORD TO PDF
# ===============================
@rate_limit('100/h')
def word_to_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        uploaded_file = request.FILES.get("docx")

        if not uploaded_file:
            messages.error(request, "Please upload a DOCX file")
            return redirect('word_to_pdf')

        # ✅ File type check
        if not uploaded_file.name.lower().endswith(".docx"):
            messages.error(request, "Only DOCX files are allowed")
            return redirect('word_to_pdf')

        # ✅ Total size validation
        if not is_total_size_safe([uploaded_file]):
            messages.error(request, "File size too large")
            return redirect('word_to_pdf')

        # ✅ Usage check
        allowed, msg = check_limit(request, uploaded_file.size)
        if not allowed:
            messages.error(request, msg)
            return redirect('word_to_pdf')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(uploaded_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, uploaded_file)
        input_path = fs.path(saved_path)

        timestamp = int(time.time())
        output_filename = f"easypdf_word_to_pdf_{session_id}_{timestamp}.pdf"
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

        try:
            from docx import Document
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch

            doc = Document(input_path)
            styles = getSampleStyleSheet()

            # ✅ Optional: limit paragraphs (safety against huge docs)
            MAX_PARAGRAPHS = 2000

            pdf_doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []

            for i, paragraph in enumerate(doc.paragraphs):
                if i > MAX_PARAGRAPHS:
                    messages.error(request, "Document too large to process")
                    return redirect('word_to_pdf')

                if paragraph.text.strip():
                    text = paragraph.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                    style = ParagraphStyle(
                        'Custom',
                        parent=styles['Normal'],
                        fontSize=11,
                        leading=14
                    )

                    story.append(Paragraph(text, style))
                    story.append(Spacer(1, 0.1 * inch))

            pdf_doc.build(story)

            # ✅ Save session
            request.session['word_to_pdf_result'] = {
                'filename': output_filename
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            # ✅ Usage update (use output size instead of input)
            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, 1)

            return redirect('word_to_pdf_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return redirect('word_to_pdf')

        finally:
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
            except:
                pass

    return render(request, "word_to_pdf.html")


def word_to_pdf_result(request):
    data = request.session.get('word_to_pdf_result')
    if not data:
        return redirect('word_to_pdf')
    return render(request, 'word_to_pdf_result.html', data)


# ===============================
# 3.2 PDF TO WORD
# ===============================
@rate_limit('100/h')
def pdf_to_word(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        uploaded_file = request.FILES.get("pdf")

        if not uploaded_file:
            messages.error(request, "Please upload a PDF file")
            return redirect('pdf_to_word')

        if not uploaded_file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are allowed")
            return redirect('pdf_to_word')

        if not is_total_size_safe([uploaded_file]):
            messages.error(request, "File size too large")
            return redirect('pdf_to_word')

        allowed, msg = check_limit(request, uploaded_file.size)
        if not allowed:
            messages.error(request, msg)
            return redirect('pdf_to_word')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(uploaded_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, uploaded_file)
        input_path = fs.path(saved_path)

        timestamp = int(time.time())
        output_filename = f"easypdf_pdf_to_word_{session_id}_{timestamp}.docx"
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

        try:
            from docx import Document
            from pypdf import PdfReader

            reader = PdfReader(input_path)

            # ✅ PAGE LIMIT CONTROL (important consistency)
            MAX_PDF_PAGES = 200

            total_pages = len(reader.pages)

            if total_pages > MAX_PDF_PAGES:
                messages.error(
                    request,
                    f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}."
                )
                return redirect('pdf_to_word')

            doc = Document()

            extracted_text = 0

            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    doc.add_paragraph(text.strip())
                    extracted_text += 1

            if extracted_text == 0:
                messages.error(request, "No readable text found in PDF")
                return redirect('pdf_to_word')

            doc.save(output_path)

            # ✅ SESSION
            request.session['pdf_to_word_result'] = {
                'filename': output_filename,
                'page_count': total_pages
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            # ✅ IMPORTANT: use OUTPUT size, not input
            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, 1)

            return redirect('pdf_to_word_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return redirect('pdf_to_word')

        finally:
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
            except:
                pass

    return render(request, "pdf_to_word.html")


def pdf_to_word_result(request):
    data = request.session.get('pdf_to_word_result')
    if not data:
        return redirect('pdf_to_word')
    return render(request, 'pdf_to_word_result.html', data)


# ===============================
# 3.3 EXCEL TO PDF
# ===============================
@rate_limit('100/h')
def excel_to_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        uploaded_file = request.FILES.get("excel")

        if not uploaded_file:
            messages.error(request, "Please upload an Excel file")
            return redirect('excel_to_pdf')

        if not uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, "Only Excel files allowed")
            return redirect('excel_to_pdf')

        if not is_total_size_safe([uploaded_file]):
            messages.error(request, "File size too large")
            return redirect('excel_to_pdf')

        allowed, msg = check_limit(request, uploaded_file.size)
        if not allowed:
            messages.error(request, msg)
            return redirect('excel_to_pdf')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(uploaded_file.name)
        temp_name = f"{session_id}_{int(time.time())}_{safe_name}"
        saved_path = fs.save(temp_name, uploaded_file)
        input_path = fs.path(saved_path)

        timestamp = int(time.time())
        output_filename = f"easypdf_excel_to_pdf_{session_id}_{timestamp}.pdf"
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

        try:
            import pandas as pd
            from reportlab.lib.pagesizes import landscape, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
            from reportlab.lib import colors

            df = pd.read_excel(input_path)

            # ✅ Empty file check
            if df.empty or len(df.columns) == 0:
                messages.error(request, "Excel file is empty or invalid")
                return redirect('excel_to_pdf')

            # ❗ SAFETY LIMIT (important for performance)
            MAX_ROWS = 2000
            if len(df) > MAX_ROWS:
                messages.error(request, f"Excel too large (max {MAX_ROWS} rows allowed)")
                return redirect('excel_to_pdf')

            doc = SimpleDocTemplate(output_path, pagesize=landscape(A4))

            # Convert safely (avoid NaN crash)
            df = df.fillna("")

            data = [df.columns.tolist()] + df.astype(str).values.tolist()

            table = Table(data)

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))

            doc.build([table])

            # ✅ SESSION
            request.session['excel_to_pdf_result'] = {
                'filename': output_filename,
                'row_count': len(df),
                'col_count': len(df.columns)
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            # ✅ Usage tracking (use OUTPUT size)
            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, 1)

            return redirect('excel_to_pdf_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return redirect('excel_to_pdf')

        finally:
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
            except:
                pass

    return render(request, "excel_to_pdf.html")



def excel_to_pdf_result(request):
    data = request.session.get('excel_to_pdf_result')
    if not data:
        return redirect('excel_to_pdf')
    return render(request, 'excel_to_pdf_result.html', data)


@rate_limit('100/h')
def text_to_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        text_content = request.POST.get('text_content', '')
        uploaded_file = request.FILES.get('text_file')

        # ✅ file size safety
        if uploaded_file and not is_total_size_safe([uploaded_file]):
            messages.error(request, "File size too large")
            return redirect('text_to_pdf')

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        # =========================
        # CASE 1: TXT FILE UPLOAD
        # =========================
        if uploaded_file:
            if not uploaded_file.name.lower().endswith('.txt'):
                messages.error(request, "Only TXT files are allowed")
                return redirect('text_to_pdf')

            allowed, msg = check_limit(request, uploaded_file.size)
            if not allowed:
                messages.error(request, msg)
                return redirect('text_to_pdf')

            try:
                text_content = uploaded_file.read().decode('utf-8')
            except:
                messages.error(request, "Invalid text file encoding")
                return redirect('text_to_pdf')

        # =========================
        # CASE 2: MANUAL TEXT
        # =========================
        elif not text_content.strip():
            messages.error(request, "Provide text or upload TXT file")
            return redirect('text_to_pdf')

        timestamp = int(time.time())
        output_filename = f"easypdf_text_to_pdf_{session_id}_{timestamp}.pdf"
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

        try:
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch

            # ❗ Safety limit (prevent huge text crash)
            MAX_CHARS = 200000
            if len(text_content) > MAX_CHARS:
                messages.error(request, "Text too large (max 200KB characters)")
                return redirect('text_to_pdf')

            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            style = ParagraphStyle(
                'Custom',
                parent=styles['Normal'],
                fontSize=11,
                leading=14
            )

            for para in text_content.split('\n'):
                if para.strip():
                    para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(para, style))
                    story.append(Spacer(1, 0.1 * inch))

            doc.build(story)

            # ✅ SESSION
            request.session['text_to_pdf_result'] = {
                'filename': output_filename,
                'char_count': len(text_content)
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            # ✅ usage tracking (output size is better)
            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, 1)

            return redirect('text_to_pdf_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return redirect('text_to_pdf')

    return render(request, "text_to_pdf.html")


def text_to_pdf_result(request):
    data = request.session.get('text_to_pdf_result')
    if not data:
        return redirect('text_to_pdf')

    return render(request, 'text_to_pdf_result.html', data)


# 3.5 BULK IMAGE TO PDF
@rate_limit('50/h')
def bulk_image_to_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        images = request.FILES.getlist('images') or request.FILES.getlist('images[]')

        if not images:
            messages.error(request, "No images selected")
            return redirect('bulk_image_to_pdf')

        if not is_total_size_safe(images):
            messages.error(request, "Total upload too large")
            return redirect('bulk_image_to_pdf')

        if len(images) > 20:
            messages.error(request, "Max 20 images allowed")
            return redirect('bulk_image_to_pdf')

        total_size = sum(img.size for img in images)

        allowed, msg = check_limit(request, total_size)
        if not allowed:
            messages.error(request, msg)
            return redirect('bulk_image_to_pdf')

        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, letter, legal
        from reportlab.lib.utils import ImageReader

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]
        timestamp = int(time.time())

        page_sizes = {'a4': A4, 'letter': letter, 'legal': legal}
        page_width, page_height = page_sizes.get(
            request.POST.get('page_size', 'a4'),
            A4
        )

        output_filename = f"easypdf_images_to_pdf_{session_id}_{timestamp}.pdf"
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

        valid_count = 0

        try:
            c = canvas.Canvas(output_path, pagesize=(page_width, page_height))

            for img in images:
                if not is_safe_image(img) or not validate_image_size(img):
                    continue

                img.seek(0)

                try:
                    pil = Image.open(img)
                    pil.verify()
                    img.seek(0)
                    pil = Image.open(img)
                except:
                    continue

                if pil.mode in ('RGBA', 'P'):
                    pil = pil.convert('RGB')

                pil.thumbnail((1200, 1200))

                w, h = pil.size
                ratio = min(page_width / w, page_height / h)
                draw_w, draw_h = w * ratio, h * ratio

                x = (page_width - draw_w) / 2
                y = (page_height - draw_h) / 2

                c.drawImage(ImageReader(pil), x, y, draw_w, draw_h)
                c.showPage()

                valid_count += 1

            c.save()

            if valid_count == 0:
                messages.error(request, "No valid images")
                return redirect('bulk_image_to_pdf')

            # ✅ SESSION
            request.session['bulk_image_to_pdf_result'] = {
                'filename': output_filename,
                'page_count': valid_count
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            # ✅ usage tracking (use output size, not input)
            output_size = os.path.getsize(output_path)
            update_usage(request, output_size, valid_count)

            return redirect('bulk_image_to_pdf_result')

        except Exception as e:
            messages.error(request, f"Conversion failed: {str(e)[:200]}")
            return redirect('bulk_image_to_pdf')

    return render(request, "bulk_image_to_pdf.html")


def bulk_image_to_pdf_result(request):
    data = request.session.get('bulk_image_to_pdf_result')
    if not data:
        return redirect('bulk_image_to_pdf')

    return render(request, 'bulk_image_to_pdf_result.html', data)

# 3.6 QR CODE GENERATOR
@rate_limit('200/h')
def qr_code_generator(request):
    if request.method == "POST":
        content = request.POST.get('content', '').strip()
        fill_color = request.POST.get('fill_color', '#000000').strip()
        back_color = request.POST.get('back_color', '#FFFFFF').strip()

        if not fill_color.startswith('#'):
            fill_color = '#000000'

        if not back_color.startswith('#'):
            back_color = '#FFFFFF'

        if not content:
            return render(request, "qr_code_generator.html", {"error": "Enter content"})

        import qrcode, base64
        from io import BytesIO

        size = int(request.POST.get('size', 800))
        border = int(request.POST.get('border', 2))

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=border)

        if content.startswith("http"):
            data = content
        elif content.isdigit():
            data = f"tel:{content}"
        elif "@" in content:
            data = f"mailto:{content}"
        else:
            data = content

        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')
        img = img.resize((size, size))

        timestamp = int(time.time())
        filename = f"easypdf_qr_{timestamp}.png"
        filepath = os.path.join(settings.MEDIA_ROOT, filename)

        img.save(filepath, "PNG")

        buffer = BytesIO()
        img.save(buffer, format='PNG')

        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        update_usage(request, size * size, 1)

        return render(request, "qr_code_generator.html", {
            "qr_image": img_base64,
            "content": content,
            "filename": filename
        })

    return render(request, "qr_code_generator.html")

# 3.7 PDF METADATA
@rate_limit('100/h')
def pdf_metadata(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        pdf_file = request.FILES.get('pdf')

        if not pdf_file:
            return render(request, "pdf_metadata.html", {"error": "Upload PDF"})

        if not is_total_size_safe([pdf_file]):
            return render(request, "pdf_metadata.html", {"error": "Too large file"})

        if not is_valid_pdf(pdf_file):
            return render(request, "pdf_metadata.html", {"error": "Invalid PDF"})

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, "pdf_metadata.html")

        fs = FileSystemStorage()
        timestamp = int(time.time())
        name = fs.save(f"easypdf_metadata_{timestamp}.pdf", pdf_file)
        path = fs.path(name)

        try:
            # ✅ PAGE VALIDATION ADDED HERE (CONSISTENT RULE)
            is_valid, total_pages = validate_pdf_pages(path)

            if not is_valid:
                return render(
                    request,
                    "pdf_metadata.html",
                    {"error": f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}."}
                )

            reader = PdfReader(path)
            meta = reader.metadata or {}

            data = {
                'file_name': pdf_file.name,
                'file_size': round(pdf_file.size / 1024, 2),
                'num_pages': len(reader.pages),
                'title': meta.get('/Title', ''),
                'author': meta.get('/Author', ''),
                'subject': meta.get('/Subject', ''),
            }

            request.session['pdf_metadata_result'] = data
            request.session.modified = True

            update_usage(request, pdf_file.size, 1)

            return redirect('pdf_metadata_result')

        finally:
            if os.path.exists(path):
                os.remove(path)

    return render(request, "pdf_metadata.html")


def pdf_metadata_result(request):
    data = request.session.get('pdf_metadata_result')
    if not data:
        return redirect('pdf_metadata')

    return render(request, 'pdf_metadata_result.html', data)

# ===============================
# SECURITY & UTILITY TOOLS
# ===============================

# 4.1 ADD WATERMARK
@rate_limit('100/h')
def add_watermark(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        pdf_file = request.FILES.get('pdf')

        if not pdf_file:
            return render(request, "add_watermark.html", {"error": "Upload PDF file"})

        if not is_total_size_safe([pdf_file]):
            messages.error(request, "File too large")
            return redirect('add_watermark')

        if not is_valid_pdf(pdf_file):
            messages.error(request, "Invalid PDF")
            return render(request, 'add_watermark.html')

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            messages.error(request, msg)
            return render(request, "add_watermark.html")

        watermark_text = request.POST.get('watermark_text', 'Confidential')
        position = request.POST.get('position', 'center')
        font_size = int(request.POST.get('font_size', 40))
        rotation = int(request.POST.get('rotation', 45))
        color = request.POST.get('color', '#000000')
        opacity = int(request.POST.get('opacity', 30))

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = fs.save(f"{session_id}_{safe_name}", pdf_file)
        pdf_path = fs.path(temp_name)

        # ✅ PAGE VALIDATION ADDED HERE
        is_valid, total_pages = validate_pdf_pages(pdf_path)
        if not is_valid:
            messages.error(
                request,
                f"PDF has {total_pages} pages. Max allowed is {MAX_PDF_PAGES}."
            )
            return render(request, 'add_watermark.html')

        try:
            from pypdf import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from io import BytesIO

            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

            r, g, b = hex_to_rgb(color)

            first_page = reader.pages[0]
            w, h = float(first_page.mediabox.width), float(first_page.mediabox.height)

            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=(w, h))

            # Font
            can.setFont("Helvetica", font_size)

            # Color
            can.setFillColorRGB(r, g, b)

            # ✅ Opacity from frontend
            opacity = int(request.POST.get('opacity', 30)) / 100

            # Apply transparency
            try:
                can.setFillAlpha(opacity)
            except:
                pass

            # Position
            x, y = w / 2, h / 2

            if position == "top-left":
                x, y = 80, h - 80
            elif position == "top-right":
                x, y = w - 80, h - 80
            elif position == "bottom-left":
                x, y = 80, 80
            elif position == "bottom-right":
                x, y = w - 80, 80

            # Draw watermark
            can.saveState()
            can.translate(x, y)

            # ✅ Reverse rotation so preview = output
            can.rotate(-rotation)

            # Alignment
            if position in ["top-left", "bottom-left"]:
                can.drawString(0, 0, watermark_text)
            elif position in ["top-right", "bottom-right"]:
                can.drawRightString(0, 0, watermark_text)
            else:
                can.drawCentredString(0, 0, watermark_text)

            can.restoreState()
            can.save()

            packet.seek(0)
            watermark = PdfReader(packet).pages[0]

            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)

            timestamp = int(time.time())
            output_filename = f"easypdf_watermark_{timestamp}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            request.session['add_watermark_result'] = {
                'filename': output_filename
            }

            request.session['my_files'] = request.session.get('my_files', []) + [output_filename]
            request.session.modified = True

            update_usage(request, pdf_file.size, 1)

            return redirect('add_watermark_result')

        except Exception as e:
            return render(request, "add_watermark.html", {"error": str(e)})

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, "add_watermark.html")

def add_watermark_result(request):
    data = request.session.get('add_watermark_result')

    # If no session data → prevent direct access
    if not data or 'filename' not in data:
        messages.warning(request, "No file found. Please process again.")
        return redirect('add_watermark')

    filename = data['filename']

    # Build file URL (MEDIA)
    file_url = f"/media/{filename}"

    return render(request, "add_watermark_result.html", {
        "filename": filename,
        "file_url": file_url
    })

# 4.2 REMOVE PASSWORD
@rate_limit('100/h')
def remove_password(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == "POST":
        pdf_file = request.FILES.get('pdf')
        password = request.POST.get('password', '').strip()

        if not pdf_file:
            return render(request, "remove_password.html", {
                "error": "Please upload a PDF file."
            })

        if not password:
            return render(request, "remove_password.html", {
                "error": "Please enter the password."
            })

        if not is_total_size_safe([pdf_file]):
            return render(request, "remove_password.html", {
                "error": "File is too large."
            })

        if not is_valid_pdf(pdf_file):
            return render(request, "remove_password.html", {
                "error": "Invalid PDF file."
            })

        allowed, msg = check_limit(request, pdf_file.size)
        if not allowed:
            return render(request, "remove_password.html", {
                "error": msg
            })

        fs = FileSystemStorage()
        session_id = str(uuid.uuid4())[:8]

        safe_name = secure_filename(pdf_file.name)
        temp_name = fs.save(f"{session_id}_{safe_name}", pdf_file)
        pdf_path = fs.path(temp_name)

        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(pdf_path)

            # FIRST check password
            if reader.is_encrypted:
                result = reader.decrypt(password)

                if result == 0:
                    return render(request, "remove_password.html", {
                        "error": "You entered the wrong password. Please enter the correct password."
                    })

            # AFTER successful decrypt check pages
            total_pages = len(reader.pages)

            if total_pages > MAX_PDF_PAGES:
                return render(request, "remove_password.html", {
                    "error": f"PDF has {total_pages} pages. Maximum allowed is {MAX_PDF_PAGES}."
                })

            writer = PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            output_filename = f"easypdf_unlocked_{int(time.time())}.pdf"
            output_path = os.path.join(settings.MEDIA_ROOT, output_filename)

            with open(output_path, "wb") as f:
                writer.write(f)

            request.session["remove_password_result"] = {
                "filename": output_filename
            }

            request.session["my_files"] = request.session.get("my_files", []) + [output_filename]
            request.session.modified = True

            update_usage(request, pdf_file.size, 1)

            return redirect("remove_password_result")

        except Exception as e:
            print("REMOVE PASSWORD ERROR:", str(e))
            return render(request, "remove_password.html", {
                "error": "Unable to process this PDF."
            })

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    return render(request, "remove_password.html")

    
def remove_password_result(request):
    data = request.session.get('remove_password_result')

    if not data:
        messages.warning(request, "No file found. Please try again.")
        return redirect('remove_password')

    return render(request, 'remove_password_result.html', data)

# 4.3 PASSWORD STRENGTH CHECKER
def password_strength_checker(request):
    return render(request, 'password_strength_checker.html')


# 4.4 PASSWORD GENERATOR
def password_generator(request):
    return render(request, 'password_generator.html')


# ===============================
# EXAM & STUDY TOOLS
# ===============================

def quiz_generator(request):
    return render(request, 'quiz_generator.html')


def flashcard_generator(request):
    return render(request, 'flashcard_generator.html')


def study_timer(request):
    return render(request, 'study_timer.html')


def grade_calculator(request):
    return render(request, 'grade_calculator.html')


# ===============================
# PRODUCTIVITY TOOLS
# ===============================

# 5.1 PDF PAGE REORGANIZER
def pdf_reorganizer(request):

    return render(request, 'pdf_reorganizer.html', {
        'title': 'Reorganize PDF Pages Online Free | EasyPDF',
        'description': 'Reorder, rearrange and organize PDF pages easily. Free online PDF page organizer tool with no signup required.',
        'keywords': 'reorder pdf pages, rearrange pdf, organize pdf online free',
        'page': 'pdf_reorganizer'
    })


@rate_limit('100/h')
def reorganize_pdf(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pdf_data = data.get('pdf_data')
            page_order = data.get('page_order')

            if not pdf_data or not isinstance(page_order, list):
                return JsonResponse({'status': 'error', 'message': 'Invalid input'}, status=400)

            pdf_bytes = base64.b64decode(pdf_data)

            # 🔐 SIZE LIMIT
            if len(pdf_bytes) > 200 * 1024 * 1024:
                return JsonResponse({
                    'status': 'error',
                    'message': 'File too large (max 200MB)'
                }, status=400)

            reader = PdfReader(BytesIO(pdf_bytes))

            # ✅ PAGE LIMIT VALIDATION (IMPORTANT FIX)
            is_valid, total_pages = validate_pdf_pages(BytesIO(pdf_bytes))
            if not is_valid:
                return JsonResponse({
                    'status': 'error',
                    'message': f'PDF too large ({total_pages} pages)'
                }, status=400)

            # Normalize + deduplicate page order
            seen = set()
            valid_pages = []

            for p in page_order:
                if isinstance(p, int) and 1 <= p <= total_pages and p not in seen:
                    valid_pages.append(p)
                    seen.add(p)

            if not valid_pages:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid page order'
                }, status=400)

            writer = PdfWriter()

            for p in valid_pages:
                writer.add_page(reader.pages[p - 1])

            output_buffer = BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)

            output_base64 = base64.b64encode(output_buffer.getvalue()).decode()

            update_usage(request, len(pdf_bytes), len(valid_pages))

            timestamp = int(time.time())
            filename = f"easypdf_pdf_reorganizer_{timestamp}.pdf"

            return JsonResponse({
                'status': 'success',
                'pdf_data': output_base64,
                'page_count': len(valid_pages),
                'filename': filename
            })

        except Exception as e:
            print("Reorganize Error:", e)
            return JsonResponse({
                'status': 'error',
                'message': 'Processing failed'
            }, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

    
# 5.2 STUDY TIMETABLE
def study_timetable(request):
    return render(request, 'study_timetable.html', {
        'title': 'Free Study Timetable Generator Online | EasyPDF',
        'description': 'Create a smart study timetable instantly. Plan your daily study schedule and improve productivity with our free timetable generator.',
        'keywords': 'study timetable generator, student planner, study schedule maker, timetable for students',
        'page': 'study_timetable'
    })



def generate_timetable(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)

    try:
        data = json.loads(request.body)

        subjects = data.get('subjects', [])
        hours_per_day = int(data.get('hours_per_day', 4))
        days = int(data.get('days', 7))

        if not subjects:
            return JsonResponse({'status': 'error', 'message': 'No subjects'}, status=400)

        start_time = datetime.strptime(data.get('custom_time', '06:00'), "%H:%M")

        timetable = []
        subject_count = len(subjects)

        for day in range(days):
            current_time = start_time
            day_plan = []

            rotated = subjects[day % subject_count:] + subjects[:day % subject_count]

            for subject in rotated:
                end_time = current_time + timedelta(hours=1)

                day_plan.append({
                    'subject': subject,
                    'start': current_time.strftime("%I:%M %p"),
                    'end': end_time.strftime("%I:%M %p"),
                    'duration': "1 hr"
                })

                current_time = end_time + timedelta(minutes=10)

            timetable.append({
                'day': f"Day {day+1}",
                'schedule': day_plan
            })

        return JsonResponse({
            'status': 'success',
            'timetable': timetable
        })

    except Exception as e:
        print("Timetable Error:", e)
        return JsonResponse({'status': 'error'}, status=500)


def download_timetable_pdf(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            timetable = data.get('timetable', [])

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()

            elements = [Paragraph("Study Timetable", styles['Title']), Spacer(1, 10)]

            for day in timetable:
                elements.append(Paragraph(day['day'], styles['Heading2']))
                elements.append(Spacer(1, 5))

                table_data = [["Subject", "Start", "End", "Duration"]]

                for item in day['schedule']:
                    table_data.append([
                        item['subject'],
                        item['start'],
                        item['end'],
                        item['duration']
                    ])

                table = Table(table_data)
                elements.append(table)
                elements.append(Spacer(1, 10))

            doc.build(elements)
            buffer.seek(0)

            pdf_base64 = base64.b64encode(buffer.getvalue()).decode()
            timestamp = int(time.time())
            filename = f"easypdf_study_timetable_{timestamp}.pdf"
            return JsonResponse({
                'status': 'success',
                'pdf': pdf_base64,
                'filename': filename
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error'})

# 5.3 TO-DO LIST
def todo_list(request):
    return render(request, 'todo_list.html', {
        'title': 'To-Do List - EasyPDF',
        'page': 'todo_list'
    })



def save_todos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            todos = data.get('todos', [])

            if not isinstance(todos, list):
                return JsonResponse({'status': 'error'}, status=400)

            request.session['todo_list'] = todos
            request.session.modified = True

            return JsonResponse({'status': 'success'})

        except Exception as e:
            return JsonResponse({'status': 'error'}, status=400)

    return JsonResponse({'status': 'error'}, status=405)


def load_todos(request):
    if request.method == 'GET':
        todos = request.session.get('todo_list', [])
        return JsonResponse({'status': 'success', 'todos': todos})

    return JsonResponse({'status': 'error'}, status=405)

# 5.4 WORD COUNTER
def word_counter(request):
    try:
        cleanup_old_files()
    except Exception as e:
        print("Cleanup failed:", e)
    return render(request, 'word_counter.html', {
        'title': 'Word Counter - EasyPDF',
        'page': 'word_counter'
    })


# ===============================
# NEW PAGES VIEWS
# ===============================

def about(request):
    return render(request, 'about.html', {
        'title': 'About EasyPDF - Free Online PDF & Image Tools',
        'description': 'EasyPDF provides free online tools for PDF, image, and document conversion. Built for students, developers, and professionals.',
        'keywords': 'about easypdf, free pdf tools, online pdf converter',
        'page': 'about'
    })


def contact(request):
    return render(request, 'contact.html', {
        'title': 'Contact EasyPDF - Get Help & Support',
        'description': 'Contact EasyPDF for support, feedback, or business inquiries. We are here to help you.',
        'keywords': 'contact easypdf, support pdf tools',
        'page': 'contact'
    })



def contact_submit(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        # ✅ Validation
        if not name or not email or not message:
            messages.error(request, "All fields are required")
            return redirect('contact')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address")
            return redirect('contact')

        if len(message) < 10:
            messages.error(request, "Message too short")
            return redirect('contact')

        if "http://" in message or "https://" in message:
            messages.warning(request, "Links are not allowed in message")
            return redirect('contact')

        try:
            # ✅ Email to YOU (Admin)
            send_mail(
                subject=f"[EasyPDF Contact] {subject}",
                message=f"""
New message from EasyPDF:

Name: {name}
Email: {email}

Message:
{message}
                """,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.EMAIL_HOST_USER],  # your email
                fail_silently=False,
            )

            # ✅ Confirmation email to USER
            send_mail(
                subject="We received your message - EasyPDF",
                message=f"""
Hi {name},

Thanks for contacting EasyPDF 🙌

We received your message and will get back to you within 24-48 hours.

Your message:
{message}

— EasyPDF Team
                """,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(request, "Message sent successfully! Check your email ✔️")
            return redirect('contact')

        except Exception as e:
            print("EMAIL ERROR:", e)
            messages.error(request, "Something went wrong. Please try again later.")
            return redirect('contact')

    return redirect('contact')

def privacy_policy(request):
    return render(request, 'privacy-policy.html', {
        'title': 'Privacy Policy - EasyPDF',
        'description': 'Learn how EasyPDF collects, uses, and protects your data while using our free online tools.',
        'keywords': 'privacy policy easypdf, data protection pdf tools',
        'page': 'privacy_policy'
    })


def terms(request):
    return render(request, 'terms.html', {
        'title': 'Terms of Service - EasyPDF',
        'description': 'Read the terms and conditions for using EasyPDF tools and services.',
        'keywords': 'terms easypdf, usage policy pdf tools',
        'page': 'terms'
    })

from django.shortcuts import render


# ===============================
# BLOG LIST PAGE
# ===============================
# ===============================
# BLOG VIEWS - COMPLETE LIST
# ===============================

def blog_list(request):
    blogs = [
        {
            "title": "How to Merge PDF Files: Complete Guide for Students",
            "url": "blog_merge_pdf",
            "description": "Learn how to combine multiple PDF files into one document. Step-by-step guide for merging assignments, reports, and scanned documents without losing quality.",
            "date": "April 25, 2026",
            "read_time": 6,
            "category": "PDF Tools",
            "featured": True,
        },
        {
            "title": "How to Split PDF Files: Extract Specific Pages",
            "url": "blog_split_pdf",
            "description": "Extract specific pages from PDF documents. Learn to split by page ranges and create new PDFs from selected pages.",
            "date": "April 2026",
            "read_time": 5,
            "category": "PDF Tools",
            "featured": False,
        },
        {
            "title": "How to Compress PDF for Email Attachments",
            "url": "blog_compress_pdf",
            "description": "Reduce PDF file size for email attachments and online submissions. Free online guide to make PDFs smaller without losing quality.",
            "date": "April 2026",
            "read_time": 5,
            "category": "PDF Tools",
            "featured": False,
        },
        {
            "title": "How to Convert JPG to PDF on Mobile and PC",
            "url": "blog_jpg_to_pdf",
            "description": "Convert JPG images to PDF on mobile, PC, or online for free. Perfect for converting scanned notes and photos.",
            "date": "April 2026",
            "read_time": 5,
            "category": "Conversion",
            "featured": False,
        },
        {
            "title": "How to Remove Pages from a PDF Easily",
            "url": "blog_remove_pages",
            "description": "Delete unwanted pages from PDF files online for free. Step-by-step guide to remove specific pages and clean up documents.",
            "date": "April 2026",
            "read_time": 4,
            "category": "PDF Tools",
            "featured": False,
        },
        {
            "title": "How to Add Page Numbers to PDF Documents",
            "url": "blog_add_page_numbers",
            "description": "Learn how to add page numbers to PDF documents online for free. Professional formatting for reports and assignments.",
            "date": "April 2026",
            "read_time": 4,
            "category": "PDF Tools",
            "featured": False,
        },
        {
            "title": "How to Resize Images for Online Forms and Exams",
            "url": "blog_resize_images",
            "description": "Learn how to resize images for online forms, exams, and submissions. Step-by-step guide to change image dimensions.",
            "date": "April 2026",
            "read_time": 5,
            "category": "Image Tools",
            "featured": False,
        },
        {
            "title": "Best Free PDF Tools for Students in 2026",
            "url": "blog_best_pdf_tools",
            "description": "Discover the best free PDF tools for students. Merge, split, compress, and edit PDFs for assignments and exam preparation.",
            "date": "April 2026",
            "read_time": 6,
            "category": "Student Success",
            "featured": False,
        },
        {
            "title": "How to Rotate PDF Pages Permanently",
            "url": "blog_rotate_pdf",
            "description": "Fix page orientation in your PDF documents. Learn how to rotate single or multiple pages 90°, 180°, or 270°.",
            "date": "April 20, 2026",
            "read_time": 4,
            "category": "PDF Tools",
            "featured": False,
        },
        {
            "title": "How to Create the Perfect Study Timetable",
            "url": "blog_study_timetable",
            "description": "Create an effective study schedule with proven tips. Maximize your productivity and ace your exams.",
            "date": "April 15, 2026",
            "read_time": 5,
            "category": "Student Success",
            "featured": False,
        },
        {
            "title": "How to Convert PDF to Word Without Losing Formatting",
            "url": "blog_pdf_to_word",
            "description": "Step-by-step guide to converting PDF files to editable Word documents while preserving tables, images, and font styles.",
            "date": "April 10, 2026",
            "read_time": 5,
            "category": "Conversion",
            "featured": False,
        },
        {
            "title": "How to Convert Any Website to PDF",
            "url": "blog_website_to_pdf",
            "description": "Save web pages as PDF files in seconds. Perfect for saving articles, research papers, and online resources.",
            "date": "April 5, 2026",
            "read_time": 4,
            "category": "Web Tools",
            "featured": False,
        },
        {
            "title": "What is OCR? Complete Guide to Text Recognition",
            "url": "blog_ocr_guide",
            "description": "Learn how Optical Character Recognition works and how to extract editable text from scanned PDFs and images.",
            "date": "March 28, 2026",
            "read_time": 7,
            "category": "AI Tools",
            "featured": False,
        },
        {
            "title": "How to Password Protect a PDF File",
            "url": "blog_secure_pdf",
            "description": "Keep your sensitive documents secure by adding password protection to your PDF files.",
            "date": "March 20, 2026",
            "read_time": 5,
            "category": "Security",
            "featured": False,
        },
    ]
    
    return render(request, 'blog/blog_list.html', {
        'blogs': blogs,
    })


# ===============================
# EXISTING BLOG VIEWS (Keep these)
# ===============================

def blog_merge_pdf(request):
    context = {
        'blog_title': 'How to Merge PDF Files: A Complete Guide for Students & Professionals',
        'meta_description': 'Learn how to merge PDF files online for free. Step-by-step guide for combining multiple PDFs into one document.',
        'blog_date': 'April 25, 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 6,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/merge-pdf/',
        'tool_name': 'Merge PDF Tool',
    }
    return render(request, 'blog/blog_how_to_merge_pdf.html', context)


def blog_rotate_pdf(request):
    context = {
        'blog_title': 'How to Rotate PDF Pages Permanently (90°, 180°, 270°)',
        'meta_description': 'Fix page orientation in your PDF documents. Learn how to rotate single or multiple pages permanently with our free online tool.',
        'blog_date': 'April 20, 2026',
        'blog_date_iso': '2026-04-20',
        'read_time': 4,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/rotate-pdf/',
        'tool_name': 'Rotate PDF Tool',
    }
    return render(request, 'blog/blog_how_to_rotate_pdf.html', context)


def blog_study_timetable(request):
    context = {
        'blog_title': 'How to Create the Perfect Study Timetable for Engineering Students',
        'meta_description': 'Create an effective study schedule with our proven tips and free study timetable generator. Maximize your productivity and ace your exams.',
        'blog_date': 'April 15, 2026',
        'blog_date_iso': '2026-04-15',
        'read_time': 5,
        'category': 'Student Success',
        'category_slug': 'student',
        'show_toc': True,
        'tool_url': '/study-timetable/',
        'tool_name': 'Study Timetable Generator',
    }
    return render(request, 'blog/blog_how_to_study_timetable.html', context)


def blog_pdf_to_word(request):
    context = {
        'blog_title': 'How to Convert PDF to Word Without Losing Formatting (Free)',
        'meta_description': 'Step-by-step guide to converting PDF files to editable Word documents while preserving tables, images, and font styles.',
        'blog_date': 'April 10, 2026',
        'blog_date_iso': '2026-04-10',
        'read_time': 5,
        'category': 'Conversion',
        'category_slug': 'conversion',
        'show_toc': True,
        'tool_url': '/pdf-to-word/',
        'tool_name': 'PDF to Word Converter',
    }
    return render(request, 'blog/blog_how_to_pdf_to_word.html', context)


def blog_website_to_pdf(request):
    context = {
        'blog_title': 'How to Convert Any Website to PDF for Offline Reading',
        'meta_description': 'Save web pages as PDF files in seconds. Perfect for saving articles, research papers, and online resources for later reference.',
        'blog_date': 'April 5, 2026',
        'blog_date_iso': '2026-04-05',
        'read_time': 4,
        'category': 'Web Tools',
        'category_slug': 'web',
        'show_toc': True,
        'tool_url': '/website-to-pdf/',
        'tool_name': 'Website to PDF Tool',
    }
    return render(request, 'blog/blog_how_to_website_to_pdf.html', context)


def blog_ocr_guide(request):
    context = {
        'blog_title': 'What is OCR? Complete Guide to Text Recognition from Scanned Documents',
        'meta_description': 'Learn how Optical Character Recognition works and how to extract editable text from scanned PDFs, images, and documents.',
        'blog_date': 'March 28, 2026',
        'blog_date_iso': '2026-03-28',
        'read_time': 7,
        'category': 'AI Tools',
        'category_slug': 'ai',
        'show_toc': True,
        'tool_url': '/ocr/',
        'tool_name': 'OCR Tool',
    }
    return render(request, 'blog/blog_how_to_ocr_guide.html', context)


def blog_secure_pdf(request):
    context = {
        'blog_title': 'How to Password Protect a PDF File (Step-by-Step Guide)',
        'meta_description': 'Keep your sensitive documents secure by adding password protection to your PDF files. Learn best practices for PDF security.',
        'blog_date': 'March 20, 2026',
        'blog_date_iso': '2026-03-20',
        'read_time': 5,
        'category': 'Security',
        'category_slug': 'security',
        'show_toc': True,
        'tool_url': '/protect-pdf/',
        'tool_name': 'Protect PDF Tool',
    }
    return render(request, 'blog/blog_how_to_secure_pdf.html', context)


# ===============================
# NEW BLOG VIEWS (Add these)
# ===============================

def blog_split_pdf(request):
    context = {
        'blog_title': 'How to Split PDF Files: Extract Specific Pages Easily',
        'meta_description': 'Learn how to split PDF files and extract specific pages online for free. Step-by-step guide to separate PDF pages, remove unwanted pages, and organize documents.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 5,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/split-pdf/',
        'tool_name': 'Split PDF Tool',
    }
    return render(request, 'blog/blog_how_to_split_pdf.html', context)


def blog_compress_pdf(request):
    context = {
        'blog_title': 'How to Compress PDF for Email Attachments',
        'meta_description': 'Learn how to compress PDF files to reduce size for email attachments. Free online guide to make PDFs smaller without losing quality.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 5,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/compress-pdf/',
        'tool_name': 'Compress PDF Tool',
    }
    return render(request, 'blog/blog_how_to_compress_pdf.html', context)


def blog_jpg_to_pdf(request):
    context = {
        'blog_title': 'How to Convert JPG to PDF on Mobile and PC',
        'meta_description': 'Learn how to convert JPG images to PDF on mobile, PC, or online for free. Step-by-step guide for converting multiple images to a single PDF document.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 5,
        'category': 'Conversion',
        'category_slug': 'conversion',
        'show_toc': True,
        'tool_url': '/jpg-to-pdf/',
        'tool_name': 'JPG to PDF Converter',
    }
    return render(request, 'blog/blog_how_to_jpg_to_pdf.html', context)



def blog_remove_pages(request):
    context = {
        'blog_title': 'How to Remove Pages from a PDF Easily',
        'meta_description': 'Learn how to delete unwanted pages from PDF files online for free. Step-by-step guide to remove specific pages, extract ranges, and clean up your PDF documents.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 4,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/remove-pages/',
        'tool_name': 'Remove Pages Tool',
    }
    return render(request, 'blog/blog_how_to_remove_pages.html', context)


def blog_add_page_numbers(request):
    context = {
        'blog_title': 'How to Add Page Numbers to PDF Documents',
        'meta_description': 'Learn how to add page numbers to PDF documents online for free. Step-by-step guide to insert page numbers, customize position and format for professional documents.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 4,
        'category': 'PDF Tools',
        'category_slug': 'pdf',
        'show_toc': True,
        'tool_url': '/add-page-numbers/',
        'tool_name': 'Add Page Numbers Tool',
    }
    return render(request, 'blog/blog_how_to_add_page_numbers.html', context)


def blog_resize_images(request):
    context = {
        'blog_title': 'How to Resize Images for Online Forms and Exams',
        'meta_description': 'Learn how to resize images for online forms, exams, and submissions. Step-by-step guide to change image dimensions, reduce file size, and meet upload requirements.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 5,
        'category': 'Image Tools',
        'category_slug': 'image',
        'show_toc': True,
        'tool_url': '/resize-images/',
        'tool_name': 'Resize Images Tool',
    }
    return render(request, 'blog/blog_how_to_resize_images.html', context)


def blog_best_pdf_tools(request):
    context = {
        'blog_title': 'Best Free PDF Tools for Students in 2026',
        'meta_description': 'Discover the best free PDF tools for students in 2026. Merge, split, compress, and edit PDFs for assignments, projects, and exam preparation. Complete student guide.',
        'blog_date': 'April 2026',
        'blog_date_iso': '2026-04-25',
        'read_time': 6,
        'category': 'Student Success',
        'category_slug': 'student',
        'show_toc': True,
        'tool_url': '/merge-pdf/',
        'tool_name': 'Free PDF Tools',
    }
    return render(request, 'blog/blog_best_pdf_tools_for_students.html', context)


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Sitemap: https://easypdf-dy1o.onrender.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")