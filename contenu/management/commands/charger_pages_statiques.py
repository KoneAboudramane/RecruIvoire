from datetime import date
from django.core.management.base import BaseCommand
from contenu.models import PageStatique, SectionPage, Fonctionnalite, OffreTarif, ChiffreCle

PAGES = [
    {
        'slug': 'confidentialite',
        'titre': 'Politique de confidentialité',
        'description': 'Comment nous collectons, utilisons et protégeons vos données personnelles.',
        'mise_a_jour': date(2026, 3, 1),
        'sections': [
            {
                'ancre': 'collecte', 'icone': '📋', 'ordre': 1,
                'titre': '1. Données collectées',
                'contenu': (
                    '<p class="mb-4">Dans le cadre de l\'utilisation de la plateforme, nous collectons les informations suivantes :</p>'
                    '<ul>'
                    '<li><strong>Données d\'identité</strong> : prénom, nom, adresse e-mail, mot de passe (chiffré)</li>'
                    '<li><strong>Données de profil</strong> : photo, téléphone, date de naissance, nationalité, ville</li>'
                    '<li><strong>Données professionnelles</strong> : CV, lettres de motivation, portfolio, expériences, formations, compétences</li>'
                    '<li><strong>Données de connexion</strong> : adresse IP, navigateur, date et heure de connexion, pages visitées</li>'
                    '<li><strong>Données de communication</strong> : messages envoyés via le formulaire de contact</li>'
                    '<li><strong>Données de newsletter</strong> : adresse e-mail des abonnés et statut d\'abonnement</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'utilisation', 'icone': '⚙️', 'ordre': 2,
                'titre': '2. Utilisation des données',
                'contenu': (
                    '<p class="mb-4">Vos données sont utilisées pour :</p>'
                    '<ul>'
                    '<li>Créer et gérer votre compte candidat</li>'
                    '<li>Générer, afficher et télécharger vos CV et lettres de motivation</li>'
                    '<li>Afficher votre portfolio professionnel</li>'
                    '<li>Vous envoyer des e-mails de confirmation, de réinitialisation de mot de passe et de newsletter</li>'
                    '<li>Traiter vos demandes via le formulaire de contact</li>'
                    '<li>Améliorer nos services grâce à des statistiques anonymisées</li>'
                    '<li>Respecter nos obligations légales</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'partage', 'icone': '🤝', 'ordre': 3,
                'titre': '3. Partage des données',
                'contenu': (
                    '<p class="mb-4">Vos données personnelles ne sont <strong>jamais vendues</strong> à des tiers. Elles peuvent être transmises dans les cas suivants :</p>'
                    '<ul>'
                    '<li><strong>Prestataires techniques</strong> : hébergeur, fournisseur d\'e-mail (dans le strict cadre du service)</li>'
                    '<li><strong>Entreprises recruteuses</strong> : uniquement si vous postulez à une offre (avec votre consentement explicite)</li>'
                    '<li><strong>Portfolio public</strong> : les données de votre portfolio sont visibles si vous activez le lien public</li>'
                    '<li><strong>Autorités</strong> : sur réquisition légale uniquement</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'conservation', 'icone': '🗓️', 'ordre': 4,
                'titre': '4. Durée de conservation',
                'contenu': (
                    '<ul>'
                    '<li><strong>Compte actif</strong> : données conservées pendant toute la durée d\'activité du compte</li>'
                    '<li><strong>Compte supprimé</strong> : données effacées sous <strong>30 jours</strong> après suppression</li>'
                    '<li><strong>Newsletter</strong> : e-mail conservé jusqu\'au désabonnement, supprimé sous 7 jours après demande</li>'
                    '<li><strong>Logs de connexion</strong> : conservés 12 mois pour des raisons de sécurité</li>'
                    '<li><strong>Messages de contact</strong> : conservés 2 ans à titre d\'archive</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'cookies', 'icone': '🍪', 'ordre': 5,
                'titre': '5. Cookies et traceurs',
                'contenu': (
                    '<p class="mb-4">Nous utilisons uniquement les cookies <strong>strictement nécessaires</strong> au fonctionnement du site :</p>'
                    '<ul>'
                    '<li><strong>Session Django</strong> (<code>sessionid</code>) : maintient votre connexion</li>'
                    '<li><strong>Protection CSRF</strong> (<code>csrftoken</code>) : sécurise les formulaires</li>'
                    '<li><strong>Préférence de langue</strong> (<code>django_language</code>) : mémorise votre langue</li>'
                    '<li><strong>Thème</strong> (<code>theme</code> en localStorage) : mémorise le mode sombre/clair</li>'
                    '</ul>'
                    '<p class="mt-4">Aucun cookie publicitaire ou de tracking tiers n\'est utilisé.</p>'
                ),
            },
            {
                'ancre': 'droits', 'icone': '⚖️', 'ordre': 6,
                'titre': '6. Vos droits',
                'contenu': (
                    '<p class="mb-4">Conformément à la réglementation applicable, vous disposez des droits suivants sur vos données :</p>'
                    '<ul>'
                    '<li><strong>Droit d\'accès</strong> : obtenir une copie de vos données personnelles</li>'
                    '<li><strong>Droit de rectification</strong> : corriger des informations inexactes (depuis votre profil)</li>'
                    '<li><strong>Droit à l\'effacement</strong> : demander la suppression de votre compte et de vos données</li>'
                    '<li><strong>Droit d\'opposition</strong> : vous opposer au traitement de vos données à des fins marketing</li>'
                    '<li><strong>Droit à la portabilité</strong> : recevoir vos données dans un format structuré</li>'
                    '</ul>'
                    '<p class="mt-4">Pour exercer ces droits, contactez-nous à : <a href="mailto:privacy@recrutepro.ci" class="font-semibold underline" style="color:#c96010;">privacy@recrutepro.ci</a></p>'
                ),
            },
            {
                'ancre': 'securite', 'icone': '🔒', 'ordre': 7,
                'titre': '7. Sécurité des données',
                'contenu': (
                    '<p class="mb-4">Nous mettons en œuvre des mesures techniques et organisationnelles pour protéger vos données :</p>'
                    '<ul>'
                    '<li>Mots de passe chiffrés via <strong>PBKDF2-SHA256</strong> (jamais stockés en clair)</li>'
                    '<li>Connexions sécurisées via <strong>HTTPS/TLS</strong></li>'
                    '<li>Jetons UUID pour les liens de réinitialisation et de désabonnement</li>'
                    '<li>Protection anti-CSRF sur tous les formulaires</li>'
                    '<li>Champs honeypot anti-spam sur le formulaire de contact</li>'
                    '<li>Accès administrateur limité et protégé</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'mineurs', 'icone': '👶', 'ordre': 8,
                'titre': '8. Mineurs',
                'contenu': (
                    '<p>La plateforme est destinée à des personnes de <strong>18 ans et plus</strong>. '
                    'Nous ne collectons pas sciemment de données personnelles de mineurs. '
                    'Si vous êtes parent ou tuteur et pensez que votre enfant nous a fourni des données, '
                    'contactez-nous à <a href="mailto:privacy@recrutepro.ci" class="underline font-medium" style="color:#c96010;">privacy@recrutepro.ci</a> '
                    'afin que nous procédions à leur suppression.</p>'
                ),
            },
            {
                'ancre': 'modifications', 'icone': '📝', 'ordre': 9,
                'titre': '9. Modifications de la politique',
                'contenu': (
                    '<p>Nous pouvons modifier cette politique à tout moment. En cas de changement significatif, '
                    'les utilisateurs inscrits en seront informés par e-mail ou par une notification visible sur le site. '
                    'La date de mise à jour en haut de page indique la version en vigueur. '
                    'La poursuite de l\'utilisation du service après modification vaut acceptation de la nouvelle politique.</p>'
                ),
            },
            {
                'ancre': 'contact', 'icone': '📧', 'ordre': 10,
                'titre': '10. Nous contacter',
                'contenu': (
                    '<p class="mb-4">Pour toute question relative à cette politique ou à vos données personnelles :</p>'
                    '<ul>'
                    '<li><strong>E-mail confidentialité</strong> : <a href="mailto:privacy@recrutepro.ci" class="underline font-medium" style="color:#c96010;">privacy@recrutepro.ci</a></li>'
                    '<li><strong>Adresse</strong> : Cocody, Abidjan, Côte d\'Ivoire</li>'
                    '</ul>'
                    '<p class="mt-4 text-xs text-gray-400">Nous nous engageons à répondre à vos demandes dans un délai de <strong>30 jours</strong>.</p>'
                ),
            },
        ],
    },
    {
        'slug': 'cgu',
        'titre': "Conditions Générales d'Utilisation",
        'description': (
            'En accédant à la plateforme et en utilisant ses services, vous acceptez sans réserve '
            'les présentes Conditions Générales d\'Utilisation. Si vous n\'acceptez pas ces conditions, '
            'veuillez ne pas utiliser la plateforme.'
        ),
        'mise_a_jour': date(2026, 6, 1),
        'sections': [
            {
                'ancre': 'objet', 'icone': '📄', 'ordre': 1,
                'titre': 'Objet',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed">'
                    'La plateforme est un service de recrutement en ligne permettant la mise en relation entre des candidats '
                    'à l\'emploi et des entreprises recruteuses. Les présentes CGU définissent les conditions d\'accès et '
                    'd\'utilisation de la plateforme, accessible à l\'adresse indiquée sur le site.'
                    '</p>'
                ),
            },
            {
                'ancre': 'acces', 'icone': '🔑', 'ordre': 2,
                'titre': 'Accès à la plateforme',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed mb-3">L\'accès à certaines fonctionnalités nécessite la création d\'un compte. Vous devez :</p>'
                    '<ul class="space-y-1.5 text-sm text-gray-600">'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Avoir au moins 18 ans</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Fournir des informations exactes, complètes et à jour lors de votre inscription</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Maintenir la confidentialité de votre mot de passe</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Notifier immédiatement toute utilisation non autorisée de votre compte</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'candidats', 'icone': '👤', 'ordre': 3,
                'titre': 'Obligations des candidats',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed mb-3">En tant que candidat, vous vous engagez à :</p>'
                    '<ul class="space-y-1.5 text-sm text-gray-600">'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Renseigner des informations véridiques dans votre profil, votre CV et vos lettres de motivation</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Ne pas usurper l\'identité d\'une autre personne</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Ne postuler qu\'aux offres pour lesquelles vous êtes réellement intéressé</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Ne pas utiliser la messagerie à des fins de démarchage commercial ou de spam</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Respecter les recruteurs et maintenir un comportement professionnel dans toutes vos communications</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'entreprises', 'icone': '🏢', 'ordre': 4,
                'titre': 'Obligations des entreprises',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed mb-3">En tant qu\'entreprise, vous vous engagez à :</p>'
                    '<ul class="space-y-1.5 text-sm text-gray-600">'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Publier uniquement des offres d\'emploi réelles et légales</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Ne pas publier d\'offres discriminatoires ou contraires à la législation ivoirienne</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Traiter les données des candidats avec respect et conformément à la réglementation</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Informer les candidats des suites données à leur candidature dans des délais raisonnables</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Ne pas utiliser les coordonnées des candidats à des fins autres que le recrutement</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'contenu-interdit', 'icone': '🚫', 'ordre': 5,
                'titre': 'Contenu interdit',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed mb-3">Il est strictement interdit de publier ou de transmettre du contenu :</p>'
                    '<ul class="space-y-1.5 text-sm text-gray-600">'
                    '<li class="flex items-start gap-2"><span style="color:#ef4444;">✕</span> Illicite, diffamatoire, obscène ou portant atteinte à l\'ordre public</li>'
                    '<li class="flex items-start gap-2"><span style="color:#ef4444;">✕</span> Portant atteinte aux droits de tiers (marques, brevets, droits d\'auteur)</li>'
                    '<li class="flex items-start gap-2"><span style="color:#ef4444;">✕</span> Contenant des virus, malwares ou tout code malveillant</li>'
                    '<li class="flex items-start gap-2"><span style="color:#ef4444;">✕</span> Constituant du spam, du phishing ou toute forme de démarchage non sollicité</li>'
                    '<li class="flex items-start gap-2"><span style="color:#ef4444;">✕</span> Contenant des offres d\'emploi fictives ou frauduleuses</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'propriete', 'icone': '©️', 'ordre': 6,
                'titre': 'Propriété intellectuelle',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed">'
                    'L\'ensemble des éléments composant la plateforme (logo, interface, code source, textes, modèles de CV et de lettres) '
                    'est la propriété exclusive de l\'éditeur et protégé par le droit de la propriété intellectuelle. '
                    'Toute reproduction, même partielle, est interdite sans autorisation préalable écrite.'
                    '</p>'
                    '<p class="text-sm text-gray-600 leading-relaxed mt-3">'
                    'En publiant du contenu sur la plateforme (CV, profil, offre d\'emploi), vous accordez à l\'éditeur '
                    'une licence non exclusive d\'utilisation pour le bon fonctionnement du service.'
                    '</p>'
                ),
            },
            {
                'ancre': 'responsabilite', 'icone': '⚖️', 'ordre': 7,
                'titre': 'Responsabilité',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed mb-3">La plateforme agit en qualité d\'intermédiaire technique et ne peut être tenue responsable :</p>'
                    '<ul class="space-y-1.5 text-sm text-gray-600">'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Du contenu publié par les utilisateurs (offres, CV, messages)</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Des décisions de recrutement prises par les entreprises</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Des interruptions temporaires du service pour maintenance</li>'
                    '<li class="flex items-start gap-2"><span style="color:#c96010;">›</span> Des dommages résultant d\'une utilisation non conforme aux présentes CGU</li>'
                    '</ul>'
                ),
            },
            {
                'ancre': 'resiliation', 'icone': '🚪', 'ordre': 8,
                'titre': 'Suspension et résiliation',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed">'
                    'La plateforme se réserve le droit de suspendre ou supprimer sans préavis tout compte dont le comportement '
                    'serait contraire aux présentes CGU, à la législation applicable ou aux bonnes mœurs. '
                    'L\'utilisateur peut clore son compte à tout moment en contactant le support.'
                    '</p>'
                ),
            },
            {
                'ancre': 'modifications', 'icone': '📝', 'ordre': 9,
                'titre': 'Modifications des CGU',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed">'
                    'L\'éditeur se réserve le droit de modifier les présentes CGU à tout moment. '
                    'Les utilisateurs seront informés de toute modification substantielle par e-mail ou via une notification sur le site. '
                    'La poursuite de l\'utilisation du service après modification vaut acceptation des nouvelles conditions.'
                    '</p>'
                ),
            },
            {
                'ancre': 'droit', 'icone': '🏛️', 'ordre': 10,
                'titre': 'Droit applicable et litiges',
                'contenu': (
                    '<p class="text-sm text-gray-600 leading-relaxed">'
                    'Les présentes CGU sont soumises au droit ivoirien. En cas de litige, les parties s\'engagent à rechercher '
                    'une solution amiable avant tout recours judiciaire. À défaut, les tribunaux compétents d\'Abidjan seront seuls compétents.'
                    '</p>'
                ),
            },
        ],
    },
    {
        'slug': 'mentions-legales',
        'titre': 'Mentions légales',
        'description': 'Conformément aux dispositions légales en vigueur.',
        'mise_a_jour': date(2026, 1, 1),
        'sections': [
            {
                'ancre': 'editeur', 'icone': '🏢', 'ordre': 1,
                'titre': 'Éditeur du site',
                'contenu': (
                    '<dl class="space-y-2 text-sm text-gray-600">'
                    '<div class="flex gap-2"><dt class="font-semibold text-gray-700 w-40 flex-shrink-0">Pays :</dt><dd>Côte d\'Ivoire</dd></div>'
                    '<div class="flex gap-2"><dt class="font-semibold text-gray-700 w-40 flex-shrink-0">Email :</dt><dd><a href="mailto:contact@recrutepro.ci" class="text-orange-600 hover:underline">contact@recrutepro.ci</a></dd></div>'
                    '</dl>'
                ),
            },
            {
                'ancre': 'directeur', 'icone': '👤', 'ordre': 2,
                'titre': 'Directeur de publication',
                'contenu': (
                    '<p class="text-sm text-gray-600">Le directeur de la publication est le responsable légal de la plateforme.</p>'
                ),
            },
            {
                'ancre': 'hebergement', 'icone': '🌐', 'ordre': 3,
                'titre': 'Hébergement',
                'contenu': (
                    '<p class="text-sm text-gray-600">Ce site est hébergé par un prestataire technique agréé. Les serveurs sont situés dans un datacenter sécurisé.</p>'
                ),
            },
            {
                'ancre': 'propriete', 'icone': '©️', 'ordre': 4,
                'titre': 'Propriété intellectuelle',
                'contenu': (
                    '<p class="text-sm text-gray-600">'
                    'L\'ensemble des contenus présents sur ce site (textes, images, logos, icônes) est la propriété exclusive de '
                    'l\'éditeur et est protégé par les lois sur la propriété intellectuelle. '
                    'Toute reproduction, même partielle, est interdite sans autorisation préalable.'
                    '</p>'
                ),
            },
            {
                'ancre': 'responsabilite', 'icone': '⚖️', 'ordre': 5,
                'titre': 'Limitation de responsabilité',
                'contenu': (
                    '<p class="text-sm text-gray-600">'
                    'La plateforme s\'efforce d\'assurer l\'exactitude et la mise à jour des informations diffusées sur ce site. '
                    'Toutefois, nous ne pouvons garantir l\'exactitude, la précision ou l\'exhaustivité des informations mises à disposition. '
                    'En conséquence, nous déclinons toute responsabilité pour toute imprécision, inexactitude ou omission portant sur des informations disponibles sur ce site.'
                    '</p>'
                ),
            },
            {
                'ancre': 'droit', 'icone': '🏛️', 'ordre': 6,
                'titre': 'Droit applicable',
                'contenu': (
                    '<p class="text-sm text-gray-600">'
                    'Les présentes mentions légales sont soumises au droit ivoirien. '
                    'En cas de litige, les tribunaux compétents d\'Abidjan seront seuls compétents.'
                    '</p>'
                ),
            },
        ],
    },
    {
        'slug': 'faq',
        'titre': 'Questions fréquentes',
        'description': 'Trouvez rapidement une réponse à votre question.',
        'mise_a_jour': None,
        'sections': [],
    },
    {
        'slug': 'contact',
        'titre': 'Nous contacter',
        'description': 'Une question, un problème ou une suggestion ? On est là pour vous.',
        'mise_a_jour': None,
        'sections': [],
    },
    {
        'slug': 'tarifs',
        'titre': 'Nos tarifs',
        'description': 'Des offres adaptées à chaque besoin, pour les candidats comme pour les entreprises.',
        'mise_a_jour': None,
        'sections': [],
    },
    {
        'slug': 'a-propos',
        'titre': 'Connecter les talents aux opportunités',
        'description': (
            'Né d\'une conviction simple : le recrutement en Côte d\'Ivoire mérite une plateforme moderne, '
            'intuitive et réellement adaptée aux réalités locales.'
        ),
        'mise_a_jour': None,
        'sections': [
            {
                'ancre': 'mission', 'icone': '🎯', 'ordre': 1,
                'titre': 'Notre mission',
                'contenu': (
                    'Simplifier le processus de recrutement pour les candidats comme pour les entreprises. '
                    'Nous donnons à chaque candidat les outils pour se démarquer — un CV professionnel, '
                    'une lettre de motivation soignée, et la visibilité auprès des bons recruteurs.'
                ),
            },
            {
                'ancre': 'vision', 'icone': '💡', 'ordre': 2,
                'titre': 'Notre vision',
                'contenu': (
                    'Devenir la référence du recrutement digital en Afrique de l\'Ouest, en offrant une expérience '
                    'de qualité internationale, adaptée aux marchés locaux, dans toutes les langues de nos utilisateurs.'
                ),
            },
            {
                'ancre': 'etape-candidat-1', 'icone': '1️⃣', 'ordre': 3,
                'titre': 'Créez votre compte',
                'contenu': 'Inscription gratuite en 2 minutes, via e-mail ou Google/GitHub.',
            },
            {
                'ancre': 'etape-candidat-2', 'icone': '2️⃣', 'ordre': 4,
                'titre': 'Construisez votre profil',
                'contenu': 'Créez votre CV avec nos modèles, rédigez votre lettre de motivation, complétez votre portfolio.',
            },
            {
                'ancre': 'etape-candidat-3', 'icone': '3️⃣', 'ordre': 5,
                'titre': 'Postulez & suivez vos candidatures',
                'contenu': 'Consultez les offres, postulez en un clic, suivez l\'avancement en temps réel.',
            },
            {
                'ancre': 'etape-entreprise-1', 'icone': '1️⃣', 'ordre': 6,
                'titre': 'Créez votre espace recruteur',
                'contenu': 'Compte gratuit, profil entreprise complet, invitez votre équipe RH.',
            },
            {
                'ancre': 'etape-entreprise-2', 'icone': '2️⃣', 'ordre': 7,
                'titre': 'Publiez vos offres d\'emploi',
                'contenu': 'Rédigez et publiez en quelques minutes. Les candidats correspondant à votre profil sont notifiés.',
            },
            {
                'ancre': 'etape-entreprise-3', 'icone': '3️⃣', 'ordre': 8,
                'titre': 'Gérez le pipeline et recrutez',
                'contenu': 'Scoring IA des candidats, planification des entretiens, messagerie intégrée.',
            },
            {
                'ancre': 'valeur-transparence', 'icone': '🤝', 'ordre': 9,
                'titre': 'Transparence',
                'contenu': 'Statut des candidatures en temps réel, communication ouverte entre candidats et recruteurs.',
            },
            {
                'ancre': 'valeur-confidentialite', 'icone': '🔒', 'ordre': 10,
                'titre': 'Confidentialité',
                'contenu': 'Vos données vous appartiennent. Aucune vente à des tiers, chiffrement end-to-end.',
            },
            {
                'ancre': 'valeur-inclusivite', 'icone': '🌍', 'ordre': 11,
                'titre': 'Inclusivité',
                'contenu': 'Disponible en 7 langues, accessible depuis n\'importe quel appareil, gratuit pour les candidats.',
            },
        ],
    },
]

OFFRES = [
    # ── Espace Candidat ──────────────────────────────────────────────────────────
    {
        'page_slug': 'tarifs', 'groupe': 'candidat', 'ordre': 1,
        'nom': 'Gratuit', 'prix': '0', 'unite': 'FCFA / mois',
        'badge': '', 'mise_en_avant': False, 'cta_desactive': False,
        'cta_texte': 'Commencer gratuitement', 'cta_url': '/candidat/inscription/',
        'fonctionnalites_list': [
            'Création de profil',
            "Jusqu'à 3 modèles de CV",
            "Jusqu'à 3 lettres de motivation",
            'Candidatures illimitées',
            "Alertes emploi (jusqu'à 3)",
            'Messagerie avec les recruteurs',
        ],
    },
    {
        'page_slug': 'tarifs', 'groupe': 'candidat', 'ordre': 2,
        'nom': 'Premium', 'prix': '—', 'unite': 'FCFA / mois',
        'badge': 'Bientôt', 'mise_en_avant': True, 'cta_desactive': True,
        'cta_texte': 'Disponible prochainement', 'cta_url': '',
        'fonctionnalites_list': [
            'Tout ce qui est inclus dans Gratuit',
            'CV illimités & modèles exclusifs',
            'Alertes emploi illimitées',
            'Profil mis en avant auprès des recruteurs',
            'Recommandations IA avancées',
            'Support prioritaire',
        ],
    },
    # ── Espace Entreprise ─────────────────────────────────────────────────────────
    {
        'page_slug': 'tarifs', 'groupe': 'entreprise', 'ordre': 1,
        'nom': 'Starter', 'prix': 'Gratuit', 'unite': '',
        'badge': '', 'mise_en_avant': False, 'cta_desactive': False,
        'cta_texte': 'Commencer', 'cta_url': '/entreprise/inscription/',
        'fonctionnalites_list': [
            '1 offre publiée simultanément',
            'Gestion des candidatures',
            'Messagerie candidats',
            '1 membre recruteur',
        ],
    },
    {
        'page_slug': 'tarifs', 'groupe': 'entreprise', 'ordre': 2,
        'nom': 'Pro', 'prix': 'À venir', 'unite': '',
        'badge': 'Populaire', 'mise_en_avant': True, 'cta_desactive': True,
        'cta_texte': 'Disponible prochainement', 'cta_url': '',
        'fonctionnalites_list': [
            'Offres illimitées',
            'Scoring IA des candidats',
            "Jusqu'à 5 recruteurs",
            'Statistiques avancées',
            'Support prioritaire',
        ],
    },
    {
        'page_slug': 'tarifs', 'groupe': 'entreprise', 'ordre': 3,
        'nom': 'Entreprise', 'prix': 'Sur mesure', 'unite': '',
        'badge': '', 'mise_en_avant': False, 'cta_desactive': False,
        'cta_texte': 'Nous contacter', 'cta_url': '/contact/',
        'fonctionnalites_list': [
            'Tout ce qui est inclus dans Pro',
            'Recruteurs illimités',
            'Intégration ATS personnalisée',
            'Accompagnement dédié',
        ],
    },
]

CHIFFRES = [
    {'page_slug': 'a-propos', 'chiffre': '29',  'label': 'modèles de CV',          'ordre': 1},
    {'page_slug': 'a-propos', 'chiffre': '6',   'label': 'modèles de lettre',       'ordre': 2},
    {'page_slug': 'a-propos', 'chiffre': '7',   'label': 'langues disponibles',     'ordre': 3},
    {'page_slug': 'a-propos', 'chiffre': 'IA',  'label': 'matching intelligent',    'ordre': 4},
]


class Command(BaseCommand):
    help = "Charge le contenu initial des pages statiques (confidentialité, CGU, mentions légales, tarifs, à propos)"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Supprime toutes les sections avant de recharger')

    def handle(self, *args, **options):
        pages_ok = sections_ok = offres_ok = chiffres_ok = 0

        # ── Pages + Sections ─────────────────────────────────────────────
        for p in PAGES:
            page, created = PageStatique.objects.get_or_create(
                slug=p['slug'],
                defaults={
                    'titre':       p['titre'],
                    'description': p['description'],
                    'mise_a_jour': p['mise_a_jour'],
                },
            )
            if not created:
                page.titre       = p['titre']
                page.description = p['description']
                if p['mise_a_jour']:
                    page.mise_a_jour = p['mise_a_jour']
                page.save(update_fields=['titre', 'description', 'mise_a_jour'])

            if options['reset']:
                page.sections.all().delete()
                page.offres.all().delete()
                page.chiffres.all().delete()

            for s in p['sections']:
                _, created = SectionPage.objects.get_or_create(
                    page=page, ancre=s['ancre'],
                    defaults={
                        'icone':   s['icone'],
                        'titre':   s['titre'],
                        'contenu': s['contenu'],
                        'ordre':   s['ordre'],
                    },
                )
                if created:
                    sections_ok += 1

            pages_ok += 1

        # ── Offres tarifaires + fonctionnalités ───────────────────────────
        for o in OFFRES:
            try:
                page = PageStatique.objects.get(slug=o['page_slug'])
            except PageStatique.DoesNotExist:
                continue
            offre, created = OffreTarif.objects.get_or_create(
                page=page, groupe=o['groupe'], nom=o['nom'],
                defaults={
                    'prix':          o['prix'],
                    'unite':         o['unite'],
                    'badge':         o['badge'],
                    'cta_texte':     o['cta_texte'],
                    'cta_url':       o['cta_url'],
                    'cta_desactive': o['cta_desactive'],
                    'mise_en_avant': o['mise_en_avant'],
                    'ordre':         o['ordre'],
                },
            )
            if created:
                offres_ok += 1
            # Recharge les fonctionnalités si reset ou création
            if created or options['reset']:
                offre.fonctionnalites_choisies.clear()
                for idx, texte in enumerate(o.get('fonctionnalites_list', []), start=1):
                    f, _ = Fonctionnalite.objects.get_or_create(
                        texte=texte, defaults={'ordre': idx}
                    )
                    offre.fonctionnalites_choisies.add(f)

        # ── Chiffres clés ─────────────────────────────────────────────────
        for c in CHIFFRES:
            try:
                page = PageStatique.objects.get(slug=c['page_slug'])
            except PageStatique.DoesNotExist:
                continue
            _, created = ChiffreCle.objects.get_or_create(
                page=page, chiffre=c['chiffre'],
                defaults={'label': c['label'], 'ordre': c['ordre']},
            )
            if created:
                chiffres_ok += 1

        self.stdout.write(self.style.SUCCESS(
            f'{pages_ok} page(s), {sections_ok} section(s), '
            f'{offres_ok} offre(s), {chiffres_ok} chiffre(s) créés.'
        ))
