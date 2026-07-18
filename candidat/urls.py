from django.urls import path
from . import views
from . import cv as cv_views
from . import portfolio as portfolio_views
from . import lettreMo as lettre_views
from . import newsletter as newsletter_views

app_name = 'candidat'

urlpatterns = [
    path('',                                 views.accueil,            name='accueil'),
    path('avis/',                            views.avis,               name='avis'),
    path('offres/',                          views.offres,             name='offres'),
    path('api/matching/toggle/',             views.api_matching_toggle, name='api_matching_toggle'),
    path('offres/<int:offre_id>/',           views.offre_detail,       name='offre_detail'),
    path('offres/<int:offre_id>/postuler/',  views.postuler,           name='postuler'),
    path('mes-candidatures/',                            views.mes_candidatures,     name='mes_candidatures'),
    path('mes-candidatures/historique/',                 views.historique_candidatures, name='historique_candidatures'),
    path('mes-candidatures/<int:candidature_id>/retirer/', views.retirer_candidature, name='retirer_candidature'),
    path('entretien/<int:entretien_id>/calendrier/',       views.entretien_ics,        name='entretien_ics'),
    path('entretien/<int:entretien_id>/contacter/',        views.entretien_contacter,  name='entretien_contacter'),
    path('entreprises/<int:entreprise_id>/', views.entreprise_profil,  name='entreprise_profil'),

    path('inscription/',                                 views.inscription,                    name='inscription'),
    path('inscription/en-attente/',                      views.inscription_en_attente,         name='inscription_en_attente'),
    path('api/inscription/verifier-code/',               views.api_verifier_code_inscription,  name='api_verifier_code_inscription'),
    path('api/inscription/renvoyer-code/',               views.api_renvoyer_code_inscription,  name='api_renvoyer_code_inscription'),
    path('connexion/',    views.connexion,   name='connexion'),
    path('deconnexion/',  views.deconnexion, name='deconnexion'),
    path('dashboard/',    views.dashboard,   name='dashboard'),
    path('profil/',       views.profil,      name='profil'),
    path('api/changer-mot-de-passe/',  views.api_changer_mot_de_passe,    name='api_changer_mot_de_passe'),
    path('api/temoignage/',            views.api_soumettre_temoignage,    name='api_soumettre_temoignage'),
    path('api/profil/identite/',        views.api_sauvegarder_identite,    name='api_sauvegarder_identite'),
    path('api/profil/supprimer-photo/', views.api_supprimer_photo,         name='api_supprimer_photo'),
    path('api/profil/score/',           views.api_profil_score,            name='api_profil_score'),
    path('api/profil/portfolio/',          views.api_sauvegarder_portfolio,       name='api_sauvegarder_portfolio'),
    path('api/profil/portfolio/modele/',   views.api_changer_modele_portfolio,    name='api_changer_modele_portfolio'),
    path('api/profil/rubriques/',      views.api_sauvegarder_rubriques,   name='api_sauvegarder_rubriques'),
    path('api/profil/projet-media/',   views.api_upload_projet_media,     name='api_upload_projet_media'),

    # CV
    path('modeles-cv/',                                       cv_views.modeles_cv,    name='modeles_cv'),
    path('cv/<int:template_id>/apercu/',                      cv_views.apercu_cv,     name='apercu_cv'),
    path('cv/<int:template_id>/creer/',                       cv_views.creer_cv,      name='creer_cv'),
    path('cv/<int:template_id>/apercu-fragment/',             cv_views.apercu_modele_fragment, name='apercu_modele_fragment'),
    path('cv/<int:template_id>/telecharger/<str:fmt>/',       cv_views.telecharger_cv, name='telecharger_cv'),
    path('api/cv/<int:template_id>/sauvegarder/',             cv_views.sauvegarder_cv, name='api_sauvegarder_cv'),
    path('cv/<int:cv_id>/modifier/',                          cv_views.modifier_cv,    name='modifier_cv'),
    path('api/cv/<int:cv_id>/archiver/',                      cv_views.archiver_cv,              name='api_archiver_cv'),
    path('api/cv/<int:cv_id>/regenerer/',                     cv_views.regenerer_cv_artefacts,   name='api_regenerer_cv'),
    path('api/cvs/',                                          cv_views.api_lister_cvs,            name='api_lister_cvs'),
    path('api/cv/<int:cv_id>/images/',                        cv_views.api_images_cv,             name='api_images_cv'),
    path('api/cv/importer/',                                  cv_views.api_importer_cv,           name='api_importer_cv'),
    path('api/cv/<int:cv_id>/extraire/',                      cv_views.api_extraire_cv,           name='api_extraire_cv'),
    path('api/cv/sauvegarder-extraction/',                    cv_views.api_sauvegarder_extraction, name='api_sauvegarder_extraction'),

    # CV — adaptation IA à une offre
    path('offres/<int:offre_id>/adapter-cv/verifier/',        views.verifier_avant_adaptation_cv_ia, name='verifier_avant_adaptation_cv_ia'),
    path('offres/<int:offre_id>/adapter-cv/',                 views.lancer_adaptation_cv_ia,      name='lancer_adaptation_cv_ia'),
    path('offres/<int:offre_id>/adapter-cv/statut/',          views.statut_adaptation_cv_ia,      name='statut_adaptation_cv_ia'),
    path('offres/<int:offre_id>/adapter-cv/ouvrir/',          views.creer_cv_depuis_adaptation,   name='creer_cv_depuis_adaptation'),

    # Lettre de motivation
    path('modeles-lettre/',                                        lettre_views.modeles_lettre,    name='modeles_lettre'),
    path('lettre/<int:template_id>/apercu/',                       lettre_views.apercu_lettre,     name='apercu_lettre'),
    path('lettre/<int:template_id>/creer/',                        lettre_views.creer_lettre,      name='creer_lettre'),
    path('lettre/<int:template_id>/telecharger/<str:fmt>/',        lettre_views.telecharger_lettre,  name='telecharger_lettre'),
    path('api/lettre/<int:template_id>/sauvegarder/',              lettre_views.sauvegarder_lettre,  name='api_sauvegarder_lettre'),
    path('api/lettres/',                                           lettre_views.api_lister_lettres,        name='api_lister_lettres'),
    path('api/lettre/<int:lettre_id>/archiver/',                   lettre_views.archiver_lettre,           name='api_archiver_lettre'),
    path('api/lettre/<int:lettre_id>/regenerer/',                  lettre_views.regenerer_lettre_artefacts, name='api_regenerer_lettre'),
    path('api/lettre/<int:lettre_id>/images/',                     lettre_views.api_images_lettre,         name='api_images_lettre'),
    path('lettre/<int:lettre_id>/modifier/',                       lettre_views.modifier_lettre,           name='modifier_lettre'),

    # Lettre — adaptation IA à une offre (verification reutilise verifier_avant_adaptation_cv_ia)
    path('offres/<int:offre_id>/adapter-lettre/',              views.lancer_adaptation_lettre_ia,   name='lancer_adaptation_lettre_ia'),
    path('offres/<int:offre_id>/adapter-lettre/statut/',       views.statut_adaptation_lettre_ia,   name='statut_adaptation_lettre_ia'),
    path('offres/<int:offre_id>/adapter-lettre/ouvrir/',       views.creer_lettre_depuis_adaptation, name='creer_lettre_depuis_adaptation'),

    # Portfolio
    path('mon-portfolio/',                                         views.mon_portfolio,                          name='mon_portfolio'),
    path('portfolio/',                                              portfolio_views.portfolio,                    name='portfolio'),
    path('portfolio/p/<int:candidat_id>/',                          portfolio_views.portfolio_public,             name='portfolio_public'),
    path('portfolio/p/<int:candidat_id>/contact/',                  portfolio_views.api_portfolio_contact,        name='api_portfolio_contact'),
    path('portfolio/p/<int:candidat_id>/projet/<int:projet_id>/',   portfolio_views.portfolio_projet_detail,      name='portfolio_projet_detail'),
    path('portfolio/partage/<uuid:token>/',                         portfolio_views.portfolio_partage,            name='portfolio_partage'),
    path('api/portfolio/regenerer-token/',                          portfolio_views.api_regenerer_token_portfolio, name='api_regenerer_token_portfolio'),

    # Réinitialisation du mot de passe
    path('mot-de-passe-oublie/',            views.mot_de_passe_oublie,         name='mot_de_passe_oublie'),
    path('reinitialisation/<uuid:token>/',  views.reinitialiser_mot_de_passe,  name='reinitialiser_mot_de_passe'),

    # API réinitialisation (appelées en AJAX depuis Alpine.js)
    path('api/verifier-email/',             views.api_verifier_email,           name='api_verifier_email'),
    path('api/envoyer-reinitialisation/',   views.api_envoyer_reinitialisation, name='api_envoyer_reinitialisation'),
    path('api/verifier-code/',              views.api_verifier_code,            name='api_verifier_code'),

    # Offres favorites
    path('favoris/',                              views.mes_favoris,        name='mes_favoris'),
    path('api/favoris/<int:offre_id>/toggle/',   views.api_toggle_favori,  name='api_toggle_favori'),

    # Invitations et messagerie directe
    path('invitations/',                                   views.invitations,                  name='invitations'),
    path('invitations/<int:inv_id>/<str:action>/',         views.invitation_repondre,          name='invitation_repondre'),
    path('messages/non-lus/',                              views.api_messages_non_lus_candidat, name='api_messages_non_lus'),
    path('messages/',                                      views.conversations_liste,           name='conversations'),
    path('messages/<int:conv_id>/',                        views.conversation_detail,           name='conversation_detail'),
    path('messages/<int:conv_id>/envoyer/',                views.api_envoyer_message_candidat, name='api_envoyer_message'),
    path('messages/<int:conv_id>/action/',                 views.cand_api_conv_action,          name='cand_api_conv_action'),
    path('messages/msg/<int:msg_id>/action/',             views.cand_api_msg_action,            name='cand_api_msg_action'),

    # Notifications candidat
    path('notifications/',                                  views.notifications_page,           name='notifications'),
    path('api/notifications/',                              views.api_notifications_lister,     name='api_notifications_lister'),
    path('api/notifications/<int:pk>/lire/',                views.api_notifications_lire,       name='api_notifications_lire'),
    path('api/notifications/toutes-lues/',                  views.api_notifications_toutes_lues, name='api_notifications_toutes_lues'),
    path('api/notifications/<int:pk>/supprimer/',           views.api_notifications_supprimer,  name='api_notifications_supprimer'),
    path('api/notifications/tout-supprimer/',               views.api_notifications_supprimer_toutes, name='api_notifications_supprimer_toutes'),
    path('api/notifications/preferences/email/',            views.api_notifications_pref_email,       name='api_notifications_pref_email'),
    path('api/notifications/preferences/inapp/',            views.api_notifications_pref_inapp,       name='api_notifications_pref_inapp'),
    path('api/notifications/preferences/recommandations/', views.api_recommandations_toggle,          name='api_recommandations_toggle'),
    path('api/notifications/preferences/alertes/',         views.api_alertes_master_toggle,            name='api_alertes_master_toggle'),
    path('api/alertes/',                                   views.api_alertes_liste,                   name='api_alertes_liste'),
    path('api/alertes/creer/',                             views.api_alerte_creer,                    name='api_alerte_creer'),
    path('api/alertes/<int:alerte_id>/supprimer/',         views.api_alerte_supprimer,                name='api_alerte_supprimer'),
    path('api/alertes/<int:alerte_id>/toggle/',            views.api_alerte_toggle,                   name='api_alerte_toggle'),

    # Newsletter
    path('api/newsletter/inscription/',                          newsletter_views.api_newsletter_inscription, name='api_newsletter_inscription'),
    path('api/newsletter/toggle/',                               newsletter_views.api_newsletter_toggle,      name='api_newsletter_toggle'),
    path('api/newsletter/statut/',                               newsletter_views.api_newsletter_statut,      name='api_newsletter_statut'),
    path('api/newsletter/preferences/',                          newsletter_views.api_newsletter_preferences, name='api_newsletter_preferences'),
    path('newsletter/desabonnement/<uuid:token>/',               newsletter_views.newsletter_desabonnement,   name='newsletter_desabonnement'),
    path('newsletter/gerer/',                                    newsletter_views.gerer_newsletter,           name='newsletter_gerer'),

    # OAuth — géré par django-allauth (voir /accounts/)
]
