from django import template

register = template.Library()


@register.simple_tag
def any_active(elements, path):
    """Retourne True si au moins un élément du groupe correspond au chemin actuel."""
    for el in elements:
        if el['correspondance_exacte'] and path == el['url']:
            return True
        if not el['correspondance_exacte'] and el['url'] in path:
            return True
    return False
