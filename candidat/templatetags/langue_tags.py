from django import template
from django.utils.translation import get_language
from django.conf import settings

register = template.Library()


@register.simple_tag(takes_context=True)
def chemin_sans_langue(context):
    """
    Retourne request.path sans le préfixe de langue.
    Ex : /en/candidat/profil/ → /candidat/profil/
         /candidat/profil/    → /candidat/profil/  (langue par défaut, pas de préfixe)
    Cela évite le bug de changement de langue multiple où translate_url() échoue
    à résoudre un chemin déjà préfixé dans le mauvais contexte de langue.
    """
    request = context.get('request')
    if not request:
        return '/'
    path = request.path
    lang = get_language()
    if lang and lang != settings.LANGUAGE_CODE:
        prefix = '/{}/'.format(lang)
        if path.startswith(prefix):
            path = '/' + path[len(prefix):]
    return path
