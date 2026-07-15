"""
Commande Django : envoie le résumé hebdomadaire des candidatures aux abonnés
ayant coché `resume_candidatures`.

Seuls les candidats inscrits (abonnement_newsletter.candidat non nul) sont
concernés. Les abonnés anonymes sont ignorés automatiquement.
Ne rien envoyer si le candidat n'a aucune candidature active.

Usage :
    python manage.py envoyer_resume_candidatures
    python manage.py envoyer_resume_candidatures --dry-run
    python manage.py envoyer_resume_candidatures --candidat 42
"""

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone


# Statuts considérés comme « actifs » (en cours de traitement)
CODES_ACTIFS    = {'POSTULEE', 'PRESELECTIONNEE', 'ENTRETIEN', 'TEST'}
# Statuts finaux récents (clôturés dans les 7 derniers jours)
CODES_RECENTS   = {'ACCEPTEE', 'REFUSEE', 'RETIREE'}


class Command(BaseCommand):
    help = "Envoie le résumé hebdomadaire des candidatures aux abonnés."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les stats sans envoyer aucun email.')
        parser.add_argument('--candidat', type=int, default=None,
                            help='Limiter à un candidat précis (ID).')

    def handle(self, *args, **opts):
        from candidat.models import AbonneNewsletter, LogoSite
        from datetime import timedelta

        dry_run     = opts['dry_run']
        candidat_id = opts['candidat']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n> Envoi newsletter — Résumé hebdomadaire candidatures"
        ))
        self.stdout.write(f"  Mode : {'DRY-RUN' if dry_run else 'REEL'}")

        qs = (
            AbonneNewsletter.objects
            .filter(actif=True, resume_candidatures=True, candidat__isnull=False)
            .select_related('candidat')
        )
        if candidat_id:
            qs = qs.filter(candidat_id=candidat_id)

        logo_site   = LogoSite.get_actif()
        depuis_7j   = timezone.now() - timedelta(days=7)
        stats       = {'envoyes': 0, 'ignores': 0, 'erreurs': 0}

        for abonne in qs:
            candidat   = abonne.candidat
            donnees    = _collecter_candidatures(candidat, depuis_7j)

            if not donnees['actives'] and not donnees['recentes']:
                stats['ignores'] += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] {candidat.email} — "
                    f"{len(donnees['actives'])} active(s), "
                    f"{len(donnees['recentes'])} récente(s)"
                )
                stats['envoyes'] += 1
                continue

            try:
                _envoyer_email(abonne, candidat, donnees, logo_site)
                stats['envoyes'] += 1
            except Exception as e:
                stats['erreurs'] += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {candidat.email} : {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n=== Résultats ==="
            f"\n  Envoyés  : {stats['envoyes']}"
            f"\n  Ignorés  : {stats['ignores']} (aucune candidature active)"
            f"\n  Erreurs  : {stats['erreurs']}"
        ))


# ── Collecte des candidatures ─────────────────────────────────────────────────

def _collecter_candidatures(candidat, depuis_7j):
    """Retourne les candidatures actives + les clôturées dans les 7 derniers jours."""
    from candidat.models import Candidature

    toutes = (
        Candidature.objects
        .filter(candidat=candidat)
        .select_related('offre', 'offre__entreprise', 'statut')
        .order_by('-dateCandidature')
    )

    actives, recentes = [], []
    for c in toutes:
        code = c.statut.code if c.statut else None
        if code in CODES_ACTIFS:
            actives.append(c)
        elif code in CODES_RECENTS and c.dateCandidature >= depuis_7j:
            recentes.append(c)

    # Stats par statut pour les actives
    stats = {}
    for c in actives:
        label = c.statut.libelle if c.statut else 'En attente'
        stats[label] = stats.get(label, 0) + 1

    return {
        'actives':  actives,
        'recentes': recentes,
        'stats':    stats,
        'total_actives': len(actives),
        'total_recentes': len(recentes),
    }


# ── Envoi email ───────────────────────────────────────────────────────────────

def _envoyer_email(abonne, candidat, donnees, logo_site):
    from django.conf import settings

    site_url   = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    desabo_url = f'{site_url}/candidat/newsletter/desabonnement/{abonne.token_desabonnement}/'

    ctx = {
        'logo_site':  logo_site,
        'candidat':   candidat,
        'donnees':    donnees,
        'desabo_url': desabo_url,
        'site_url':   site_url,
        'semaine':    timezone.now().strftime('%d %B %Y'),
    }

    sujet = f"📊 Votre résumé candidatures — {logo_site.nom_site}"
    txt   = render_to_string('candidat/newsletter/email_resume_candidatures.txt',  ctx)
    html  = render_to_string('candidat/newsletter/email_resume_candidatures.html', ctx)

    msg = EmailMultiAlternatives(subject=sujet, body=txt, to=[candidat.email])
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)
