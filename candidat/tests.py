from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from referentiel.models import Utilisateur, TypeCompte, Statut
from entreprise.models import Entreprise, OffreEmploi, StatutOffre
from .models import Candidat, Candidature


class UtilisateurModelTest(TestCase):
    """Tests du modèle Utilisateur (AUTH_USER_MODEL)."""

    def test_creation_utilisateur(self):
        user = Utilisateur.objects.create_user(
            email='test@example.com',
            type_compte=TypeCompte.CANDIDAT,
            password='motdepasse123',
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.type_compte, TypeCompte.CANDIDAT)
        self.assertTrue(user.check_password('motdepasse123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_creation_superuser(self):
        admin = Utilisateur.objects.create_superuser(
            email='admin@example.com',
            password='admin123',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_email_unique(self):
        Utilisateur.objects.create_user(email='unique@example.com', password='test')
        with self.assertRaises(Exception):
            Utilisateur.objects.create_user(email='unique@example.com', password='test2')

    def test_email_obligatoire(self):
        with self.assertRaises(ValueError):
            Utilisateur.objects.create_user(email='', password='test')


class CandidatModelTest(TestCase):
    """Tests du modèle Candidat (multi-table inheritance)."""

    def setUp(self):
        self.candidat = Candidat(
            email='candidat@example.com',
            type_compte=TypeCompte.CANDIDAT,
            nom='KONE',
            prenom='Aboudramane',
            emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()

    def test_creation_candidat(self):
        self.assertEqual(self.candidat.nom, 'KONE')
        self.assertEqual(self.candidat.prenom, 'Aboudramane')
        self.assertEqual(self.candidat.email, 'candidat@example.com')

    def test_candidat_est_utilisateur(self):
        self.assertIsInstance(self.candidat, Utilisateur)
        self.assertEqual(self.candidat.type_compte, TypeCompte.CANDIDAT)

    def test_str(self):
        self.assertIn('KONE', str(self.candidat))

    def test_mot_de_passe(self):
        self.assertTrue(self.candidat.check_password('test123'))
        self.assertFalse(self.candidat.check_password('mauvais'))

    def test_changer_mot_de_passe(self):
        self.candidat.set_password('ancien')
        self.candidat.save()
        result = self.candidat.changerMotDePasse('ancien', 'nouveau')
        self.assertTrue(result)
        self.assertTrue(self.candidat.check_password('nouveau'))

    def test_changer_mot_de_passe_echec(self):
        self.candidat.set_password('ancien')
        self.candidat.save()
        result = self.candidat.changerMotDePasse('mauvais', 'nouveau')
        self.assertFalse(result)


class CandidatAuthViewsTest(TestCase):
    """Tests des vues d'authentification candidat."""

    def setUp(self):
        self.client = Client()
        self.candidat = Candidat(
            email='auth@example.com',
            type_compte=TypeCompte.CANDIDAT,
            nom='Test',
            prenom='Auth',
            emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()

    def test_page_connexion_accessible(self):
        resp = self.client.get(reverse('candidat:connexion'))
        self.assertEqual(resp.status_code, 200)

    def test_connexion_reussie(self):
        resp = self.client.post(reverse('candidat:connexion'), {
            'email': 'auth@example.com',
            'motdepasse': 'test123',
        })
        self.assertEqual(resp.status_code, 302)

    def test_connexion_mauvais_mdp(self):
        resp = self.client.post(reverse('candidat:connexion'), {
            'email': 'auth@example.com',
            'motdepasse': 'mauvais',
        })
        self.assertEqual(resp.status_code, 200)

    def test_deconnexion(self):
        self.client.force_login(self.candidat)
        resp = self.client.post(reverse('candidat:deconnexion'))
        self.assertEqual(resp.status_code, 302)

    def test_acces_protege_sans_connexion(self):
        resp = self.client.get(reverse('candidat:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('connexion', resp.url)

    def test_acces_protege_avec_connexion(self):
        self.client.force_login(self.candidat)
        resp = self.client.get(reverse('candidat:dashboard'))
        self.assertEqual(resp.status_code, 200)


class CandidatPagePubliqueTest(TestCase):
    """Tests des pages publiques."""

    def test_accueil(self):
        resp = self.client.get(reverse('candidat:accueil'))
        self.assertEqual(resp.status_code, 200)

    def test_page_inscription(self):
        resp = self.client.get(reverse('candidat:inscription'))
        self.assertEqual(resp.status_code, 200)


# ══════════════════════════════════════════════════════════════════════════════
# Nouveaux tests
# ══════════════════════════════════════════════════════════════════════════════


class CandidatureWorkflowTest(TestCase):
    """Tests du cycle de vie complet d'une candidature."""

    def setUp(self):
        self.client = Client()

        # Creer les statuts referentiel
        self.statut_postulee = Statut.objects.create(
            code='POSTULEE', libelle='Postulée', ordre=1,
        )
        self.statut_retiree = Statut.objects.create(
            code='RETIREE', libelle='Retirée', ordre=10, estFinal=True,
        )

        # Creer le candidat
        self.candidat = Candidat(
            email='workflow@example.com',
            type_compte=TypeCompte.CANDIDAT,
            nom='Dupont',
            prenom='Marie',
            emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()

        # Creer l'entreprise et une offre publiee
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Entreprise Workflow',
            emailProfessionnel='workflow@entreprise.ci',
        )
        self.entreprise.set_password('test')
        self.entreprise.save()

        self.offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Developpeur Django',
            typeContrat='CDI',
            statutOffre=StatutOffre.PUBLIEE,
        )

    def test_postuler_cree_candidature(self):
        """POST vers postuler cree une Candidature avec statut POSTULEE."""
        self.client.force_login(self.candidat)
        resp = self.client.post(
            reverse('candidat:postuler', args=[self.offre.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Candidature.objects.filter(
                candidat=self.candidat,
                offre=self.offre,
                statut=self.statut_postulee,
            ).exists()
        )

    def test_postuler_deux_fois_refuse(self):
        """Deuxieme POST vers la meme offre est rejete (deja candidaté)."""
        self.client.force_login(self.candidat)
        # Premiere candidature
        self.client.post(
            reverse('candidat:postuler', args=[self.offre.pk]),
        )
        self.assertEqual(
            Candidature.objects.filter(
                candidat=self.candidat, offre=self.offre,
            ).count(),
            1,
        )
        # Deuxieme tentative
        resp = self.client.post(
            reverse('candidat:postuler', args=[self.offre.pk]),
        )
        # Doit rediriger (warning) et ne pas creer de doublon
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            Candidature.objects.filter(
                candidat=self.candidat, offre=self.offre,
            ).count(),
            1,
        )

    def test_retirer_candidature(self):
        """POST vers retirer change le statut a RETIREE."""
        self.client.force_login(self.candidat)
        # Creer la candidature
        self.client.post(
            reverse('candidat:postuler', args=[self.offre.pk]),
        )
        candidature = Candidature.objects.get(
            candidat=self.candidat, offre=self.offre,
        )
        self.assertEqual(candidature.statut, self.statut_postulee)

        # Retirer
        resp = self.client.post(
            reverse('candidat:retirer_candidature', args=[candidature.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        candidature.refresh_from_db()
        self.assertEqual(candidature.statut, self.statut_retiree)

    def test_postuler_sans_connexion_redirige(self):
        """Un visiteur non connecte est redirige vers la page de connexion."""
        resp = self.client.post(
            reverse('candidat:postuler', args=[self.offre.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('connexion', resp.url)


class CandidatProfilTest(TestCase):
    """Tests d'acces au profil et au dashboard."""

    def setUp(self):
        self.client = Client()
        self.candidat = Candidat(
            email='profil@example.com',
            type_compte=TypeCompte.CANDIDAT,
            nom='Test',
            prenom='Profil',
            emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()

    def test_dashboard_accessible_connecte(self):
        """Un candidat connecte peut acceder au dashboard."""
        self.client.force_login(self.candidat)
        resp = self.client.get(reverse('candidat:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_redirige_sans_connexion(self):
        """Un visiteur non connecte est redirige vers la connexion."""
        resp = self.client.get(reverse('candidat:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('connexion', resp.url)

    def test_profil_accessible_connecte(self):
        """Un candidat connecte peut acceder a sa page profil."""
        self.client.force_login(self.candidat)
        resp = self.client.get(reverse('candidat:profil'))
        self.assertEqual(resp.status_code, 200)
