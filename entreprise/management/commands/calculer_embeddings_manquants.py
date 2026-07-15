"""Calcule les embeddings ATS manquants (candidats + offres).

Rattrapage périodique : couvre les cas où le calcul en arrière-plan déclenché
depuis une vue (`recrutement.background.lancer_en_arriere_plan`) n'aurait pas
abouti (thread interrompu, redémarrage de l'app...). Pas de worker persistant
possible sous Passenger/O2switch — cette commande est donc destinée à un
déclenchement périodique via cron (cPanel > Tâches Cron), avec `flock` pour
éviter les exécutions concourantes si un run dépasse l'intervalle :

    */15 * * * * flock -n /tmp/rp_embeddings.lock \\
        /home/<user>/virtualenv/.../bin/python /home/<user>/recrutement/manage.py \\
        calculer_embeddings_manquants

Usage :
    python manage.py calculer_embeddings_manquants
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Calcule les embeddings ATS manquants pour les candidats et offres."

    def handle(self, *args, **options):
        from entreprise.tasks import calculer_tous_embeddings_manquants

        nb_candidats, nb_offres = calculer_tous_embeddings_manquants()

        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {nb_candidats} candidat(s) + {nb_offres} offre(s) traité(s)."
        ))
