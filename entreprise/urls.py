from django.urls import path
from . import views

app_name = 'entreprise'

urlpatterns = [
    # ── Accueil ────────────────────────────────────────────────────────────────
    path('',                    views.accueil,              name='accueil'),
    path('avis/',                views.avis,                name='avis'),

    # ── Découverte de profils candidats (portfolios publics) ──────────────────
    path('candidats/',                       views.candidats_liste,         name='candidats'),
    path('candidats/<int:candidat_id>/portfolio/', views.voir_portfolio_candidat, name='voir_portfolio'),

    # ── Auth entreprise ────────────────────────────────────────────────────────
    path('inscription/',        views.inscription,          name='inscription'),
    path('connexion/',          views.connexion,            name='connexion'),
    path('deconnexion/',        views.deconnexion,          name='deconnexion'),

    # ── Espace entreprise ──────────────────────────────────────────────────────
    path('tableau-bord/',               views.tableau_bord,         name='tableau_bord'),
    path('profil/',                     views.profil,               name='profil'),
    path('profil/preferences/',         views.entreprise_preferences, name='entreprise_preferences'),
    path('profil/modifier/',            views.modifier_profil,      name='modifier_profil'),
    path('profil/changer-mdp/',         views.changer_mot_de_passe, name='changer_mdp'),

    # ── Gestion des membres ────────────────────────────────────────────────────
    path('membres/',                        views.membres_liste,    name='membres_liste'),
    path('membres/ajouter/',                views.ajouter_membre,   name='ajouter_membre'),
    path('membres/<int:pk>/modifier/',      views.modifier_membre,  name='modifier_membre'),
    path('membres/<int:pk>/supprimer/',     views.supprimer_membre, name='supprimer_membre'),
    path('membres/<int:pk>/toggle/',              views.toggle_membre,              name='toggle_membre'),
    path('membres/<int:pk>/renvoyer-identifiants/', views.renvoyer_identifiants_membre, name='renvoyer_identifiants_membre'),

    # ── Offres d'emploi ───────────────────────────────────────────────────────
    path('offres/',                         views.offres_liste,         name='offres_liste'),
    path('offres/historique/',              views.offres_historique,    name='offres_historique'),
    path('offres/creer/',                   views.offre_creer,          name='offre_creer'),
    path('offres/<int:pk>/',                views.offre_detail,         name='offre_detail'),
    path('offres/<int:pk>/modifier/',       views.offre_modifier,       name='offre_modifier'),
    path('offres/<int:pk>/statut/',         views.offre_changer_statut, name='offre_changer_statut'),
    path('offres/<int:pk>/supprimer/',      views.offre_supprimer,      name='offre_supprimer'),

    # ── Candidatures (gestion côté recruteur) ─────────────────────────────────
    path('candidatures/',                                views.candidatures_par_offre,  name='candidatures'),
    path('candidatures/offre/<int:offre_id>/',           views.candidatures_offre,      name='candidatures_offre'),
    path('candidatures/offre/<int:offre_id>/message/',   views.message_groupe_envoyer, name='message_groupe_envoyer'),
    path('candidatures/<int:candidature_id>/decision/',  views.candidature_decision,    name='candidature_decision'),
    path('candidatures/<int:candidature_id>/annuler-decision/', views.candidature_annuler_decision, name='candidature_annuler_decision'),
    path('candidatures/<int:candidature_id>/analyser-ia/', views.candidature_analyser_ia, name='candidature_analyser_ia'),
    path('candidatures/offre/<int:offre_id>/scoring-ia/',  views.candidatures_offre_scoring_ia, name='candidatures_offre_scoring_ia'),

    # ── ATS : Profils recommandés (sourcing proactif) ─────────────────────────
    path('offres/<int:offre_id>/suggestions/',         views.suggestions_offre, name='suggestions_offre'),
    path('offres/<int:offre_id>/profils-recommandes/', views.profils_recommandes_offre, name='profils_recommandes_offre'),
    path('offres/<int:offre_id>/profils-recommandes/<int:candidat_id>/<str:action>/',
         views.proposition_marquer_par_couple, name='proposition_marquer_par_couple'),
    path('propositions/<int:proposition_id>/<str:action>/', views.proposition_profil_marquer, name='proposition_profil_marquer'),

    # ── Notifications recruteur (cloche + page historique) ────────────────────
    path('suggestions/',                              views.suggestions_recues,              name='suggestions_recues'),
    path('tableau-bord/stats/',                       views.api_stats_tableau_bord,           name='api_stats_tableau_bord'),
    path('notifications/',                            views.notifications_liste,             name='notifications_liste'),
    path('notifications/historique/',                 views.notifications_page,              name='notifications_page'),
    path('notifications/<int:notification_id>/lire/', views.notification_marquer_lue,        name='notification_marquer_lue'),
    path('notifications/<int:notification_id>/supprimer/', views.notification_supprimer,     name='notification_supprimer'),
    path('notifications/tout-lire/',                  views.notifications_tout_marquer_lues, name='notifications_tout_marquer_lues'),
    path('notifications/tout-supprimer/',             views.notifications_tout_supprimer,    name='notifications_tout_supprimer'),
    path('candidatures/offre/<int:offre_id>/reinitialiser/', views.candidatures_offre_reinitialiser, name='candidatures_offre_reinitialiser'),
    path('candidatures/offre/<int:offre_id>/accepter-bulk/', views.candidatures_accepter_bulk,   name='candidatures_accepter_bulk'),

    # ── Entretiens (post-acceptation) ─────────────────────────────────────────
    path('entretiens/',                          views.entretiens_liste,     name='entretiens'),
    path('entretiens/tous/',                     views.entretiens_tous,      name='entretiens_tous'),
    path('entretiens/offre/<int:offre_id>/',     views.entretiens_offre,     name='entretiens_offre'),
    path('entretiens/offre/<int:offre_id>/programmes/', views.entretiens_offre_programmes, name='entretiens_offre_programmes'),
    path('entretiens/offre/<int:offre_id>/planifier-bulk/', views.entretiens_planifier_bulk, name='entretiens_planifier_bulk'),
    path('entretiens/<int:candidature_id>/planifier/', views.entretien_planifier, name='entretien_planifier'),
    path('entretiens/<int:entretien_id>/reporter/',        views.entretien_reporter,        name='entretien_reporter'),
    path('entretiens/<int:entretien_id>/annuler/',         views.entretien_annuler,         name='entretien_annuler'),
    path('entretiens/<int:entretien_id>/marquer-realise/', views.entretien_marquer_realise, name='entretien_marquer_realise'),

    # ── Modèles de message (admin entreprise) ─────────────────────────────────
    path('modeles-messages/',                            views.modeles_messages_liste,    name='modeles_messages'),
    path('modeles-messages/creer/',                      views.modele_message_creer,      name='modele_message_creer'),
    path('modeles-messages/<int:pk>/',                   views.modele_message_detail,     name='modele_message_detail'),
    path('modeles-messages/<int:pk>/modifier/',          views.modele_message_modifier,   name='modele_message_modifier'),
    path('modeles-messages/<int:pk>/supprimer/',         views.modele_message_supprimer,  name='modele_message_supprimer'),

    # ── Vérification ──────────────────────────────────────────────────────────
    path('verification/email/envoyer/',
         views.envoyer_verification_email,  name='envoyer_verification_email'),
    path('verification/email/verifier-code/',
         views.verifier_code_email,         name='verifier_code_email'),
    path('verification/demande/',
         views.soumettre_demande_verification, name='soumettre_demande_verification'),
    path('admin/kyc/<int:demande_pk>/<str:doc_type>/',
         views.admin_kyc_document,             name='admin_kyc_document'),

    # ── Réinitialisation MDP entreprise ───────────────────────────────────────
    path('mot-de-passe-oublie/',
         views.mot_de_passe_oublie,                    name='mot_de_passe_oublie'),
    path('reinitialisation/<uuid:token>/',
         views.reinitialiser_mot_de_passe,             name='reinitialiser_mot_de_passe'),
    path('api/temoignage/',
         views.api_soumettre_temoignage_entreprise,    name='api_temoignage'),
    path('api/verifier-email/',
         views.api_verifier_email_entreprise,          name='api_verifier_email'),
    path('api/envoyer-reinitialisation/',
         views.api_envoyer_reinitialisation_entreprise, name='api_envoyer_reinitialisation'),
    path('api/verifier-code/',
         views.api_verifier_code_entreprise,           name='api_verifier_code'),

    # ── Contact candidat (invitation + messagerie) ───────────────────────────────
    path('candidats/<int:candidat_id>/suggerer/',           views.api_suggerer_profil,           name='api_suggerer_profil'),
    path('candidats/<int:candidat_id>/inviter/',           views.api_inviter_candidat,          name='api_inviter_candidat'),
    path('candidats/<int:candidat_id>/retenir/',            views.api_retenir_entretien,          name='api_retenir_entretien'),
    path('candidats/<int:candidat_id>/message/',           views.api_demarrer_conversation,      name='api_demarrer_conversation'),
    path('recruteur/messages/non-lus/',                    views.recruteur_messages_non_lus,     name='recruteur_messages_non_lus'),
    path('recruteur/conversations/',                       views.recruteur_conversations,        name='recruteur_conversations'),
    path('recruteur/conversations/<int:conv_id>/',         views.recruteur_conversation_detail,  name='recruteur_conversation_detail'),
    path('recruteur/conversations/<int:conv_id>/envoyer/', views.recruteur_api_envoyer_message,  name='recruteur_api_envoyer_message'),
    path('recruteur/conversations/<int:conv_id>/action/', views.recruteur_api_conv_action,       name='recruteur_api_conv_action'),
    path('recruteur/messages/<int:msg_id>/action/',      views.recruteur_api_msg_action,        name='recruteur_api_msg_action'),

    # ── Partage de profil candidat vers entreprise externe ───────────────────
    path('partager/candidat/<int:candidat_id>/',
         views.partage_creer,                          name='partage_creer'),
    path('partager/mes-liens/',
         views.partages_liste,                         name='partages_liste'),
    path('partager/<uuid:token>/desactiver/',
         views.partage_desactiver,                     name='partage_desactiver'),
    # URL publique — accessible sans authentification
    path('profil-partage/<uuid:token>/',
         views.profil_partage_public,                  name='profil_partage_public'),

    # ── Espace recruteur ───────────────────────────────────────────────────────
    path('recruteur/connexion/',            views.recruteur_connexion,       name='recruteur_connexion'),
    path('recruteur/deconnexion/',          views.recruteur_deconnexion,     name='recruteur_deconnexion'),
    path('recruteur/tableau-bord/',         views.recruteur_tableau_bord,    name='recruteur_tableau_bord'),
    path('recruteur/profil/',               views.recruteur_profil,          name='recruteur_profil'),
    path('recruteur/profil/modifier/',      views.recruteur_modifier_profil, name='recruteur_modifier_profil'),
    path('recruteur/profil/changer-mdp/',   views.recruteur_changer_mdp,     name='recruteur_changer_mdp'),
    path('recruteur/profil/preferences/',   views.recruteur_preferences,     name='recruteur_preferences'),
]
