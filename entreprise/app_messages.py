"""Wrapper messages auto-taguant chaque message avec 'entreprise'."""
from django.contrib import messages as _m


def success(request, msg, **kw):
    _m.success(request, msg, extra_tags='entreprise', **kw)


def error(request, msg, **kw):
    _m.error(request, msg, extra_tags='entreprise', **kw)


def info(request, msg, **kw):
    _m.info(request, msg, extra_tags='entreprise', **kw)


def warning(request, msg, **kw):
    _m.warning(request, msg, extra_tags='entreprise', **kw)
