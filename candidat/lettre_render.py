"""Rendu fidèle des lettres en PDF / PNG / JPG via Playwright (Chromium headless).

Même pipeline que cv_render.py : on charge le template standalone de la lettre
(`candidat/lettreMo/modeles/{slug}.html`) dans Chromium, on attend networkidle,
puis on génère le PDF. Pas d'Alpine.js ni de pagination — le template est
purement server-side (Django vars), donc le rendu est immédiat.
"""

import io
import logging

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

_PDF_OPTIONS = {
    'format'           : 'A4',
    'print_background' : True,
    'margin'           : {'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
    'prefer_css_page_size': True,
}

_IMAGE_DPI = 200


def _render_html(modele, lettre_data, request):
    html = render_to_string(
        'candidat/lettreMo/lettre_render.html',
        {'lettre': lettre_data, 'modele': modele},
        request=request,
    )
    base_url = request.build_absolute_uri('/')
    if '<head>' in html:
        html = html.replace('<head>', f'<head><base href="{base_url}">', 1)
    else:
        html = f'<base href="{base_url}">' + html
    return html


def _generate_pdf_bytes(html):
    from .cv_render import run_on_browser_thread

    return run_on_browser_thread(_generate_pdf_bytes_on_worker, html)


def _generate_pdf_bytes_on_worker(browser, html):
    context = browser.new_context(viewport={'width': 794, 'height': 1123})
    try:
        page = context.new_page()
        page.set_content(html, wait_until='networkidle', timeout=30_000)
        try:
            page.evaluate('() => document.fonts ? document.fonts.ready : null')
        except Exception:
            pass
        page.add_style_tag(content='@page { size: A4 portrait; margin: 0; }')
        return page.pdf(**_PDF_OPTIONS)
    finally:
        context.close()


def _pdf_to_image(pdf_bytes, fmt='png'):
    import fitz
    from PIL import Image

    doc    = fitz.open(stream=pdf_bytes, filetype='pdf')
    zoom   = _IMAGE_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    pix    = doc.load_page(0).get_pixmap(matrix=matrix, alpha=False)
    doc.close()

    if fmt == 'jpg':
        img = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92, optimize=True)
        return buf.getvalue()
    return pix.tobytes('png')


def render_pdf(modele, lettre_data, request):
    """Retourne les bytes PDF de la lettre (rendu Chromium — identique à l'aperçu)."""
    html = _render_html(modele, lettre_data, request)
    return _generate_pdf_bytes(html)


def render_image(modele, lettre_data, request, fmt='png'):
    """Retourne la première page de la lettre en image PNG ou JPG."""
    pdf_bytes = render_pdf(modele, lettre_data, request)
    return _pdf_to_image(pdf_bytes, fmt=fmt)
