import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from referentiel.models import Utilisateur, TypeCompte, Statut
from entreprise.models import Entreprise, OffreEmploi, StatutOffre
from .models import Candidat, Candidature, CV, CVContenu, Competence, ModeleCV


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


class CvAdaptationGuardrailTest(TestCase):
    """Garde-fous de validation de la reponse LLM (candidat.cv_adaptation) — aucun appel reseau."""

    def test_reponse_incomplete_leve_erreur(self):
        from candidat.ai_provider import LLMUnavailableError
        from candidat.cv_adaptation import _valider_et_appliquer
        with self.assertRaises(LLMUnavailableError):
            _valider_et_appliquer({'titre': 'Developpeuse'}, {'titre': 'x', 'profil': 'y'})

    def test_troncature_longueurs(self):
        from candidat.cv_adaptation import PROFIL_MAX_LEN, TITRE_MAX_LEN, _valider_et_appliquer
        reponse  = {'titre': 'A' * 500, 'profil': 'B' * 5000}
        resultat = _valider_et_appliquer(reponse, {'titre': 'old', 'profil': 'old'})
        self.assertEqual(len(resultat['titre']), TITRE_MAX_LEN)
        self.assertEqual(len(resultat['profil']), PROFIL_MAX_LEN)

    def test_ne_touche_pas_aux_autres_cles(self):
        """Seuls `titre`/`profil` changent — le reste du dict CV est recopie tel quel."""
        from candidat.cv_adaptation import _valider_et_appliquer
        cv_dict  = {'titre': 'old', 'profil': 'old', 'experiences': ['A'], 'competences': ['B'], 'nomCv': 'Mon CV'}
        resultat = _valider_et_appliquer({'titre': 'new', 'profil': 'new'}, cv_dict)
        self.assertEqual(resultat['experiences'], ['A'])
        self.assertEqual(resultat['competences'], ['B'])
        self.assertEqual(resultat['nomCv'], 'Mon CV')
        # Le dict source n'est jamais mute (copie defensive).
        self.assertEqual(cv_dict['titre'], 'old')


class CompetencesManquantesTest(TestCase):
    """candidat.matching.competences_manquantes — suggestion d'ecart, purement informatif."""

    def setUp(self):
        self.candidat = Candidat(
            email='gaps@example.com', type_compte=TypeCompte.CANDIDAT,
            nom='Test', prenom='Gaps', emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()
        Competence.objects.create(candidat=self.candidat, nomLibre='Python')

        self.entreprise = Entreprise.objects.create(
            raisonSocial='Gaps Corp', emailProfessionnel='gaps@entreprise.ci',
        )
        self.entreprise.set_password('test')
        self.entreprise.save()

    def test_renvoie_les_competences_absentes_du_profil(self):
        from candidat.matching import competences_manquantes
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise, titre='Poste Test', typeContrat='CDI',
            competencesRequises=['Python', 'Negociation', 'CRM'],
        )
        manquantes = competences_manquantes(self.candidat, offre)
        self.assertNotIn('Python', manquantes)
        self.assertIn('Negociation', manquantes)
        self.assertIn('CRM', manquantes)

    def test_aucun_ecart_si_offre_ne_precise_rien(self):
        from candidat.matching import competences_manquantes
        offre = OffreEmploi.objects.create(
            entreprise=self.entreprise, titre='Poste Sans Competences', typeContrat='CDI',
        )
        self.assertEqual(competences_manquantes(self.candidat, offre), [])


class ExperienceRankingTest(TestCase):
    """Classement local (sans IA) des experiences/competences — candidat.experience_ranking."""

    def test_repli_sans_moteur_semantique(self):
        from candidat import experience_ranking
        experiences = [{'entreprise': f'E{i}', 'postes': [{'titre': f'P{i}'}]} for i in range(5)]
        with patch('candidat.matching_semantic.est_disponible', return_value=False):
            resultat = experience_ranking.classer_experiences_par_pertinence(experiences, offre=None, top_n=3)
        self.assertEqual(resultat, experiences[:3])

    def test_reordonner_competences_priorise_les_correspondances(self):
        from unittest.mock import MagicMock

        from candidat import experience_ranking
        offre = MagicMock()
        offre.competencesRequises = ['Python']
        offre.typesCompetence.all.return_value = []
        competences = [{'nom': 'Excel'}, {'nom': 'Python'}, {'nom': 'Photoshop'}]
        resultat = experience_ranking.reordonner_competences(competences, offre)
        self.assertEqual(resultat[0]['nom'], 'Python')


class CvAdaptationIAViewTest(TestCase):
    """Vues de l'adaptation IA de CV (declenchement, statut, ouverture editeur)."""

    def setUp(self):
        self.client = Client()
        cache.clear()

        self.candidat = Candidat(
            email='cvia@example.com', type_compte=TypeCompte.CANDIDAT,
            nom='Dupont', prenom='Marie', emailVerifie=True,
        )
        self.candidat.set_password('test123')
        self.candidat.save()

        self.entreprise = Entreprise.objects.create(
            raisonSocial='CV IA Corp', emailProfessionnel='cvia@entreprise.ci',
        )
        self.entreprise.set_password('test')
        self.entreprise.save()

        self.offre = OffreEmploi.objects.create(
            entreprise=self.entreprise, titre='Developpeuse Django',
            typeContrat='CDI', statutOffre=StatutOffre.PUBLIEE,
        )

        self.modele = ModeleCV.objects.create(nom='Classic Blue Test', fichier='classic-blue')

        snapshot = {
            'prenom': 'Marie', 'nom': 'Dupont', 'titre': 'Developpeuse Python',
            'email': 'cvia@example.com', 'telephone': '', 'ville': '', 'pays': '',
            'adresse': '', 'age': '', 'linkedin': '', 'portfolio': '', 'permis': '',
            'profil': "Developpeuse avec 3 ans d'experience Django.",
            'showCertif': True, 'showProjets': True, 'showBenev': True, 'showRef': True,
            'interetsMasques': [],
            'experiences': [{
                'id': 1, 'entreprise': 'Acme', 'ville': 'Abidjan', 'pays': 'CI', 'lieu': 'Abidjan, CI',
                'debut': '2021-01', 'fin': '2023-01', 'enCours': False,
                'postes': [{'id': 1, 'titre': 'Developpeuse Backend', 'debut': '2021-01', 'fin': '2023-01', 'enCours': False}],
                'hasMissionsClient': False, 'missionsClient': [],
            }],
            'formations': [], 'competences': [{'id': 1, 'nom': 'Python'}],
            'langues': [], 'interets': [], 'projets': [], 'benevs': [],
            'elementsMasques': {},
        }
        contenu = CVContenu.objects.create(donneesSnapshot=snapshot)
        self.cv_source = CV.objects.create(
            candidat=self.candidat, modele=self.modele, contenu=contenu,
            nomCv='Mon CV Backend', titre='Developpeuse Python', profil=snapshot['profil'],
        )

    def tearDown(self):
        cache.clear()

    @patch('recrutement.background.lancer_en_arriere_plan')
    def test_declenchement_lance_tache_fond(self, mock_bg):
        self.client.force_login(self.candidat)
        resp = self.client.post(
            reverse('candidat:lancer_adaptation_cv_ia', args=[self.offre.pk]),
            data=json.dumps({'cv_id': self.cv_source.pk}), content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.content)['ok'])
        mock_bg.assert_called_once()
        args = mock_bg.call_args[0]
        self.assertEqual(args[0].__name__, 'adapter_cv_ia')
        self.assertEqual(args[1:], (self.candidat.pk, self.offre.pk, self.cv_source.pk))

    @patch('recrutement.background.lancer_en_arriere_plan')
    def test_declenchement_cv_inexistant_404(self, mock_bg):
        self.client.force_login(self.candidat)
        resp = self.client.post(
            reverse('candidat:lancer_adaptation_cv_ia', args=[self.offre.pk]),
            data=json.dumps({'cv_id': 999999}), content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)
        mock_bg.assert_not_called()

    def test_declenchement_sans_connexion_redirige(self):
        resp = self.client.post(
            reverse('candidat:lancer_adaptation_cv_ia', args=[self.offre.pk]),
            data=json.dumps({'cv_id': self.cv_source.pk}), content_type='application/json',
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('connexion', resp.url)

    @patch('recrutement.background.lancer_en_arriere_plan')
    def test_quota_quotidien_bloque_apres_limite(self, mock_bg):
        from candidat.views.cv_ai import QUOTA_QUOTIDIEN_CV_IA
        self.client.force_login(self.candidat)
        lock_key = f'cv_ia_computing_{self.candidat.pk}_{self.offre.pk}_{self.cv_source.pk}'
        for _ in range(QUOTA_QUOTIDIEN_CV_IA):
            resp = self.client.post(
                reverse('candidat:lancer_adaptation_cv_ia', args=[self.offre.pk]),
                data=json.dumps({'cv_id': self.cv_source.pk}), content_type='application/json',
            )
            self.assertEqual(resp.status_code, 200)
            # Simule la fin de la tache fond (mockee = ne le fait jamais elle-meme).
            cache.delete(lock_key)
        resp = self.client.post(
            reverse('candidat:lancer_adaptation_cv_ia', args=[self.offre.pk]),
            data=json.dumps({'cv_id': self.cv_source.pk}), content_type='application/json',
        )
        self.assertEqual(resp.status_code, 429)

    def test_statut_computing_par_defaut(self):
        self.client.force_login(self.candidat)
        resp = self.client.get(
            reverse('candidat:statut_adaptation_cv_ia', args=[self.offre.pk]),
            {'cv_id': self.cv_source.pk},
        )
        self.assertEqual(json.loads(resp.content)['status'], 'computing')

    def test_statut_ready_renvoie_redirect_url(self):
        self.client.force_login(self.candidat)
        status_key = f'cv_ia_status_{self.candidat.pk}_{self.offre.pk}_{self.cv_source.pk}'
        cache.set(status_key, {'status': 'ready', 'message': ''}, 600)
        resp = self.client.get(
            reverse('candidat:statut_adaptation_cv_ia', args=[self.offre.pk]),
            {'cv_id': self.cv_source.pk},
        )
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'ready')
        self.assertIn(str(self.offre.pk), data['redirect_url'])
        self.assertIn(str(self.cv_source.pk), data['redirect_url'])

    def test_ouverture_editeur_avec_cache(self):
        from candidat.cv import _cv_to_dict
        self.client.force_login(self.candidat)
        adapted = _cv_to_dict(self.cv_source)
        adapted['titre']  = 'Titre adapte'
        adapted['profil'] = 'Profil adapte'
        adapted['nomCv']  = 'Mon CV Backend — adapte'
        result_key = f'cv_ia_result_{self.candidat.pk}_{self.offre.pk}_{self.cv_source.pk}'
        cache.set(result_key, adapted, 600)

        resp = self.client.get(
            reverse('candidat:creer_cv_depuis_adaptation', args=[self.offre.pk, self.cv_source.pk]),
        )
        self.assertEqual(resp.status_code, 200)

    def test_ouverture_editeur_cache_expire_redirige(self):
        self.client.force_login(self.candidat)
        resp = self.client.get(
            reverse('candidat:creer_cv_depuis_adaptation', args=[self.offre.pk, 999999]),
        )
        self.assertEqual(resp.status_code, 302)

    def test_offre_detail_contient_carte_adaptation_ia(self):
        """La carte d'adaptation IA apparait sur la page offre pour un candidat avec CV."""
        self.client.force_login(self.candidat)
        resp = self.client.get(reverse('candidat:offre_detail', args=[self.offre.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'adaptationCvIa')

    def test_bout_en_bout_dict_adapte_sauvegarde_via_flux_existant(self):
        """Le dict produit par `adapter_cv_pour_offre` passe par `sauvegarder_cv`
        SANS AUCUNE modification de cet endpoint — preuve que la reutilisation
        du flux d'edition existant fonctionne reellement."""
        from candidat.cv_adaptation import adapter_cv_pour_offre

        with patch('candidat.cv_adaptation.generer_json', return_value={
            'titre':  'Developpeuse Backend Django — orientee offre',
            'profil': 'Profil reformule pour coller au vocabulaire de l\'offre.',
        }):
            adapted = adapter_cv_pour_offre(self.cv_source, self.offre)

        self.assertNotEqual(adapted['nomCv'], self.cv_source.nomCv)
        self.assertEqual(adapted['titre'], 'Developpeuse Backend Django — orientee offre')

        self.client.force_login(self.candidat)
        resp = self.client.post(
            reverse('candidat:api_sauvegarder_cv', args=[self.modele.pk]),
            data=json.dumps({
                'cv_id': None, 'titre': adapted['titre'], 'nom_cv': adapted['nomCv'], 'cv': adapted,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(CV.objects.filter(candidat=self.candidat).count(), 2)

        nouveau = CV.objects.get(candidat=self.candidat, nomCv=adapted['nomCv'])
        self.assertEqual(nouveau.titre, adapted['titre'])

        self.cv_source.refresh_from_db()
        self.assertEqual(self.cv_source.titre, 'Developpeuse Python')
        self.assertEqual(self.cv_source.nomCv, 'Mon CV Backend')
