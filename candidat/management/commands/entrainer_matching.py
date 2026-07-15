"""
Commande Django : entraîne le modèle ML de matching candidat ↔ offre.

Usage :
    python manage.py entrainer_matching             # entraîne avec les valeurs par défaut
    python manage.py entrainer_matching --min 30    # seuil minimum d'exemples
    python manage.py entrainer_matching --dry-run   # n'enregistre pas le modèle

Workflow :
    1. Récupère les Candidature dont le statut.code est dans LABELS_PAR_STATUT.
    2. Pour chaque, construit X (features) + y (label numérique 0-100).
    3. Refuse l'entraînement si nb_exemples < --min (défaut: 30).
    4. Split train/test 80/20 (stratifié si possible).
    5. Entraîne `GradientBoostingRegressor` (sklearn, robuste, peu de tuning).
    6. Évalue (MAE, RMSE, R²) sur le test set.
    7. Persiste dans `media/ml_models/matching_current.joblib` + un snapshot daté.
    8. Affiche un rapport lisible.

Le modèle prédira un score 0-100 directement (régression).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Entraîne le modèle ML de matching à partir des Candidature à statut final."

    def add_arguments(self, parser):
        parser.add_argument(
            '--min', type=int, default=30,
            help="Nombre minimum de candidatures labellisées requis (défaut 30).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'enregistre pas le modèle, affiche seulement le rapport.",
        )
        parser.add_argument(
            '--test-size', type=float, default=0.2,
            help="Proportion du jeu de test (défaut 0.2).",
        )

    # ──────────────────────────────────────────────────────────────────────
    # Handle
    # ──────────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        # ── Vérification des dépendances ──────────────────────────────────
        try:
            import numpy as np
            import joblib
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        except Exception as e:
            raise CommandError(
                "Dépendances manquantes pour l'entraînement : %s. "
                "Installez avec : pip install scikit-learn joblib numpy" % e
            )

        from candidat.models import Candidature
        from candidat.matching import extraire_profil
        from candidat.ml_features import (
            construire_features, vecteur, FEATURE_NAMES, label_pour_statut,
        )
        from candidat import matching_semantic as ms

        seuil_min = opts['min']
        dry_run   = opts['dry_run']
        test_size = opts['test_size']

        # ── 1. Récupération des candidatures labellisables ────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 1/6 --Chargement des candidatures..."
        ))
        candidatures = list(
            Candidature.objects
            .select_related('candidat', 'offre', 'offre__entreprise',
                            'offre__entreprise__secteurActiviteRef', 'statut')
            .prefetch_related(
                'candidat__competences__typeCompetence',
                'candidat__languesParlees__langue',
                'offre__typesCompetence',
                'offre__langues',
            )
        )
        # Filtre : statut labellisable uniquement
        candidatures_lab = []
        for c in candidatures:
            if c.statut and label_pour_statut(c.statut.code) is not None:
                candidatures_lab.append(c)

        self.stdout.write(
            f"  ->{len(candidatures)} candidatures totales, "
            f"{len(candidatures_lab)} avec un statut exploitable."
        )

        if len(candidatures_lab) < seuil_min:
            self.stdout.write(self.style.ERROR(
                f"\nX Pas assez de données : {len(candidatures_lab)} candidatures "
                f"labellisables, minimum requis {seuil_min}."
            ))
            self.stdout.write(self.style.WARNING(
                "\nStatuts pris en compte pour l'apprentissage :\n"
                "  *EMBAUCHEE ->100   *ACCEPTEE ->85   *ENTRETIEN ->70\n"
                "  *TEST ->65          *PRESELECTIONNEE ->60   *VUE ->40\n"
                "  *REFUSEE ->10\n"
                "Statuts exclus : POSTULEE (pas de signal), RETIREE (retrait candidat)."
            ))
            return

        # ── 2. Construction des features ──────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 2/6 --Construction du dataset (X, y)..."
        ))
        X_list, y_list = [], []
        n_erreurs = 0
        semantic_dispo = ms.est_disponible()
        if semantic_dispo:
            self.stdout.write("  ->moteur sémantique disponible (embedding utilisé).")
        else:
            self.stdout.write(self.style.WARNING(
                "  ! sentence-transformers absent --feature 'similarite_semantique' = 0."
            ))

        for c in candidatures_lab:
            try:
                profil   = extraire_profil(c.candidat)
                emb_cand = ms.embedding_candidat(c.candidat) if semantic_dispo else None
                features, _ = construire_features(profil, c.offre, emb_cand)
                X_list.append(vecteur(features))
                y_list.append(label_pour_statut(c.statut.code))
            except Exception as e:
                n_erreurs += 1
                logger.warning("Skip candidature #%s : %s", c.id, e)

        if not X_list:
            raise CommandError(
                "Aucune feature exploitable n'a pu être construite."
            )
        if n_erreurs:
            self.stdout.write(self.style.WARNING(
                f"  ! {n_erreurs} candidatures ignorées (erreur d'extraction)."
            ))

        X = np.vstack(X_list)
        y = np.array(y_list)
        self.stdout.write(
            f"  ->X shape = {X.shape}, y shape = {y.shape}, "
            f"y range = [{y.min():.0f} ; {y.max():.0f}]"
        )

        # ── 3. Split train / test ─────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 3/6 --Split train / test..."
        ))
        # Si très peu d'exemples, on garde un test minuscule (mais non vide).
        n_test_min = max(2, int(len(X) * test_size))
        n_test     = min(n_test_min, max(2, len(X) // 5))
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=n_test, random_state=42,
        )
        self.stdout.write(f"  ->train: {len(X_train)} | test: {len(X_test)}")

        # ── 4. Entraînement ───────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 4/6 --Entraînement (GradientBoostingRegressor)..."
        ))
        modele = GradientBoostingRegressor(
            n_estimators   = 200,
            max_depth      = 4,
            learning_rate  = 0.05,
            random_state   = 42,
        )
        modele.fit(X_train, y_train)
        self.stdout.write("  ->Modèle entraîné.")

        # ── 5. Évaluation ─────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 5/6 --Évaluation sur le jeu de test..."
        ))
        y_pred = modele.predict(X_test)
        mae    = float(mean_absolute_error(y_test, y_pred))
        rmse   = float(mean_squared_error(y_test, y_pred) ** 0.5)
        r2     = float(r2_score(y_test, y_pred)) if len(set(y_test)) > 1 else 0.0
        importances = dict(zip(FEATURE_NAMES, modele.feature_importances_.tolist()))

        self.stdout.write(f"  *MAE  = {mae:.2f}   (erreur absolue moyenne, en points 0-100)")
        self.stdout.write(f"  *RMSE = {rmse:.2f}   (racine de l'erreur quadratique)")
        self.stdout.write(f"  *R²   = {r2:.3f}    (qualité du fit, 1.0 = parfait)")
        self.stdout.write("\n  Importance des features (top 5) :")
        top = sorted(importances.items(), key=lambda x: -x[1])[:5]
        for name, imp in top:
            self.stdout.write(f"    {imp:>6.3f}   {name}")

        # ── 6. Persistence ────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 6/6 --Persistance du modèle..."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "  ->DRY-RUN : modèle NON sauvegardé."
            ))
            return

        target_dir = Path(settings.MEDIA_ROOT) / 'ml_models'
        target_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        payload = {
            'modele': modele,
            'metadata': {
                'date_entrainement':  datetime.now().isoformat(),
                'nb_exemples':        int(len(X)),
                'nb_train':           int(len(X_train)),
                'nb_test':            int(len(X_test)),
                'feature_names':      FEATURE_NAMES,
                'metriques':          {'mae': mae, 'rmse': rmse, 'r2': r2},
                'importances':        importances,
                'version':            '1.0',
                'semantic_disponible': semantic_dispo,
            },
        }

        # Snapshot daté (historique)
        snap_path = target_dir / f'matching_{ts}.joblib'
        joblib.dump(payload, snap_path)
        # Pointeur courant
        current_path = target_dir / 'matching_current.joblib'
        joblib.dump(payload, current_path)

        # Invalide le cache de matching_ml pour que le prochain appel le recharge
        from candidat import matching_ml
        matching_ml.vider_cache()

        self.stdout.write(self.style.SUCCESS(
            f"\nOK Modèle persisté :\n"
            f"  *courant  : {current_path}\n"
            f"  *snapshot : {snap_path}"
        ))
        self.stdout.write(self.style.SUCCESS(
            "  Il sera utilisé automatiquement par le moteur de matching."
        ))
