"""Crée des candidatures réalistes : chaque candidat postule aux offres
qui correspondent le mieux à son profil (top N selon le score de matching).

Idempotent : si une candidature existe déjà (contrainte unique candidat+offre),
elle est laissée intacte.

Usage :
    python manage.py seed_candidatures
    python manage.py seed_candidatures --top 6 --seuil 50
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from candidat.models import Candidat, Candidature, CV
from candidat.matching import Matcher
from entreprise.models import OffreEmploi, StatutOffre


class Command(BaseCommand):
    help = "Génère des candidatures : top-N offres matchant le profil de chaque candidat."

    def add_arguments(self, parser):
        parser.add_argument('--top',   type=int, default=5,
                            help="Nombre d'offres à postuler par candidat (défaut: 5).")
        parser.add_argument('--seuil', type=int, default=45,
                            help="Score de matching minimum pour postuler (défaut: 45).")

    @transaction.atomic
    def handle(self, *args, **options):
        top   = options['top']
        seuil = options['seuil']

        # Offres publiées (les seules auxquelles on peut postuler)
        offres = list(
            OffreEmploi.objects
            .filter(statutOffre=StatutOffre.PUBLIEE)
            .select_related('entreprise')
        )
        if not offres:
            self.stdout.write(self.style.WARNING("Aucune offre publiée — rien à faire."))
            return

        candidats = Candidat.objects.all().order_by('id')
        total_creees = 0
        total_skip   = 0

        for c in candidats:
            # CV principal du candidat (si plusieurs, prend le plus récent)
            cv = CV.objects.filter(candidat=c).order_by('-id').first()

            matcher = Matcher(c)
            scores = matcher.scorer_plusieurs(offres)
            # Tri par score décroissant + filtre seuil
            scores = [r for r in scores if int(r.get('score') or 0) >= seuil]
            scores.sort(key=lambda r: r.get('score') or 0, reverse=True)
            cibles = scores[:top]

            if not cibles:
                self.stdout.write(
                    f"   - {c.prenom} {c.nom} : aucun match ≥ {seuil}% (ignoré)"
                )
                continue

            self.stdout.write(f"\n=== {c.prenom} {c.nom} (id={c.id}) ===")
            for r in cibles:
                offre = r['offre']
                score = int(r.get('score') or 0)

                # Idempotence : skip si déjà candidat à cette offre
                if Candidature.objects.filter(candidat=c, offre=offre).exists():
                    total_skip += 1
                    self.stdout.write(f"   = déjà postulé : {offre.titre} ({offre.entreprise.raisonSocial})")
                    continue

                cand = Candidature(
                    candidat=c,
                    offre=offre,
                    cvSauvegarde=cv,           # réutilise le CV du site si dispo
                )
                cand.save()
                cand.soumettre()               # statut POSTULEE + historique + compteur offre
                total_creees += 1
                self.stdout.write(
                    f"   + postulé : {offre.titre} chez {offre.entreprise.raisonSocial} "
                    f"(score {score}%)"
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {total_creees} candidature(s) créée(s), {total_skip} déjà existante(s)."
        ))
