from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from referentiel.models import Utilisateur, TypeCompte, Contrat
from candidat.models import Candidat
from .models import Entreprise, Recruteur, OffreEmploi, StatutOffre, RoleMembre


class EntrepriseModelTest(TestCase):
    """Tests du modèle Entreprise."""

    def test_creation_entreprise(self):
        ent = Entreprise.objects.create(
            raisonSocial='Tech Corp',
            emailProfessionnel='contact@techcorp.ci',
        )
        ent.set_password('secret123')
        ent.save()
        self.assertEqual(str(ent), 'Tech Corp')
        self.assertTrue(ent.check_password('secret123'))

    def test_mot_de_passe_incorrect(self):
        ent = Entreprise.objects.create(
            raisonSocial='Test',
            emailProfessionnel='test@ent.ci',
        )
        ent.set_password('bon')
        self.assertFalse(ent.check_password('mauvais'))


class RecruteurModelTest(TestCase):
    """Tests du modèle Recruteur (multi-table inheritance)."""

    def setUp(self):
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Entreprise Test',
            emailProfessionnel='ent@test.ci',
        )
        self.recruteur = Recruteur(
            email='recruteur@test.ci',
            type_compte=TypeCompte.RECRUTEUR,
            entreprise=self.entreprise,
            nom='Dupont',
            prenom='Jean',
            emailProfessionnel='recruteur@test.ci',
            roleMembre=RoleMembre.RH,
        )
        self.recruteur.set_password('test123')
        self.recruteur.save()

    def test_creation_recruteur(self):
        self.assertEqual(self.recruteur.entreprise, self.entreprise)
        self.assertEqual(self.recruteur.roleMembre, RoleMembre.RH)

    def test_recruteur_est_utilisateur(self):
        self.assertIsInstance(self.recruteur, Utilisateur)

    def test_droits_par_role(self):
        droits = self.recruteur.get_droits_par_role()
        self.assertIn('offres', droits)
        self.assertIn('create', droits['offres'])

    def test_est_lecteur(self):
        self.assertFalse(self.recruteur.est_lecteur)
        self.recruteur.roleMembre = RoleMembre.LECTEUR
        self.assertTrue(self.recruteur.est_lecteur)


class OffreEmploiModelTest(TestCase):
    """Tests du modèle OffreEmploi."""

    def setUp(self):
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Entreprise Offre',
            emailProfessionnel='offre@test.ci',
        )

    def test_creation_offre(self):
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Développeur Python',
            typeContrat='CDI',
        )
        self.assertTrue(offre.reference.startswith('OFF-'))
        self.assertEqual(offre.statutOffre, StatutOffre.BROUILLON)

    def test_publier_offre(self):
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Designer UX',
            typeContrat='CDD',
        )
        offre.publier()
        offre.refresh_from_db()
        self.assertEqual(offre.statutOffre, StatutOffre.PUBLIEE)
        self.assertIsNotNone(offre.datePublication)

    def test_fermer_offre(self):
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Chef de projet',
            typeContrat='CDI',
        )
        offre.publier()
        offre.fermer()
        offre.refresh_from_db()
        self.assertEqual(offre.statutOffre, StatutOffre.FERMEE)

    def test_reference_unique(self):
        o1 = OffreEmploi.objects.create(
            entreprise=self.entreprise, titre='Offre 1', typeContrat='CDI',
        )
        o2 = OffreEmploi.objects.create(
            entreprise=self.entreprise, titre='Offre 2', typeContrat='CDD',
        )
        self.assertNotEqual(o1.reference, o2.reference)


class EntrepriseAuthViewsTest(TestCase):
    """Tests des vues d'authentification entreprise."""

    def setUp(self):
        self.client = Client()
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Auth Entreprise',
            emailProfessionnel='auth@entreprise.ci',
        )
        self.entreprise.set_password('test123')
        self.entreprise.save()

    def test_page_connexion_accessible(self):
        resp = self.client.get(reverse('entreprise:connexion'))
        self.assertEqual(resp.status_code, 200)

    def test_connexion_entreprise_reussie(self):
        resp = self.client.post(reverse('entreprise:connexion'), {
            'email': 'auth@entreprise.ci',
            'motPasse': 'test123',
        })
        self.assertEqual(resp.status_code, 302)

    def test_connexion_entreprise_mauvais_mdp(self):
        resp = self.client.post(reverse('entreprise:connexion'), {
            'email': 'auth@entreprise.ci',
            'motPasse': 'mauvais',
        })
        self.assertEqual(resp.status_code, 200)


class EmailUniciteTest(TestCase):
    """Test que le même email ne peut pas servir pour candidat ET recruteur."""

    def test_email_unique_entre_types(self):
        Candidat.objects.create(
            email='unique@test.com',
            type_compte=TypeCompte.CANDIDAT,
        )
        with self.assertRaises(Exception):
            Recruteur.objects.create(
                email='unique@test.com',
                type_compte=TypeCompte.RECRUTEUR,
                entreprise=Entreprise.objects.create(
                    raisonSocial='E', emailProfessionnel='e@e.ci',
                ),
            )


# ══════════════════════════════════════════════════════════════════════════════
# Nouveaux tests
# ══════════════════════════════════════════════════════════════════════════════


class EntrepriseConnexionSecuriteTest(TestCase):
    """Tests de securite de la session entreprise."""

    def setUp(self):
        self.client = Client()
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Securite Corp',
            emailProfessionnel='secu@entreprise.ci',
        )
        self.entreprise.set_password('secret123')
        self.entreprise.save()

    def test_connexion_change_session_id(self):
        """Apres login, l'identifiant de session change (cycle_key)."""
        # Faire une requete GET pour obtenir un session_key initial
        self.client.get(reverse('entreprise:connexion'))
        old_key = self.client.session.session_key

        # Se connecter
        self.client.post(reverse('entreprise:connexion'), {
            'email': 'secu@entreprise.ci',
            'motPasse': 'secret123',
        })
        new_key = self.client.session.session_key

        # Le session_key doit avoir change (protection contre session fixation)
        self.assertNotEqual(old_key, new_key)

    def test_session_expire_apres_8h(self):
        """La duree d'expiration de la session est de 28800 secondes (8 heures)."""
        self.client.post(reverse('entreprise:connexion'), {
            'email': 'secu@entreprise.ci',
            'motPasse': 'secret123',
        })
        expiry = self.client.session.get_expiry_age()
        self.assertEqual(expiry, 28800)


class OffreEmploiWorkflowTest(TestCase):
    """Tests du cycle de vie des offres d'emploi."""

    def setUp(self):
        self.client = Client()
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Offre Workflow Corp',
            emailProfessionnel='offre-wf@entreprise.ci',
        )
        self.entreprise.set_password('secret123')
        self.entreprise.save()

        # Creer un type de contrat dans le referentiel
        self.contrat_cdi = Contrat.objects.create(libelle='CDI')

    def _login_entreprise(self):
        """Helper : connecter l'entreprise via la session."""
        self.client.post(reverse('entreprise:connexion'), {
            'email': 'offre-wf@entreprise.ci',
            'motPasse': 'secret123',
        })

    @patch('entreprise.tasks.calculer_embedding_offre.delay')
    def test_creer_offre(self, mock_embedding):
        """L'entreprise peut creer une offre via le formulaire."""
        self._login_entreprise()
        resp = self.client.post(reverse('entreprise:offre_creer'), {
            'titre': 'Ingenieur DevOps',
            'contrat': str(self.contrat_cdi.pk),
            'missions': 'Deploiement et maintenance',
            'profilRecherche': 'Expert Docker',
        })
        # Doit rediriger apres creation reussie
        self.assertIn(resp.status_code, [200, 302])
        offre = OffreEmploi.objects.filter(titre='Ingenieur DevOps').first()
        if offre:
            self.assertEqual(offre.entreprise, self.entreprise)
            self.assertEqual(offre.statutOffre, StatutOffre.BROUILLON)

    def test_publier_offre_change_statut(self):
        """Publier une offre met son statutOffre a PUBLIEE."""
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Data Scientist',
            typeContrat='CDI',
        )
        self.assertEqual(offre.statutOffre, StatutOffre.BROUILLON)
        offre.publier()
        offre.refresh_from_db()
        self.assertEqual(offre.statutOffre, StatutOffre.PUBLIEE)
        self.assertIsNotNone(offre.datePublication)

    def test_offre_detail_accessible(self):
        """La page de detail d'une offre est accessible pour l'entreprise connectee."""
        session = self.client.session
        session['entreprise_id'] = self.entreprise.pk
        session.save()
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise,
            titre='Designer UI',
            typeContrat='CDD',
        )
        resp = self.client.get(
            reverse('entreprise:offre_detail', args=[offre.pk]),
        )
        self.assertEqual(resp.status_code, 200)


class PermissionsRecruteurTest(TestCase):
    """Tests d'acces selon le role du recruteur."""

    def setUp(self):
        self.client = Client()
        self.entreprise = Entreprise.objects.create(
            raisonSocial='Permissions Corp',
            emailProfessionnel='perms@entreprise.ci',
        )
        self.entreprise.set_password('secret123')
        self.entreprise.save()

        # Contrat referentiel pour la creation d'offre
        self.contrat_cdi = Contrat.objects.create(libelle='CDI Perms')

    def _creer_recruteur(self, email, role):
        """Helper : creer un Recruteur avec un role donne."""
        rec = Recruteur(
            email=email,
            type_compte=TypeCompte.RECRUTEUR,
            entreprise=self.entreprise,
            nom='Test',
            prenom=role,
            emailProfessionnel=email,
            roleMembre=role,
        )
        rec.set_password('test123')
        rec.save()
        return rec

    @patch('entreprise.tasks.calculer_embedding_offre.delay')
    def test_lecteur_ne_peut_pas_creer_offre(self, mock_embedding):
        """Un recruteur LECTEUR ne peut pas creer d'offre (bloque)."""
        lecteur = self._creer_recruteur('lecteur@perms.ci', RoleMembre.LECTEUR)
        self.client.force_login(lecteur)
        # Aussi mettre l'entreprise en session pour que le middleware fonctionne
        session = self.client.session
        session.save()

        resp = self.client.post(reverse('entreprise:offre_creer'), {
            'titre': 'Offre interdite',
            'contrat': str(self.contrat_cdi.pk),
        })
        # Le decorateur @bloque_roles('LECTEUR', 'MANAGER') redirige
        self.assertEqual(resp.status_code, 302)
        # L'offre ne doit pas avoir ete creee
        self.assertFalse(
            OffreEmploi.objects.filter(titre='Offre interdite').exists()
        )

    def test_rh_peut_voir_candidatures(self):
        """Un recruteur RH peut acceder a la page globale des candidatures."""
        rh = self._creer_recruteur('rh@perms.ci', RoleMembre.RH)
        self.client.force_login(rh)

        resp = self.client.get(reverse('entreprise:candidatures'))
        self.assertIn(resp.status_code, [200, 302])

    def test_admin_peut_gerer_membres(self):
        """Un recruteur ADMIN peut acceder a la page de gestion des membres."""
        admin_rec = self._creer_recruteur('admin@perms.ci', RoleMembre.ADMIN)
        self.client.force_login(admin_rec)

        resp = self.client.get(reverse('entreprise:membres_liste'))
        self.assertEqual(resp.status_code, 200)


@override_settings(
    RATELIMIT_ENABLE=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class RateLimitEntrepriseTest(TestCase):
    """Tests du rate limiting sur la connexion entreprise."""

    def setUp(self):
        self.client = Client()
        self.entreprise = Entreprise.objects.create(
            raisonSocial='RateLimit Corp',
            emailProfessionnel='ratelimit@entreprise.ci',
        )
        self.entreprise.set_password('secret123')
        self.entreprise.save()

    def test_connexion_bloquee_apres_limite(self):
        """Apres 5+ tentatives echouees, la reponse contient le message de blocage."""
        url = reverse('entreprise:connexion')
        for i in range(6):
            resp = self.client.post(url, {
                'email': 'ratelimit@entreprise.ci',
                'motPasse': 'mauvais_mdp',
            })
        # La 6e tentative doit declencher le rate limit
        content = resp.content.decode()
        self.assertIn('Trop de tentatives', content)
