# tools/urls.py

from django.contrib import admin
from . import views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # ===============================
    # HOME
    # ===============================
    path('', views.home, name='home'),
    
    # ===============================
    # NEW PAGES
    # ===============================
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms, name='terms'),
    path('api/contact-submit/', views.contact_submit, name='contact_submit'),

    


    # ===============================
    # PDF TOOLS
    # ===============================
    # Merge PDF
    path('merge-pdf/', views.merge_pdf, name='merge_pdf'),
    
    # Split PDF
    path('split-pdf/', views.split_pdf, name='split_pdf'),
    path('split-pdf/result/', views.split_result, name='split_result'),
    
    # Rotate PDF
    path('rotate-pdf/', views.rotate_pdf, name='rotate_pdf'),
    path('rotate-pdf/result/', views.rotate_pdf_result, name='rotate_pdf_result'),
    
    # PDF to JPG
    path('pdf-to-jpg/', views.convert_to_jpg, name='convert_to_jpg'),
    path('pdf-to-jpg/result/', views.pdf_to_jpg_result, name='pdf_to_jpg_result'),
    
    # JPG to PDF
    path('jpg-to-pdf/', views.jpg_to_pdf, name='jpg_to_pdf'),
    path('jpg-to-pdf/result/', views.jpg_to_pdf_result, name='jpg_to_pdf_result'),
    
    # Protect PDF
    path('protect-pdf/', views.protect_pdf, name='protect_pdf'),
    path('protect-pdf/result/', views.protect_pdf_result, name='protect_pdf_result'),
    
    # PDF to Text
    path('pdf-to-text/', views.pdf_to_text, name='pdf_to_text'),
    path('pdf-to-text/result/', views.pdf_to_text_result, name='pdf_to_text_result'),
    
    # Remove Pages
    path('remove-pages/', views.remove_pages, name='remove_pages'),
    path('remove-pages/result/', views.remove_pages_result, name='remove_pages_result'),
    
    # Add Page Numbers
    path('add-page-numbers/', views.add_page_numbers, name='add_page_numbers'),
    path('add-page-numbers/result/', views.add_page_numbers_result, name='add_page_numbers_result'),
    
    # ===============================
    # IMAGE TOOLS
    # ===============================
    # Compress Images
    path('compress-images/', views.compress_page, name='compress_page'),
    path('compress-images-process/', views.compress_images, name='compress_images'),
    
    # Convert Image Format
    path('convert-image-format/', views.convert_image_format, name='convert_image_format'),
    path('api/process-image-conversion/', views.process_image_conversion, name='process_image_conversion'),
    path('convert-image-format-result/', views.convert_image_format_result, name='convert_image_format_result'),
    
    # Resize Images
    path('resize-images/', views.resize_images, name='resize_images'),
    path('resize-images/result/', views.resize_images_result, name='resize_images_result'),
    
    # Crop Images
    path('crop-images/', views.crop_images, name='crop_images'),
    path('crop-images/result/', views.crop_images_result, name='crop_images_result'),
    
    # Rotate Images
    path('rotate-images/', views.rotate_images, name='rotate_images'),
    path('rotate-images/result/', views.rotate_images_result, name='rotate_images_result'),
    
    # Flip Images
    path('flip-images/', views.flip_images, name='flip_images'),
    path('flip-images/result/', views.flip_images_result, name='flip_images_result'),
    
    # Add Border
    path('add-border/', views.add_border, name='add_border'),
    path('add-border/result/', views.add_border_result, name='add_border_result'),
    
    # Image to Grayscale
    path('image-to-grayscale/', views.image_to_grayscale, name='image_to_grayscale'),
    path('image-to-grayscale/result/', views.image_to_grayscale_result, name='image_to_grayscale_result'),
    
    # ===============================
    # CONVERSION TOOLS
    # ===============================
    # Word to PDF
    path('word-to-pdf/', views.word_to_pdf, name='word_to_pdf'),
    path('word-to-pdf/result/', views.word_to_pdf_result, name='word_to_pdf_result'),
    
    # PDF to Word
    path('pdf-to-word/', views.pdf_to_word, name='pdf_to_word'),
    path('pdf-to-word/result/', views.pdf_to_word_result, name='pdf_to_word_result'),
    
    # Excel to PDF
    path('excel-to-pdf/', views.excel_to_pdf, name='excel_to_pdf'),
    path('excel-to-pdf/result/', views.excel_to_pdf_result, name='excel_to_pdf_result'),
    
    # Text to PDF
    path('text-to-pdf/', views.text_to_pdf, name='text_to_pdf'),
    path('text-to-pdf/result/', views.text_to_pdf_result, name='text_to_pdf_result'),
    
    # Bulk Image to PDF
    path('bulk-image-to-pdf/', views.bulk_image_to_pdf, name='bulk_image_to_pdf'),
    path('bulk-image-to-pdf/result/', views.bulk_image_to_pdf_result, name='bulk_image_to_pdf_result'),
    
    # QR Code Generator
    path('qr-code-generator/', views.qr_code_generator, name='qr_code_generator'),
    
    # PDF Metadata
    path('pdf-metadata/', views.pdf_metadata, name='pdf_metadata'),
    path('pdf-metadata/result/', views.pdf_metadata_result, name='pdf_metadata_result'),
    
    # ===============================
    # SECURITY & UTILITY
    # ===============================
    # Add Watermark
    path('add-watermark/', views.add_watermark, name='add_watermark'),
    path('add-watermark/result/', views.add_watermark_result, name='add_watermark_result'),
    
    # Remove Password
    path('remove-password/', views.remove_password, name='remove_password'),
    path('remove-password-result/', views.remove_password_result, name='remove_password_result'),
    
    path('password-generator/', views.password_generator, name='password_generator'),
    
    # Password Strength Checker
    path('password-strength-checker/', views.password_strength_checker, name='password_strength_checker'),
    
    path('quiz-generator/', views.quiz_generator, name='quiz_generator'),
    
    path('flashcard-generator/', views.flashcard_generator, name='flashcard_generator'),
    
    path('study-timer/', views.study_timer, name='study_timer'),
    
    path('grade-calculator/', views.grade_calculator, name='grade_calculator'),
    
    path('pdf-reorganizer/', views.pdf_reorganizer, name='pdf_reorganizer'),
    path('api/reorganize-pdf/', views.reorganize_pdf, name='reorganize_pdf'),
    
    path('study-timetable/', views.study_timetable, name='study_timetable'),
    path('api/generate-timetable/', views.generate_timetable, name='generate_timetable'),
    path('api/download-timetable-pdf/', views.download_timetable_pdf, name='download_timetable_pdf'),
    
    # To-Do List URLs
    path('todo-list/', views.todo_list, name='todo_list'),
    path('api/save-todos/', views.save_todos, name='save_todos'),
    path('api/load-todos/', views.load_todos, name='load_todos'),
    
    # Word Counter URLs
    path('word-counter/', views.word_counter, name='word_counter'),

    path('blog/', views.blog_list, name='blog_list'),

    # BLOG PAGES (CLEAN URLS)
    path('blog/merge-pdf/', views.blog_merge_pdf, name='blog_merge_pdf'),
    path('blog/rotate-pdf/', views.blog_rotate_pdf, name='blog_rotate_pdf'),
    path('blog/study-timetable/', views.blog_study_timetable, name='blog_study_timetable'),
    path('blog/pdf-to-word/', views.blog_pdf_to_word, name='blog_pdf_to_word'),
    path('blog/website-to-pdf/', views.blog_website_to_pdf, name='blog_website_to_pdf'),
    path('blog/ocr-guide/', views.blog_ocr_guide, name='blog_ocr_guide'),
    path('blog/secure-pdf/', views.blog_secure_pdf, name='blog_secure_pdf'),
    
    path('blog/split-pdf/', views.blog_split_pdf, name='blog_split_pdf'),
    path('blog/compress-pdf/', views.blog_compress_pdf, name='blog_compress_pdf'),
    path('blog/jpg-to-pdf/', views.blog_jpg_to_pdf, name='blog_jpg_to_pdf'),
    path('blog/remove-pages/', views.blog_remove_pages, name='blog_remove_pages'),
    path('blog/add-page-numbers/', views.blog_add_page_numbers, name='blog_add_page_numbers'),
    path('blog/resize-images/', views.blog_resize_images, name='blog_resize_images'),
    path('blog/best-pdf-tools-students/', views.blog_best_pdf_tools, name='blog_best_pdf_tools'),
    # ===============================
    # DOWNLOAD
    # ===============================
    path('download/<str:filename>/', views.download_file, name='download_file'),

    path("robots.txt", views.robots_txt, name="robots_txt"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)