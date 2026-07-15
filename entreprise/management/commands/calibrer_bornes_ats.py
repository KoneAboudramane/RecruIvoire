"""Calibre les bornes ATS à partir de la distribution réelle des cosinus."""
import json
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Calibre les bornes de normalisation ATS (percentiles 5/95 des cosinus réels)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les bornes sans les sauvegarder')
        parser.add_argument('--p-basse', type=int, default=5,
                            help='Percentile pour la borne basse (défaut: 5)')
        parser.add_argument('--p-haute', type=int, default=95,
                            help='Percentile pour la borne haute (défaut: 95)')

    def handle(self, *args, **options):
        from candidat.models import Candidat
        from entreprise.models import OffreEmploi
        from entreprise.ats_predict import _cosinus

        candidats = list(
            Candidat.objects.exclude(embedding__isnull=True)
            .values_list('embedding', flat=True)
        )
        offres = list(
            OffreEmploi.objects.exclude(embedding__isnull=True)
            .values_list('embedding', flat=True)
        )

        if len(candidats) < 5 or len(offres) < 5:
            self.stderr.write(
                f'Pas assez de données : {len(candidats)} candidats, '
                f'{len(offres)} offres avec embeddings. Minimum 5 de chaque.'
            )
            return

        scores = []
        for emb_c in candidats:
            for emb_o in offres:
                scores.append(_cosinus(emb_c, emb_o))

        scores = np.array(scores)
        borne_basse = round(float(np.percentile(scores, options['p_basse'])), 4)
        borne_haute = round(float(np.percentile(scores, options['p_haute'])), 4)

        self.stdout.write(f'Paires analysées : {len(scores)}')
        self.stdout.write(f'Cosinus min={scores.min():.4f}  max={scores.max():.4f}  '
                          f'mean={scores.mean():.4f}  std={scores.std():.4f}')
        self.stdout.write(f'Borne basse (P{options["p_basse"]}) : {borne_basse}')
        self.stdout.write(f'Borne haute (P{options["p_haute"]}) : {borne_haute}')

        if options['dry_run']:
            self.stdout.write('(dry-run — rien sauvegardé)')
            return

        out_dir = Path(settings.MEDIA_ROOT) / 'ml_models'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / 'bornes_ats.json'

        data = {
            'borne_basse': borne_basse,
            'borne_haute': borne_haute,
            'nb_paires': len(scores),
            'percentile_basse': options['p_basse'],
            'percentile_haute': options['p_haute'],
            'stats': {
                'min': round(float(scores.min()), 4),
                'max': round(float(scores.max()), 4),
                'mean': round(float(scores.mean()), 4),
                'std': round(float(scores.std()), 4),
            },
        }
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f'Bornes sauvegardées dans {out_file}'))

        from entreprise.ats_predict import _bornes_cache
        import entreprise.ats_predict as _mod
        _mod._bornes_cache = None
        self.stdout.write('Cache bornes invalidé — prochain appel rechargera.')
