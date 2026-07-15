"""Rendu fidèle des CV en PDF / PNG / JPG via Playwright (Chromium headless).

Le pipeline est unique : on rend le template `candidat/cv/modeles/{fichier}.html`
exactement comme dans l'aperçu, on charge le HTML dans Chromium, on attend
qu'Alpine.js peuple le `#cv-sheet`, on émule le média `print` (qui active le
CSS `@media print` déjà défini dans `_form_styles.html` — masque navbar /
formulaire / footer et fixe la feuille à 210×297 mm), puis on demande un PDF.

Pour les images (PNG / JPG), on rasterise le PDF avec pymupdf (`fitz`) à
200 dpi → une image par page A4. Le résultat est strictement identique au
rendu navigateur sur la même page.

Aucun roundtrip HTTP n'est fait par Chromium : on utilise `page.set_content`
avec le HTML server-side rendu, et on injecte `<base href>` pour que les URLs
relatives (`/static/...`, `/media/...`) résolvent vers le serveur Django.
Pas de gestion de session ni de cookies à passer côté Playwright.

Le navigateur Chromium est partagé via un pool persistant (singleton) :
une seule instance est lancée au premier appel et réutilisée pour toutes
les générations suivantes, ce qui réduit la latence et la consommation
mémoire.

Playwright (API sync) lie son dispatcher au THREAD qui appelle
`sync_playwright().start()` : impossible d'utiliser ensuite le navigateur
depuis un autre thread (`greenlet.error: cannot switch to a different
thread`). Comme Django/Daphne traite chaque requête sur un thread du pool
ASGI (pas garanti stable d'une requête à l'autre), le navigateur et toutes
les opérations Playwright (new_context, new_page, pdf...) tournent sur un
thread dédié unique et persistant ; chaque appel de rendu est marshalé vers
ce thread via `run_on_browser_thread`.
"""

import asyncio
import io
import logging
import queue
import sys
import threading

from django.template.loader import render_to_string


logger = logging.getLogger(__name__)


# ── Thread dédié Chromium ───────────────────────────────────────────────────

_worker_thread = None
_worker_queue = None
_worker_lock = threading.Lock()


def _launch_browser(playwright):
    # Sous Windows, Daphne (Twisted) impose une SelectorEventLoop au niveau du
    # processus, incompatible avec les sous-processus (Chromium). On bascule
    # temporairement sur une ProactorEventLoop le temps du démarrage : la
    # boucle créée à cet instant est ensuite conservée et réutilisée par
    # Playwright pour tous les appels suivants, donc restaurer la policy
    # juste après n'affecte pas le fonctionnement ultérieur.
    previous_policy = None
    if sys.platform == 'win32':
        previous_policy = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        return playwright.chromium.launch(headless=True)
    finally:
        if previous_policy is not None:
            asyncio.set_event_loop_policy(previous_policy)


def _worker_main(job_queue):
    from playwright.sync_api import sync_playwright

    # `sync_playwright().start()` crée aussi une event loop (pour le driver
    # Playwright lui-même) : elle doit être Proactor dès sa création, sinon
    # le lancement du navigateur juste après échoue avec le même
    # NotImplementedError que `_launch_browser` corrige pour les relances.
    previous_policy = None
    if sys.platform == 'win32':
        previous_policy = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    finally:
        if previous_policy is not None:
            asyncio.set_event_loop_policy(previous_policy)
    logger.info("Pool Chromium : navigateur lancé (thread dédié).")

    while True:
        func, args, kwargs, result_box = job_queue.get()
        try:
            if not browser.is_connected():
                browser = _launch_browser(playwright)
                logger.info("Pool Chromium : navigateur relancé après déconnexion.")
            result_box['value'] = func(browser, *args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - propagé tel quel à l'appelant
            result_box['error'] = exc
        finally:
            result_box['event'].set()


def _ensure_worker():
    global _worker_thread, _worker_queue
    if _worker_thread is None or not _worker_thread.is_alive():
        with _worker_lock:
            if _worker_thread is None or not _worker_thread.is_alive():
                _worker_queue = queue.Queue()
                _worker_thread = threading.Thread(
                    target=_worker_main, args=(_worker_queue,),
                    daemon=True, name='cv-render-chromium',
                )
                _worker_thread.start()


# Borne max d'attente d'un job de rendu, avec marge par rapport aux timeouts
# internes (networkidle 30s + Alpine 4s + pagination 3s + génération
# PDF/rasterisation) pour ne pas se déclencher en usage normal, tout en
# évitant qu'un job bloqué gèle indéfiniment un thread HTTP Daphne en attente.
_JOB_TIMEOUT_S = 90


def run_on_browser_thread(func, *args, **kwargs):
    """Exécute `func(browser, *args, **kwargs)` sur le thread dédié qui
    possède l'instance Chromium (voir note de module ci-dessus)."""
    _ensure_worker()
    result_box = {'event': threading.Event()}
    _worker_queue.put((func, args, kwargs, result_box))
    if not result_box['event'].wait(timeout=_JOB_TIMEOUT_S):
        logger.error("Rendu Playwright : timeout après %ss, job abandonné côté appelant.", _JOB_TIMEOUT_S)
        raise TimeoutError(f"Le rendu Playwright n'a pas répondu après {_JOB_TIMEOUT_S}s.")
    if 'error' in result_box:
        raise result_box['error']
    return result_box['value']


# ── Constantes ───────────────────────────────────────────────────────────────

# Format PDF : A4 portrait, marges nulles (la feuille HTML #cv-sheet fait elle-même
# 210×297 mm via @media print, on lui laisse occuper toute la page).
_PDF_OPTIONS = {
    'format'           : 'A4',
    'print_background' : True,
    'margin'           : {'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
    'prefer_css_page_size': True,
}

# Délai max attendu pour qu'Alpine.js initialise le rendu (en ms). Au-delà, on
# génère malgré tout (le CV est probablement déjà rendu).
_ALPINE_TIMEOUT_MS = 4000

# Délai max attendu pour que le moteur de pagination JS soit stable (`window
# .__cvPaginationReady === true`). Au-delà, on génère avec ce qui est calculé.
_PAGINATION_TIMEOUT_MS = 3000

# DPI de rastérisation des images (PNG/JPG).
_IMAGE_DPI = 200


# ── Rendu HTML ───────────────────────────────────────────────────────────────

def _render_template_html(modele, cv_data, request):
    """Rend le template d'aperçu du CV avec les données fournies, et injecte
    `<base href>` pour que les ressources statiques résolvent côté Chromium.
    """
    html = render_to_string(
        f'candidat/cv/modeles/{modele.fichier}.html',
        {
            'modele':      modele,
            'modeles':     [modele],          # restreint le sélecteur de modèles à 1 entrée
            'apercu':      False,             # mode "édition" → cv_initial sera lu par Alpine
            'cv_initial':  cv_data,           # injecté en JSON via {% json_script %}
            'candidat_id': getattr(getattr(request, 'candidat', None), 'pk', None),
        },
        request=request,
    )
    base_url = request.build_absolute_uri('/')
    # `<base href>` doit précéder TOUS les autres éléments avec URL relative dans <head>.
    if '<head>' in html:
        html = html.replace('<head>', f'<head><base href="{base_url}">', 1)
    else:
        html = f'<base href="{base_url}">' + html
    return html


# ── Pipeline Playwright ──────────────────────────────────────────────────────

def _generate_pdf_bytes(html):
    """Génère le PDF sur le thread dédié Chromium (voir `run_on_browser_thread`).
    Un nouveau contexte (onglet isolé) est créé et fermé à chaque appel,
    mais le navigateur reste en mémoire entre les appels.
    """
    return run_on_browser_thread(_generate_pdf_bytes_on_worker, html)


def _generate_pdf_bytes_on_worker(browser, html):
    context = browser.new_context(viewport={'width': 794, 'height': 1123})
    try:
        page = context.new_page()
        page.set_content(html, wait_until='networkidle', timeout=30_000)

        try:
            page.wait_for_function(
                'document.querySelector("#cv-sheet, .cv-sheet-ts")?.innerText.trim().length > 20',
                timeout=_ALPINE_TIMEOUT_MS,
            )
        except Exception:
            logger.warning('Alpine ready timeout — génération sans attente prolongée.')

        try:
            page.evaluate('() => document.fonts ? document.fonts.ready : null')
        except Exception:
            pass

        try:
            page.wait_for_function(
                'window.__cvPaginationReady === true',
                timeout=_PAGINATION_TIMEOUT_MS,
            )
        except Exception:
            logger.warning('Pagination JS ready timeout — PDF capturé en l\'état.')

        page.evaluate('() => window.__cvPrepareForPdfRender && window.__cvPrepareForPdfRender()')
        page.wait_for_timeout(100)
        page.add_style_tag(content='@page { size: A4 portrait; margin: 0; }')

        return page.pdf(**_PDF_OPTIONS)
    finally:
        context.close()


def _pdf_to_pages(pdf_bytes, fmt='png'):
    """Rasterise un PDF multi-pages en images (une par page) via pymupdf."""
    import fitz
    from PIL import Image

    pages = []
    doc   = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        zoom   = _IMAGE_DPI / 72  # 72 dpi = unit PDF
        matrix = fitz.Matrix(zoom, zoom)
        for i in range(doc.page_count):
            pix = doc.load_page(i).get_pixmap(matrix=matrix, alpha=False)
            png = pix.tobytes('png')
            if fmt == 'jpg':
                img = Image.open(io.BytesIO(png)).convert('RGB')
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=92, optimize=True)
                pages.append(buf.getvalue())
            else:
                pages.append(png)
    finally:
        doc.close()
    return pages


# ── API publique ─────────────────────────────────────────────────────────────

def render_pdf(modele, cv_data, request):
    """Génère le CV en PDF (A4) — bytes prêts à servir en réponse HTTP."""
    html = _render_template_html(modele, cv_data, request)
    return _generate_pdf_bytes(html)


def render_image(modele, cv_data, request, fmt='png'):
    """Génère la **première page** du CV en image (PNG ou JPG)."""
    pdf_bytes = render_pdf(modele, cv_data, request)
    pages     = _pdf_to_pages(pdf_bytes, fmt=fmt)
    return pages[0] if pages else b''


def render_pages(modele, cv_data, request, fmt='png'):
    """Génère le PDF + une image par page (multi-pages).

    Retourne `(pdf_bytes, [page1_bytes, page2_bytes, ...])`. Utile pour
    enregistrer toutes les pages comme thumbnails.
    """
    pdf_bytes = render_pdf(modele, cv_data, request)
    pages     = _pdf_to_pages(pdf_bytes, fmt=fmt)
    return pdf_bytes, pages
