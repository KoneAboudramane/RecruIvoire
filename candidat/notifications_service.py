"""
Service de gestion des notifications candidat.

Responsabilités :
  • Création idempotente d'une notification d'alerte d'offre (`creer_notification_match`).
  • Envoi de l'email associé si le candidat a opt-in (`envoyer_email_match`).
  • Scan complet candidats × offres pour rattraper les matchings (`scanner_matchings`).

Le scoring est fait via le `Matcher` (cf. `candidat.matching`). Le seuil par
défaut est 70 — ajustable depuis la commande `notifier_matchings --seuil`.

Idempotence :
  - La contrainte unique sur (candidat, offre, type) protège côté BD.
  - Côté service, on fait un `update_or_create` pour ne JAMAIS créer de doublon.
  - L'envoi d'email est conditionné par `emailEnvoye=False` — pas de spam.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import LogoSite

logger = logging.getLogger(__name__)

# Seuil à partir duquel un candidat est notifié d'une offre
SEUIL_MATCHING_DEFAUT = 70


# ──────────────────────────────────────────────────────────────────────────────
# Création de notification
# ──────────────────────────────────────────────────────────────────────────────

def creer_notification_match(candidat, offre, score: int, source: str = 'recommandation'):
    """Crée (ou récupère) une notification d'alerte pour ce couple candidat/offre.

    Retourne le tuple `(notification, cree)` :
      - notification : instance NotificationCandidat
      - cree : True si nouvellement créée, False si déjà existante

    `source` : 'recommandation' (ML) ou 'alerte' (critères personnalisés).
    """
    from .models import NotificationCandidat

    if source == 'alerte':
        titre = "Une offre correspond à votre alerte emploi"
        message = (
            f"« {offre.titre} » chez {offre.entreprise.raisonSocial} "
            "correspond à l'une de vos alertes emploi. "
            "Consultez l'offre et postulez en quelques clics."
        )
    else:
        titre = f"Nouvelle offre qui vous correspond — {score} %"
        message = (
            f"« {offre.titre} » chez {offre.entreprise.raisonSocial} "
            f"correspond à votre profil à {score}%. "
            "Consultez l'offre et postulez en quelques clics."
        )
    lien = reverse('candidat:offre_detail', kwargs={'offre_id': offre.id})

    # Ne pas créer si le candidat a désactivé les notifications in-app
    if not candidat.notificationsInApp:
        return None, False

    notif, cree = NotificationCandidat.objects.get_or_create(
        candidat=candidat,
        offre=offre,
        type=NotificationCandidat.Type.OFFRE_MATCH,
        defaults={
            'titre':   titre,
            'message': message,
            'lien':    lien,
            'score':   score,
        },
    )
    return notif, cree


# ──────────────────────────────────────────────────────────────────────────────
# Envoi email
# ──────────────────────────────────────────────────────────────────────────────

def envoyer_email_match(notification, request=None) -> bool:
    """Envoie l'email d'alerte au candidat (si opt-in et pas déjà envoyé).

    Args:
        notification : instance NotificationCandidat (type OFFRE_MATCH)
        request : HttpRequest optionnel pour construire des URLs absolues

    Retourne True si l'email a été envoyé maintenant, False sinon (opt-in OFF,
    déjà envoyé, ou erreur SMTP).
    """
    from django.core.mail import EmailMultiAlternatives

    candidat = notification.candidat
    offre    = notification.offre

    # 1. Garde-fous
    if not candidat.notificationsOffresEmail:
        return False
    if notification.emailEnvoye:
        return False
    if not candidat.email:
        return False
    if not offre:
        return False

    # 2. URLs absolues (avec request si dispo, sinon SITE_URL settings)
    if request is not None:
        url_offre = request.build_absolute_uri(notification.lien)
        url_prefs = request.build_absolute_uri(reverse('candidat:profil') + '?onglet=confidentialite')
    else:
        base = getattr(settings, 'SITE_URL', '').rstrip('/')
        url_offre = f"{base}{notification.lien}" if base else notification.lien
        url_prefs = f"{base}{reverse('candidat:profil')}?onglet=confidentialite" if base else ''

    contexte = {
        'candidat':  candidat,
        'offre':     offre,
        'score':     notification.score,
        'url_offre': url_offre,
        'url_prefs': url_prefs,
        'logo_site': LogoSite.get_actif(),
    }

    sujet = f"🎯 Nouvelle offre qui vous correspond — {offre.titre}"
    texte = render_to_string('candidat/emails/notification_match.txt', contexte)
    html  = render_to_string('candidat/emails/notification_match.html', contexte)

    try:
        email = EmailMultiAlternatives(
            subject=sujet,
            body=texte,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[candidat.email],
        )
        email.attach_alternative(html, 'text/html')
        email.send(fail_silently=False)
        notification.marquer_email_envoye()
        return True
    except Exception as e:
        logger.exception("Erreur envoi email alerte à %s : %s", candidat.email, e)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Envoi email générique (tous types sauf OFFRE_MATCH)
# ──────────────────────────────────────────────────────────────────────────────

# Icône affichée dans l'email selon le type de notification
_ICONE_TYPE = {
    'CANDIDATURE': '📋',
    'INVITATION':  '📩',
    'ENTRETIEN':   '🗓️',
    'SYSTEME':     'ℹ️',
}


def envoyer_email_notification(notification, request=None) -> bool:
    """Envoie un email pour n'importe quel type de notification si le candidat a opt-in.

    Utilisée pour les types autres qu'OFFRE_MATCH (CANDIDATURE, MESSAGE,
    INVITATION, ENTRETIEN, SYSTEME). Pour OFFRE_MATCH, utiliser
    `envoyer_email_match` qui dispose d'un template dédié.

    Retourne True si l'email a été envoyé, False sinon.
    """
    from django.core.mail import EmailMultiAlternatives
    from .models import NotificationCandidat

    candidat = notification.candidat

    if not candidat.notificationsOffresEmail:
        return False
    if notification.emailEnvoye:
        return False
    if not candidat.email:
        return False

    if request is not None:
        url_action = request.build_absolute_uri(notification.lien) if notification.lien else ''
        url_prefs  = request.build_absolute_uri(reverse('candidat:profil') + '?onglet=confidentialite')
    else:
        base = getattr(settings, 'SITE_URL', '').rstrip('/')
        url_action = f"{base}{notification.lien}" if (base and notification.lien) else notification.lien
        url_prefs  = f"{base}{reverse('candidat:profil')}?onglet=confidentialite" if base else ''

    icone = _ICONE_TYPE.get(notification.type, '🔔')

    contexte = {
        'candidat':   candidat,
        'notif':      notification,
        'icone':      icone,
        'url_action': url_action,
        'url_prefs':  url_prefs,
        'logo_site':  LogoSite.get_actif(),
    }

    sujet = f"{icone} {notification.titre}"
    texte = render_to_string('candidat/emails/notification_generique.txt', contexte)
    html  = render_to_string('candidat/emails/notification_generique.html', contexte)

    try:
        email = EmailMultiAlternatives(
            subject=sujet,
            body=texte,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[candidat.email],
        )
        email.attach_alternative(html, 'text/html')
        email.send(fail_silently=False)
        notification.marquer_email_envoye()
        logger.info("Email notification %s envoyé à %s", notification.type, candidat.email)
        return True
    except Exception as e:
        logger.exception("Erreur envoi email notification %s à %s : %s",
                         notification.type, candidat.email, e)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Scan candidats × offres
# ──────────────────────────────────────────────────────────────────────────────

def scanner_matchings_pour_offre(offre, seuil: int = SEUIL_MATCHING_DEFAUT,
                                  envoyer_emails: bool = True) -> dict:
    """Scanne tous les candidats actifs pour une offre donnée.

    Deux chemins indépendants, activables séparément par le candidat :
      1. Recommandations automatiques (ML) : si score >= seuil
      2. Alertes personnalisées : si l'offre correspond aux critères définis

    Un seul envoi de notification par offre/candidat (idempotent).
    Retourne un dict de stats : {'analyses': N, 'notifies': N, 'emails': N}.
    """
    from .models import Candidat
    from .matching import Matcher

    candidats = Candidat.objects.filter(emailVerifie=True).prefetch_related('alertesEmploi')
    analyses, notifies, emails = 0, 0, 0

    for candidat in candidats.iterator(chunk_size=200):
        analyses += 1
        try:
            # Chemin 1 : Recommandations automatiques (ML matching)
            if candidat.recommandationsActives:
                matcher = Matcher(candidat)
                r = matcher.scorer(offre)
                if r['score'] >= seuil:
                    notif, cree = creer_notification_match(
                        candidat, offre, r['score'], source='recommandation'
                    )
                    if notif and cree:
                        notifies += 1
                        if envoyer_emails and envoyer_email_match(notif):
                            emails += 1

            # Chemin 2 : Alertes emploi personnalisées (critères manuels) — indépendant
            if candidat.alertesActives:
                for alerte in candidat.alertesEmploi.filter(active=True):
                    if alerte.correspond_a(offre):
                        notif, cree = creer_notification_match(
                            candidat, offre, seuil, source='alerte'
                        )
                        if notif and cree:
                            notifies += 1
                            if envoyer_emails and envoyer_email_match(notif):
                                emails += 1
                        break

        except Exception as e:
            logger.warning("Skip candidat %s : %s", candidat.pk, e)

    return {'analyses': analyses, 'notifies': notifies, 'emails': emails}


def scanner_matchings(seuil: int = SEUIL_MATCHING_DEFAUT,
                       envoyer_emails: bool = True,
                       offre_id: Optional[int] = None) -> dict:
    """Scanne toutes les offres publiées (ou une seule si offre_id fourni).

    Retourne un dict de stats agrégées.
    """
    from entreprise.models import OffreEmploi, StatutOffre

    offres = OffreEmploi.objects.filter(statutOffre=StatutOffre.PUBLIEE)
    if offre_id is not None:
        offres = offres.filter(pk=offre_id)

    total = {'offres': 0, 'analyses': 0, 'notifies': 0, 'emails': 0}
    for offre in offres.select_related('entreprise', 'entreprise__secteurActiviteRef',
                                        'contrat'):
        total['offres'] += 1
        stats = scanner_matchings_pour_offre(offre, seuil=seuil, envoyer_emails=envoyer_emails)
        total['analyses'] += stats['analyses']
        total['notifies'] += stats['notifies']
        total['emails']   += stats['emails']
    return total
