from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            'home',

            # PDF Tools
            'merge_pdf',
            'split_pdf',
            'rotate_pdf',
            'convert_to_jpg',
            'jpg_to_pdf',
            'protect_pdf',
            'remove_pages',
            'add_page_numbers',

            # Image Tools
            'compress_page',
            'convert_image_format',
            'resize_images',
            'crop_images',
            'rotate_images',
            'flip_images',
            'add_border',
            'image_to_grayscale',

            # Conversion Tools
            'word_to_pdf',
            'pdf_to_word',
            'excel_to_pdf',
            'text_to_pdf',
            'bulk_image_to_pdf',
            'qr_code_generator',
            'pdf_metadata',

            # Security Tools
            'add_watermark',
            'remove_password',
            'password_strength_checker',

            # Study Tools
            'quiz_generator',
            'flashcard_generator',
            'study_timer',
            'grade_calculator',

            # Productivity Tools
            'pdf_reorganizer',
            'todo_list',
            'word_counter',
        ]

    def location(self, item):
        return reverse(item)