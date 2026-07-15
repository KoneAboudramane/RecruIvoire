"""Wrapper messages auto-taguant chaque message avec 'candidat'."""
from django.contrib import messages as _m


def _tags(kw):
    extra = kw.pop('extra_tags', '') or ''
    tags = {'candidat', *extra.split()}
    return ' '.join(sorted(tags))


def success(request, msg, **kw):
    _m.success(request, msg, extra_tags=_tags(kw), **kw)


def error(request, msg, **kw):
    _m.error(request, msg, extra_tags=_tags(kw), **kw)


def info(request, msg, **kw):
    _m.info(request, msg, extra_tags=_tags(kw), **kw)


def warning(request, msg, **kw):
    _m.warning(request, msg, extra_tags=_tags(kw), **kw)
