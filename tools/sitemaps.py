from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            'home',
            'merge_pdf',
            'split_pdf',
            'rotate_pdf',
            'convert_to_jpg',
            'jpg_to_pdf',
            'protect_pdf',
            'remove_pages',
            'add_page_numbers',
            'compress_page',
            'convert_image_format',
            'resize_images',
            'crop_images',
            'rotate_images',
            'flip_images',
            'add_border',
            'image_to_grayscale',
            'word_to_pdf',
            'pdf_to_word',
            'pdf_to_text',
            'excel_to_pdf',
            'text_to_pdf',
            'qr_code_generator',
            'study_timetable',
            'quiz_generator',
            'flashcard_generator',
            'password_generator',
        ]

    def location(self, item):
        return reverse(item)