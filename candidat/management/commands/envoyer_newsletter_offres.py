"""
Commande Django : envoie les 5 meilleures offres de la semaine aux abonnés
ayant coché l'option `offres_semaine`.

  - Candidats inscrits  → top 5 via le moteur de matching (personnalisé)
  - Visiteurs anonymes  → top 5 scorées par recency + popularité (général)

Usage :
    python manage.py envoyer_newsletter_offres
    python manage.py envoyer_newsletter_offres --dry-run   # stats sans envoi
    python manage.py envoyer_newsletter_offres --limit 20  # max 20 abonnés (test)

Planification recommandée :
    Chaque lundi à 8h00 via le Planificateur de tâches Windows ou cron Linux.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import now as tz_now


NB_OFFRES = 5          # nombre d'offres dans chaque email
FENETRE_JOURS = 30     # offres publiées dans les X derniers jours


class Command(BaseCommand):
    help = "Envoie les 5 meilleures offres de la semaine aux abonnés newsletter."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les stats sans envoyer aucun email.')
        parser.add_argument('--limit', type=int, default=None,
                            help='Limite le nombre d\'abonnés traités (pour les tests).')

    def handle(self, *args, **opts):
        from candidat.models import AbonneNewsletter, LogoSite
        from entreprise.models import OffreEmploi, StatutOffre

        dry_run = opts['dry_run']
        limit   = opts['limit']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n> Envoi newsletter — Offres de la semaine"
        ))
        self.stdout.write(
            f"  Mode : {'DRY-RUN (aucun email envoyé)' if dry_run else 'REEL'}"
            + (f" | Limite : {limit} abonnés" if limit else "")
        )

        # ── Offres publiées dans la fenêtre de 30 jours ──────────────────────
        depuis = timezone.now() - timedelta(days=FENETRE_JOURS)
        offres_qs = (
            OffreEmploi.objects
            .filter(statutOffre=StatutOffre.PUBLIEE, datePublication__gte=depuis)
            .select_related('entreprise')
            .order_by('-datePublication')
        )
        offres_liste = list(offres_qs)

        if not offres_liste:
            self.stdout.write(self.style.WARNING(
                "  Aucune offre publiée dans les 30 derniers jours. Arrêt."
            ))
            return

        self.stdout.write(f"  Offres disponibles : {len(offres_liste)}")

        # ── Sélection générale pour anonymes (calculée 1 seule fois) ─────────
        offres_generales = _top_offres_generales(offres_liste, nb=NB_OFFRES)

        # ── Abonnés concernés ─────────────────────────────────────────────────
        qs_abonnes = (
            AbonneNewsletter.objects
            .filter(actif=True, offres_semaine=True)
            .select_related('candidat')
        )
        if limit:
            qs_abonnes = qs_abonnes[:limit]

        abonnes = list(qs_abonnes)
        self.stdout.write(f"  Abonnés à traiter : {len(abonnes)}")

        logo_site = LogoSite.get_actif()

        # Marquer le début d'exécution dans PlanificationNewsletter
        from candidat.models import PlanificationNewsletter
        planif = PlanificationNewsletter.singleton()
        if not dry_run:
            planif.derniere_status  = 'running'
            planif.derniere_message = ''
            planif.save(update_fields=['derniere_status', 'derniere_message'])

        stats = {'envoyes': 0, 'ignores': 0, 'erreurs': 0}

        for abonne in abonnes:
            if abonne.candidat:
                offres = _top_offres_candidat(abonne.candidat, offres_liste, nb=NB_OFFRES)
                type_envoi = 'personnalisé'
            else:
                offres = offres_generales
                type_envoi = 'général'

            if not offres:
                stats['ignores'] += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] {abonne.email} ({type_envoi}) "
                    f"→ {len(offres)} offres"
                )
                stats['envoyes'] += 1
                continue

            try:
                _envoyer_email(abonne, offres, logo_site)
                stats['envoyes'] += 1
            except Exception as e:
                stats['erreurs'] += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Erreur pour {abonne.email} : {e}"
                ))

        resume = (
            f"Envoyés : {stats['envoyes']} | "
            f"Ignorés : {stats['ignores']} | "
            f"Erreurs : {stats['erreurs']}"
        )
        self.stdout.write(self.style.SUCCESS(f"\n=== Résultats ===\n  {resume}"))

        # Mettre à jour PlanificationNewsletter après l'exécution
        if not dry_run:
            statut_final = 'error' if stats['erreurs'] and not stats['envoyes'] else 'ok'
            planif.derniere_execution  = timezone.now()
            planif.derniere_status     = statut_final
            planif.derniere_message    = resume
            planif.prochaine_execution = planif.calculer_prochaine_execution()
            planif.save(update_fields=[
                'derniere_execution', 'derniere_status',
                'derniere_message', 'prochaine_execution',
            ])


# ── Sélection des offres ──────────────────────────────────────────────────────

def _top_offres_generales(offres: list, nb: int) -> list:
    """Top N offres scorées par recency (60 %) + popularité/vues (40 %)."""
    if not offres:
        return []

    maintenant = timezone.now()
    max_vues = max((o.nbVues for o in offres), default=1) or 1

    def _score(offre):
        # Recency : 1.0 si publiée aujourd'hui, 0.0 si publiée il y a FENETRE_JOURS jours
        age_jours = max(0, (maintenant - (offre.datePublication or maintenant)).days)
        recency = max(0.0, 1.0 - age_jours / FENETRE_JOURS)
        popularite = offre.nbVues / max_vues
        return recency * 0.6 + popularite * 0.4

    return sorted(offres, key=_score, reverse=True)[:nb]


def _top_offres_candidat(candidat, offres: list, nb: int) -> list:
    """Top N offres via le moteur de matching (personnalisé pour ce candidat)."""
    try:
        from candidat.matching import Matcher
        matcher  = Matcher(candidat)
        resultats = matcher.scorer_plusieurs(offres)
        resultats.sort(key=lambda r: r['score'], reverse=True)
        return [r['offre'] for r in resultats[:nb]]
    except Exception:
        # Repli sur la sélection générale si le matching échoue
        return _top_offres_generales(offres, nb=nb)


# ── Envoi email ───────────────────────────────────────────────────────────────

def _envoyer_email(abonne, offres: list, logo_site):
    from django.conf import settings

    site_url   = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    desabo_url = f'{site_url}/candidat/newsletter/desabonnement/{abonne.token_desabonnement}/'
    personnalise = abonne.candidat is not None

    ctx = {
        'logo_site':    logo_site,
        'abonne':       abonne,
        'offres':       offres,
        'personnalise': personnalise,
        'desabo_url':   desabo_url,
        'nb_offres':    len(offres),
        'site_url':     site_url,
    }

    sujet = f"🔥 {len(offres)} offres d'emploi cette semaine — {logo_site.nom_site}"
    txt   = render_to_string('candidat/newsletter/email_offres_semaine.txt',  ctx)
    html  = render_to_string('candidat/newsletter/email_offres_semaine.html', ctx)

    msg = EmailMultiAlternatives(
        subject=sujet,
        body=txt,
        to=[abonne.email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)
