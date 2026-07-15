"""
Service de notifications côté recruteur.

Responsabilités :
  • Création idempotente d'une notification de profil recommandé.
  • Scan automatique d'une offre publiée pour trouver les profils matchant.
  • Lancement async via thread (pas de Celery requis).

Flow d'usage type :
  1. Le recruteur publie une offre.
  2. Un signal `post_save` appelle `lancer_scan_offre_async(offre)`.
  3. Un thread tourne `scanner_profils_pour_offre(offre)` :
       - score tous les candidats publics
       - crée les `PropositionProfil` correspondant
       - crée les `NotificationRecruteur` pour chaque profil au-dessus du seuil
  4. Le recruteur voit une cloche rouge dans sa navbar.

Idempotence : la contrainte unique (recruteur, offre, candidat, type)
empêche tout doublon en base.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from django.db import close_old_connections
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


# Seuil de fallback si l'offre n'a pas défini criteresATS.scoreMinimum
SEUIL_DEFAUT = 60


# ──────────────────────────────────────────────────────────────────────────────
# Création de notification
# ──────────────────────────────────────────────────────────────────────────────

def creer_notification_profil(destinataire, offre, candidat, score: int):
    """Crée (ou récupère) une notification de profil recommandé.

    Args:
        destinataire : instance `Recruteur` ou `Entreprise` (compte admin).
        offre, candidat, score : voir contexte ATS.

    Retourne `(notif, cree)` où `cree=True` si nouvellement créée.
    """
    from .models import NotificationRecruteur, Recruteur, Entreprise

    titre = f"Nouveau profil pour « {offre.titre} » — {int(score)}%"
    nom = f"{candidat.prenom} {candidat.nom}".strip() or candidat.email or "Candidat"
    message = (
        f"{nom} correspond à votre offre à {int(score)}%. "
        "Cliquez pour voir toutes les suggestions de cette offre."
    )
    # Redirection vers la page Suggestions de l'offre, ancrée sur le candidat
    lien = reverse('entreprise:suggestions_offre', args=[offre.id]) + f"#candidat-{candidat.id}"

    kwargs = {
        'offre':    offre,
        'candidat': candidat,
        'type':     NotificationRecruteur.Type.PROFIL_MATCH,
    }
    if isinstance(destinataire, Recruteur):
        kwargs['recruteur'] = destinataire
    elif isinstance(destinataire, Entreprise):
        kwargs['entreprise'] = destinataire
    else:
        raise TypeError(
            f"Destinataire doit être Recruteur ou Entreprise, reçu : {type(destinataire)}"
        )

    notif, cree = NotificationRecruteur.objects.get_or_create(
        defaults={
            'titre':   titre,
            'message': message,
            'lien':    lien,
            'score':   int(score),
        },
        **kwargs,
    )
    return notif, cree


def creer_notification_suggestion(expediteur, destinataire, candidat, note: str = '', nom_exp: str = ''):
    """Notifie un recruteur qu'un collègue (ou l'admin) lui suggère un profil candidat.

    Args:
        expediteur  : Recruteur qui fait la suggestion, ou None si admin entreprise.
        destinataire: Recruteur destinataire de la suggestion.
        candidat    : instance candidat.Candidat.
        note        : message optionnel de l'expéditeur.
        nom_exp     : nom affiché de l'expéditeur (calculé côté vue si besoin).

    Retourne `(notif, cree)`.
    """
    from .models import NotificationRecruteur

    if not nom_exp:
        nom_exp = (f"{expediteur.prenom} {expediteur.nom}").strip() or expediteur.nomComplet or "Un collègue"
    nom_cand = (f"{candidat.prenom} {candidat.nom}").strip() or candidat.email or "Un candidat"

    titre   = f"👥 {nom_exp} vous suggère un profil"
    message = f"{nom_exp} pense que {nom_cand} pourrait vous intéresser."
    if note:
        message += f" — « {note} »"

    lien = reverse('entreprise:voir_portfolio', args=[candidat.id])

    notif, cree = NotificationRecruteur.objects.get_or_create(
        recruteur = destinataire,
        candidat  = candidat,
        type      = NotificationRecruteur.Type.SUGGESTION_COLLEGUE,
        offre     = None,
        defaults  = {
            'titre':        titre,
            'message':      message,
            'lien':         lien,
            'expediteur':   expediteur,
            'expediteur_nom': nom_exp,
        },
    )
    if not cree:
        notif.titre          = titre
        notif.message        = message
        notif.lue            = False
        notif.expediteur     = expediteur
        notif.expediteur_nom = nom_exp
        notif.save(update_fields=['titre', 'message', 'lue', 'expediteur', 'expediteur_nom'])

    return notif, cree


# ──────────────────────────────────────────────────────────────────────────────
# Récupération des destinataires
# ──────────────────────────────────────────────────────────────────────────────

def _destinataires_offre(offre) -> list:
    """Destinataires à notifier pour une offre — filtrés par leur opt-in ATS.

    Stratégie de sélection :
      1. Recruteurs liés via `OffreEmploiRecruteur` (créateurs/collaborateurs)
         filtrés par `recevoirNotifsATS=True` et `estActif=True`.
      2. Si aucun recruteur lié → la publication vient du compte admin
         entreprise lui-même → on notifie l'Entreprise (si opt-in).

    Retourne une liste mixte de `Recruteur` et/ou `Entreprise`.
    """
    from .models import Recruteur

    recruteurs = list(
        Recruteur.objects.filter(
            offres_createurs__offre=offre,
            recevoirNotifsATS=True,
            estActif=True,
        ).distinct()
    )
    if recruteurs:
        return recruteurs

    # Pas de recruteur lié → publication par le compte admin entreprise
    entreprise = offre.entreprise
    if entreprise and entreprise.recevoirNotifsATS:
        return [entreprise]
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Scan principal
# ──────────────────────────────────────────────────────────────────────────────

def scanner_profils_pour_offre(offre, seuil: Optional[int] = None) -> dict:
    """Scanne tous les candidats publics et crée des notifications pour les
    profils correspondant à l'offre.

    Returns:
        dict avec stats : {
            'offre_id': int,
            'seuil': int,
            'analyses': int,        # nombre de candidats scorés
            'matches': int,         # nombre de scores >= seuil
            'notifs_creees': int,   # nouvelles notifs (hors doublons)
            'recruteurs_notifies': int,
        }
    """
    from candidat.models import Candidat
    from .models import PropositionProfil
    from . import ats_predict, ats_ml

    if seuil is None:
        seuil = int((offre.criteresATS or {}).get('scoreMinimum', SEUIL_DEFAUT))

    candidats = list(
        Candidat.objects
        .filter(portfolioPublic=True)
        .select_related('informationPersonnelle')
    )
    if not candidats:
        return {
            'offre_id': offre.id, 'seuil': seuil,
            'analyses': 0, 'matches': 0,
            'notifs_creees': 0, 'recruteurs_notifies': 0,
        }

    try:
        scores = ats_predict.scorer_candidats(offre, candidats)
    except Exception as exc:
        logger.exception("Échec scoring ATS pour offre #%s : %s", offre.id, exc)
        return {
            'offre_id': offre.id, 'seuil': seuil,
            'analyses': 0, 'matches': 0,
            'notifs_creees': 0, 'recruteurs_notifies': 0,
            'erreur': str(exc),
        }

    # Re-rank ML si dispo
    try:
        if ats_ml.est_disponible():
            scores = ats_ml.reranker(offre, candidats, scores)
    except Exception:
        logger.warning("Re-ranking ML échoué — fallback ATS brut.", exc_info=True)

    matches = [r for r in scores if r['score'] >= seuil]

    # Persistance des PropositionProfil (sans écraser une action existante)
    par_id = {c.id: c for c in candidats}
    for r in matches:
        PropositionProfil.objects.update_or_create(
            offre=offre,
            candidat_id=r['candidat_id'],
            defaults={'scoreATS': r['score']},
        )

    # Notifications par recruteur destinataire
    destinataires = _destinataires_offre(offre)
    nb_notifs = 0
    for r in matches:
        cand = par_id.get(r['candidat_id'])
        if cand is None:
            continue
        for destinataire in destinataires:
            _, cree = creer_notification_profil(
                destinataire, offre=offre, candidat=cand,
                score=int(r['score']),
            )
            if cree:
                nb_notifs += 1

    # ── Notifications côté CANDIDAT : suggestion d'offre matchante ──────────
    # Pour chaque candidat dont le profil matche, on crée (ou met à jour) une
    # NotificationCandidat de type OFFRE_MATCH. Le candidat verra la cloche
    # dans son espace et pourra ouvrir l'offre depuis son fil de notifications.
    nb_notifs_candidats = _notifier_candidats_matchants(offre, matches, par_id)

    logger.info(
        "Scan offre #%s : %s candidats, %s matches ≥%s, %s notifs recruteur, "
        "%s notifs candidat, %s destinataires.",
        offre.id, len(scores), len(matches), seuil,
        nb_notifs, nb_notifs_candidats, len(destinataires),
    )

    return {
        'offre_id':             offre.id,
        'seuil':                seuil,
        'analyses':             len(scores),
        'matches':              len(matches),
        'notifs_creees':        nb_notifs,
        'notifs_candidats':     nb_notifs_candidats,
        'recruteurs_notifies':  len(destinataires),
    }


def _notifier_candidats_matchants(offre, matches, par_id) -> int:
    """Crée une NotificationCandidat (type OFFRE_MATCH) pour chaque candidat matché.

    Utilise update_or_create pour rester idempotent (contrainte UNIQUE sur
    candidat+offre+type). Retourne le nombre total traité (créés ou mis à jour).
    """
    from candidat.models import NotificationCandidat

    if not matches:
        return 0

    entreprise = offre.entreprise
    raison = entreprise.raisonSocial if entreprise else ''
    lien   = reverse('candidat:offre_detail', args=[offre.id])

    nb = 0
    for r in matches:
        cand = par_id.get(r['candidat_id'])
        if cand is None:
            continue
        score = int(r['score'])
        try:
            NotificationCandidat.objects.update_or_create(
                candidat = cand,
                type     = NotificationCandidat.Type.OFFRE_MATCH,
                offre    = offre,
                defaults = {
                    'titre':   f"🎯 Offre suggérée — {offre.titre}",
                    'message': f"Votre profil correspond à {score}% à cette offre"
                               + (f" chez {raison}." if raison else "."),
                    'lien':    lien,
                    'score':   score,
                    'lue':     False,
                },
            )
            nb += 1
        except Exception:
            logger.exception(
                "Echec creation NotificationCandidat (candidat=%s, offre=%s)",
                cand.id, offre.id,
            )
    return nb


# ──────────────────────────────────────────────────────────────────────────────
# Lancement asynchrone via thread
# ──────────────────────────────────────────────────────────────────────────────

def lancer_scan_offre_async(offre):
    """Spawn un thread démon pour scanner l'offre sans bloquer la requête HTTP.

    En prod avec Gunicorn/uWSGI : OK, chaque worker peut spawner ses threads.
    En dev runserver : OK aussi.
    Pour scaler vraiment (Celery), remplacer cette fonction par un .delay().
    """
    def _run(offre_id):
        # Recharge l'offre dans la nouvelle thread (Django ORM thread-safe via
        # transactions séparées). On évite de passer l'instance qui peut être
        # invalidée si la transaction parente n'est pas committée.
        from .models import OffreEmploi
        try:
            offre_fresh = OffreEmploi.objects.get(pk=offre_id)
            scanner_profils_pour_offre(offre_fresh)
            # Notifier les alertes emploi personnalisées des candidats
            try:
                from candidat.notifications_service import scanner_matchings_pour_offre
                scanner_matchings_pour_offre(offre_fresh)
            except Exception:
                logger.exception("Alertes emploi candidats échouées pour offre #%s", offre_id)
        except Exception:
            logger.exception("Scan async échoué pour offre #%s", offre_id)
        finally:
            close_old_connections()

    t = threading.Thread(target=_run, args=(offre.id,), daemon=True)
    t.start()
    return t
