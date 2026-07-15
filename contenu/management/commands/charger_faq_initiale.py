from django.core.management.base import BaseCommand
from django.utils.text import slugify
from contenu.models import FaqCategorie, FaqQuestion

CATEGORIES = [
    {'slug': 'compte',     'label': 'Compte & Inscription',   'icone': '👤', 'ordre': 1},
    {'slug': 'cv',         'label': 'CV',                     'icone': '📄', 'ordre': 2},
    {'slug': 'lettre',     'label': 'Lettre de motivation',   'icone': '✉️', 'ordre': 3},
    {'slug': 'newsletter', 'label': 'Newsletter',             'icone': '📬', 'ordre': 4},
    {'slug': 'premium',    'label': 'Premium',                'icone': '👑', 'ordre': 5},
    {'slug': 'offres',     'label': "Offres d'emploi",        'icone': '💼', 'ordre': 6},
]

QUESTIONS = [
    # ── Compte ──────────────────────────────────────────────────────────────
    ('compte', 'Comment créer un compte sur la plateforme ?',
     'Cliquez sur <strong>Inscription</strong> en haut à droite, renseignez votre prénom, nom, '
     'e-mail et mot de passe, puis validez. Vous pouvez aussi vous connecter directement avec Google ou GitHub.', 1),

    ('compte', "J'ai oublié mon mot de passe. Comment le réinitialiser ?",
     'Sur la page de connexion, cliquez sur <strong>Mot de passe oublié</strong>. Entrez votre e-mail '
     'et choisissez de recevoir un code à 5 chiffres ou un lien magique. Le code est valable 10 minutes.', 2),

    ('compte', 'Puis-je modifier mon adresse e-mail ?',
     'Oui, rendez-vous dans <strong>Mon profil</strong> → onglet <em>Informations personnelles</em>. '
     'Modifiez l\'e-mail et enregistrez. Attention, le nouvel e-mail doit être unique sur la plateforme.', 3),

    ('compte', 'Comment supprimer mon compte ?',
     'Pour l\'instant, la suppression se fait en contactant notre support. Envoyez un e-mail à '
     '<a href="mailto:support@recrutepro.ci">support@recrutepro.ci</a> avec votre adresse '
     'e-mail d\'inscription et nous traiterons votre demande sous 48h.', 4),

    # ── CV ──────────────────────────────────────────────────────────────────
    ('cv', 'Comment créer mon CV sur la plateforme ?',
     'Allez dans <strong>Modèles → Modèles CV</strong>, choisissez un modèle gratuit ou premium, '
     'cliquez sur <em>Rédiger avec ce modèle</em>. Le builder s\'ouvre : remplissez le formulaire '
     'et la prévisualisation se met à jour en temps réel.', 1),

    ('cv', 'Quels formats de téléchargement sont disponibles ?',
     'Vous pouvez télécharger votre CV en <strong>PDF</strong> (haute qualité, idéal pour postuler) '
     'et en <strong>Word (DOCX)</strong> (modifiable). Le format PNG est également disponible pour '
     'certains modèles.', 2),

    ('cv', 'Mon brouillon de CV est-il sauvegardé automatiquement ?',
     'Oui ! Le builder sauvegarde automatiquement votre brouillon dans votre navigateur (localStorage). '
     'Un indicateur vert <em>Brouillon sauvegardé</em> s\'affiche après chaque modification. '
     'Le brouillon est restauré lors de votre prochain accès.', 3),

    ('cv', "Puis-je changer de modèle après avoir rempli mon CV ?",
     'Oui, dans le builder, cliquez sur n\'importe quel modèle dans la barre de sélection en haut. '
     'Le contenu que vous avez saisi est conservé, seul le style visuel change.', 4),

    ('cv', "Qu'est-ce que les missions chez les clients ?",
     'Dans la section <strong>Expériences</strong>, activez le toggle <em>Missions chez les clients</em> '
     'pour détailler les missions réalisées dans le cadre d\'une expérience (très utile pour les '
     'consultants et prestataires).', 5),

    # ── Lettre ──────────────────────────────────────────────────────────────
    ('lettre', 'Comment rédiger ma lettre de motivation ?',
     'Allez dans <strong>Modèles → Lettre de motivation</strong>, choisissez un modèle, cliquez sur '
     '<em>Rédiger avec ce modèle</em>. Remplissez les 5 sections (coordonnées, destinataire, '
     'date & objet, corps, formule de politesse). La prévisualisation se met à jour en temps réel.', 1),

    ('lettre', 'Puis-je changer le modèle de lettre en cours de rédaction ?',
     'Oui, dans le builder, les modèles disponibles sont listés dans la barre du haut. Cliquez sur '
     "l'un d'eux pour changer le style sans perdre votre contenu.", 2),

    ('lettre', 'Comment personnaliser la formule de politesse ?',
     'Dans l\'onglet <strong>Formule de politesse</strong>, tapez votre formule. Utilisez les variables '
     '<code>[titre]</code> et <code>[nom]</code> pour intégrer automatiquement les informations du '
     'destinataire. Des modèles prédéfinis (Classique, Longue, Courte) sont proposés en raccourcis.', 3),

    # ── Newsletter ───────────────────────────────────────────────────────────
    ('newsletter', "Comment m'abonner à la newsletter ?",
     "Sur la page d'accueil, entrez votre e-mail dans la section <em>Newsletter</em> et cliquez sur "
     "<strong>S'abonner</strong>. Vous recevrez un e-mail de confirmation. Si vous êtes connecté, "
     'vous pouvez aussi gérer votre abonnement dans <strong>Mon profil → Confidentialité</strong>.', 1),

    ('newsletter', 'Comment me désabonner de la newsletter ?',
     'Trois façons :<br>① Cliquez sur le lien <strong>Me désabonner</strong> en bas de chaque e-mail '
     'de newsletter.<br>② Allez dans <strong>Mon profil → Confidentialité</strong> et cliquez sur '
     "<em>Se désabonner</em>.<br>③ Rendez-vous sur la page <em>Gérer ma newsletter</em>, entrez "
     'votre e-mail et désabonnez-vous.', 2),

    ('newsletter', 'À quelle fréquence la newsletter est-elle envoyée ?',
     'La newsletter est envoyée <strong>une fois par semaine</strong>, chaque lundi matin. Elle contient '
     "une sélection des meilleures offres d'emploi, des conseils carrière et les actualités du marché "
     "de l'emploi ivoirien.", 3),

    # ── Premium ──────────────────────────────────────────────────────────────
    ('premium', "Qu'est-ce que le compte Premium ?",
     'Le compte Premium donne accès à <strong>tous les modèles CV et lettre exclusifs</strong>, '
     "l'export PDF haute qualité illimité, l'export Word illimité et une mise en avant de votre "
     'profil auprès des recruteurs.', 1),

    ('premium', 'Quel est le prix du compte Premium ?',
     "L'abonnement Premium est à <strong>5 000 FCFA/mois</strong> pendant 3 mois (au lieu de "
     '10 000 FCFA). Soit un accès complet à toutes les fonctionnalités pendant 3 mois.', 2),

    ('premium', "Comment payer l'abonnement Premium ?",
     'Le paiement se fait via <strong>Mobile Money</strong> (Orange Money, MTN MoMo, Wave) et par '
     'carte bancaire. Le processus de paiement est sécurisé. Contactez le support pour toute question.', 3),

    ('premium', 'Les modèles gratuits sont-ils de bonne qualité ?',
     'Absolument ! Les modèles gratuits sont professionnels et adaptés à tous les secteurs. '
     'Les modèles Premium offrent simplement des designs plus élaborés et des fonctionnalités avancées.', 4),

    # ── Offres ───────────────────────────────────────────────────────────────
    ("offres", "Comment postuler à une offre d'emploi ?",
     'Consultez les offres disponibles dans la section <strong>Offres d\'emploi</strong>. Cliquez sur '
     'une offre pour voir le détail, puis sur <em>Postuler</em>. Vous devrez être connecté et avoir '
     'un CV créé sur la plateforme.', 1),

    ('offres', 'Comment suivre l\'état de mes candidatures ?',
     'Toutes vos candidatures sont accessibles dans <strong>Mes candidatures</strong> depuis la navbar. '
     'Vous y verrez le statut de chaque dossier : En attente, Vu, Entretien, Refusé, Accepté.', 2),

    ('offres', "Puis-je retirer une candidature après l'avoir envoyée ?",
     'Oui, depuis la page <strong>Mes candidatures</strong>, vous pouvez retirer une candidature tant '
     "qu'elle est au statut <em>En attente</em>. Une fois la candidature traitée par le recruteur, "
     'le retrait n\'est plus possible.', 3),
]


class Command(BaseCommand):
    help = "Charge les catégories et questions FAQ initiales en base"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Supprime toutes les données FAQ avant de recharger')

    def handle(self, *args, **options):
        if options['reset']:
            FaqQuestion.objects.all().delete()
            FaqCategorie.objects.all().delete()
            self.stdout.write(self.style.WARNING('Données FAQ supprimées.'))

        cats_created = 0
        for c in CATEGORIES:
            _, created = FaqCategorie.objects.get_or_create(
                slug=c['slug'],
                defaults={'label': c['label'], 'icone': c['icone'], 'ordre': c['ordre']},
            )
            if created:
                cats_created += 1

        qs_created = 0
        for cat_slug, question, reponse, ordre in QUESTIONS:
            try:
                cat = FaqCategorie.objects.get(slug=cat_slug)
            except FaqCategorie.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Catégorie introuvable : {cat_slug}'))
                continue
            _, created = FaqQuestion.objects.get_or_create(
                categorie=cat, question=question,
                defaults={'reponse': reponse, 'ordre': ordre},
            )
            if created:
                qs_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'{cats_created} catégorie(s) et {qs_created} question(s) créées.'
        ))
