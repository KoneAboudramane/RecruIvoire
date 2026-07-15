"""Team / members management views (entreprise app)."""
import logging

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..decorators import admin_required
from ..models import Recruteur, RoleMembre

from candidat.models import LogoSite

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# GESTION DES MEMBRES (vue entreprise)
# ════════════════════════════════════════════════════════════════════════════════

@admin_required
def membres_liste(request):
    from django.db.models import Q as _Q
    from ..models import DROITS_DEFAUT

    tous = request.entreprise.recruteurs.all().select_related('entreprise')
    stats = {
        'total':   tous.count(),
        'actifs':  tous.filter(estActif=True).count(),
        'admin':   tous.filter(roleMembre=RoleMembre.ADMIN).count(),
        'rh':      tous.filter(roleMembre=RoleMembre.RH).count(),
        'manager': tous.filter(roleMembre=RoleMembre.MANAGER).count(),
        'lecteur': tous.filter(roleMembre=RoleMembre.LECTEUR).count(),
    }

    # ── Filtres ──────────────────────────────────────────────────────────
    q             = request.GET.get('q', '').strip()
    role_filtre   = request.GET.get('role', '').strip()
    statut_filtre = request.GET.get('statut', '').strip()

    membres = tous.order_by('roleMembre', 'nomComplet')
    if q:
        from recrutement.search import fts_filter
        membres = fts_filter(membres, q,
                             vector_fields=['nom', 'prenom'],
                             fallback_lookups=['nomComplet__icontains',
                                              'emailProfessionnel__icontains'])
    if role_filtre and role_filtre in dict(RoleMembre.choices):
        membres = membres.filter(roleMembre=role_filtre)
    if statut_filtre == 'actif':
        membres = membres.filter(estActif=True)
    elif statut_filtre == 'inactif':
        membres = membres.filter(estActif=False)

    # Matrice permissions pré-traitée pour le template
    ressources = ['offres', 'candidatures', 'entretiens', 'membres', 'statistiques', 'parametres']
    roles_ordre = ['ADMIN', 'RH', 'MANAGER', 'LECTEUR']
    matrice = []
    for r in ressources:
        ligne = {'ressource': r, 'droits': {}}
        for role in roles_ordre:
            actions = DROITS_DEFAUT.get(role, {}).get(r, [])
            ligne['droits'][role] = ', '.join(actions) if actions else '—'
        matrice.append(ligne)

    return render(request, 'entreprise/membres/liste.html', {
        'membres':        membres,
        'stats':          stats,
        'roles':          RoleMembre.choices,
        'matrice':        matrice,
        'q':              q,
        'role_filtre':    role_filtre,
        'statut_filtre':  statut_filtre,
    })


def _generer_mdp_membre(longueur=10):
    import secrets
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(longueur))


@admin_required
def ajouter_membre(request):
    if request.method != 'POST':
        return render(request, 'entreprise/membres/ajouter.html', {
            'roles': RoleMembre.choices,
        })

    data   = request.POST
    errors = {}

    nom   = data.get('nomComplet', '').strip()
    email = data.get('emailProfessionnel', '').strip().lower()
    role  = data.get('roleMembre', RoleMembre.RH)

    if not nom:
        errors['nomComplet'] = 'Le nom complet est obligatoire.'
    if not email:
        errors['emailProfessionnel'] = "L'email professionnel est obligatoire."
    elif Recruteur.objects.filter(emailProfessionnel=email).exists():
        errors['emailProfessionnel'] = 'Cet email est déjà utilisé par un autre recruteur.'
    if role not in dict(RoleMembre.choices):
        errors['roleMembre'] = 'Rôle invalide.'

    if errors:
        return render(request, 'entreprise/membres/ajouter.html', {
            'errors': errors, 'data': data, 'roles': RoleMembre.choices,
        })

    mdp = _generer_mdp_membre()

    rec = Recruteur(
        entreprise         = request.entreprise,
        nomComplet         = nom,
        emailProfessionnel = email,
        roleMembre         = role,
        telephone          = data.get('telephone', '').strip(),
        dateEmbauche       = timezone.now().date(),
    )
    rec.set_password(mdp)
    rec.initialiserDroits()
    with transaction.atomic():
        rec.save()
        request.entreprise.nombreMembre = request.entreprise.recruteurs.filter(estActif=True).count()
        request.entreprise.save(update_fields=['nombreMembre'])

    lien_connexion = request.build_absolute_uri(reverse('entreprise:recruteur_connexion'))
    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site
    try:
        html = render_to_string('entreprise/emails/membre_credentials.html', {
            'recruteur':      rec,
            'entreprise':     request.entreprise,
            'mot_de_passe':   mdp,
            'lien_connexion': lien_connexion,
            'logo_site':      logo_site,
        })
        send_mail(
            subject=f"Vos identifiants — {request.entreprise.raisonSocial} sur {nom_site}",
            message=(
                f"Bonjour {rec.nomComplet},\n\n"
                f"{request.entreprise.raisonSocial} vous a ajouté comme {rec.get_roleMembre_display()} "
                f"sur {nom_site}.\n\n"
                f"Vos identifiants de connexion :\n"
                f"  Email      : {email}\n"
                f"  Mot de passe : {mdp}\n\n"
                f"Connectez-vous : {lien_connexion}\n\n"
                f"Pour votre sécurité, changez votre mot de passe à la première connexion.\n\n"
                f"L'équipe {nom_site}"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@recrute-pro.ci'),
            recipient_list=[email],
            html_message=html,
            fail_silently=False,
        )
        messages.success(request,
            f'Le membre {rec.nomComplet} a été ajouté. Ses identifiants ont été envoyés à {email}.')
    except Exception:
        messages.warning(request,
            f'Membre ajouté, mais l\'envoi de l\'email a échoué. '
            f'Mot de passe temporaire à transmettre manuellement : {mdp}')

    return redirect('entreprise:membres_liste')


@admin_required
def modifier_membre(request, pk):
    rec = get_object_or_404(Recruteur, pk=pk, entreprise=request.entreprise)
    recruteur_connecte = getattr(request, 'recruteur', None)
    se_modifie_lui_meme = recruteur_connecte is not None and recruteur_connecte.pk == rec.pk

    if request.method != 'POST':
        return render(request, 'entreprise/membres/modifier.html', {
            'membre': rec, 'roles': RoleMembre.choices,
            'se_modifie_lui_meme': se_modifie_lui_meme,
        })

    data   = request.POST
    errors = {}

    nom   = data.get('nomComplet', '').strip()
    email = data.get('emailProfessionnel', '').strip().lower()
    role  = data.get('roleMembre', rec.roleMembre)

    if not nom:
        errors['nomComplet'] = 'Le nom complet est obligatoire.'
    if not email:
        errors['emailProfessionnel'] = "L'email est obligatoire."
    elif Recruteur.objects.filter(emailProfessionnel=email).exclude(pk=pk).exists():
        errors['emailProfessionnel'] = 'Cet email est déjà utilisé.'

    if se_modifie_lui_meme and role != rec.roleMembre:
        errors['roleMembre'] = "Vous ne pouvez pas modifier votre propre rôle."

    if errors:
        return render(request, 'entreprise/membres/modifier.html', {
            'errors': errors, 'data': data, 'membre': rec, 'roles': RoleMembre.choices,
            'se_modifie_lui_meme': se_modifie_lui_meme,
        })

    rec.nomComplet         = nom
    rec.emailProfessionnel = email
    if not se_modifie_lui_meme:
        rec.roleMembre     = role
    rec.telephone          = data.get('telephone', '').strip()
    date_emb = data.get('dateEmbauche', '').strip()
    rec.dateEmbauche = date_emb or None

    new_mdp = data.get('nouveauMotPasse', '').strip()
    if new_mdp:
        if len(new_mdp) < 8:
            messages.error(request, 'Le nouveau mot de passe doit contenir au moins 8 caractères.')
            return redirect('entreprise:modifier_membre', pk=pk)
        rec.set_password(new_mdp)

    rec.droitsAcces = rec.get_droits_par_role()
    rec.save()

    messages.success(request, f'Le profil de {rec.nomComplet} a été mis à jour.')
    return redirect('entreprise:membres_liste')


@admin_required
@require_POST
def supprimer_membre(request, pk):
    rec = get_object_or_404(Recruteur, pk=pk, entreprise=request.entreprise)

    recruteur_connecte = getattr(request, 'recruteur', None)
    if recruteur_connecte is not None and recruteur_connecte.pk == rec.pk:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('entreprise:membres_liste')

    nom = rec.nomComplet
    with transaction.atomic():
        rec.delete()
        request.entreprise.nombreMembre = request.entreprise.recruteurs.filter(estActif=True).count()
        request.entreprise.save(update_fields=['nombreMembre'])

    messages.success(request, f'Le membre {nom} a été supprimé.')
    return redirect('entreprise:membres_liste')


@admin_required
@require_POST
def toggle_membre(request, pk):
    rec = get_object_or_404(Recruteur, pk=pk, entreprise=request.entreprise)

    recruteur_connecte = getattr(request, 'recruteur', None)
    if recruteur_connecte is not None and recruteur_connecte.pk == rec.pk:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect('entreprise:membres_liste')

    with transaction.atomic():
        rec.estActif = not rec.estActif
        rec.save(update_fields=['estActif'])

        request.entreprise.nombreMembre = request.entreprise.recruteurs.filter(estActif=True).count()
        request.entreprise.save(update_fields=['nombreMembre'])

    statut = 'activé' if rec.estActif else 'désactivé'
    messages.success(request, f'Le compte de {rec.nomComplet} a été {statut}.')
    return redirect('entreprise:membres_liste')


@admin_required
@require_POST
def renvoyer_identifiants_membre(request, pk):
    """Génère un nouveau mot de passe et renvoie les identifiants par email."""
    rec = get_object_or_404(Recruteur, pk=pk, entreprise=request.entreprise)

    mdp = _generer_mdp_membre()
    rec.set_password(mdp)
    rec.save(update_fields=['motPasse'])

    lien_connexion = request.build_absolute_uri(reverse('entreprise:recruteur_connexion'))
    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site
    try:
        html = render_to_string('entreprise/emails/membre_credentials.html', {
            'recruteur':      rec,
            'entreprise':     request.entreprise,
            'mot_de_passe':   mdp,
            'lien_connexion': lien_connexion,
            'logo_site':      logo_site,
        })
        send_mail(
            subject=f"Nouveaux identifiants — {request.entreprise.raisonSocial} sur {nom_site}",
            message=(
                f"Bonjour {rec.nomComplet},\n\n"
                f"Vos identifiants ont été réinitialisés.\n\n"
                f"  Email        : {rec.emailProfessionnel}\n"
                f"  Mot de passe : {mdp}\n\n"
                f"Connectez-vous : {lien_connexion}\n\n"
                f"L'équipe {nom_site}"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@recrute-pro.ci'),
            html_message=html,
            recipient_list=[rec.emailProfessionnel],
            fail_silently=False,
        )
        messages.success(request, f'Nouveaux identifiants envoyés à {rec.emailProfessionnel}.')
    except Exception:
        messages.warning(
            request,
            f'Le mot de passe a été réinitialisé mais l\'email n\'a pas pu être envoyé. '
            f'Communiquez le manuellement à {rec.nomComplet}.',
        )
    return redirect('entreprise:membres_liste')
