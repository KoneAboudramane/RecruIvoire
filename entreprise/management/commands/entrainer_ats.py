"""
Commande Django : entraîne le modèle ML de re-ranking ATS pour les profils
proposés au recruteur (cf. PropositionProfil).

Usage :
    python manage.py entrainer_ats              # entraîne avec les défauts
    python manage.py entrainer_ats --min 30     # seuil minimum d'exemples
    python manage.py entrainer_ats --dry-run    # rapport sans sauvegarde

Workflow :
  1. Charge toutes les `PropositionProfil` (offre, candidat, action).
  2. Convertit chaque action en label numérique :
       invite   → 100  (signal très positif : le recruteur a invité à postuler)
       contacte →  85  (positif : le recruteur a contacté)
       vu       →  60  (mildement positif : il a regardé le portfolio)
       propose  →  30  (neutre/négatif : proposé mais pas d'action)
       ignore   →  10  (négatif : profil masqué)
  3. Construit les features via `ats_ml.construire_features()`.
  4. Refuse l'entraînement si nb < --min (défaut 30).
  5. Split 80/20, entraîne GradientBoostingRegressor.
  6. Évalue (MAE, RMSE, R²).
  7. Persiste dans media/ml_models/ats_current.joblib + snapshot daté.

Le modèle prédira un score 0-100 directement (régression).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


# ── Mapping action → label numérique ─────────────────────────────────────────

LABEL_PAR_ACTION = {
    'invite':    100,
    'contacte':   85,
    'vu':         60,
    'propose':    30,
    'ignore':     10,
}


class Command(BaseCommand):
    help = "Entraîne le modèle ML de re-ranking ATS à partir des PropositionProfil."

    def add_arguments(self, parser):
        parser.add_argument(
            '--min', type=int, default=30,
            help="Nombre minimum de propositions étiquetées requis (défaut 30).",
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

    def handle(self, *args, **opts):
        # ── Dépendances ML ────────────────────────────────────────────────
        try:
            import numpy as np
            import joblib
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import (
                mean_absolute_error, mean_squared_error, r2_score,
            )
        except Exception as e:
            raise CommandError(
                "Dépendances manquantes : %s. "
                "Installez : pip install scikit-learn joblib numpy" % e
            )

        from entreprise.models import PropositionProfil
        from entreprise import ats_ml

        seuil_min = opts['min']
        dry_run   = opts['dry_run']
        test_size = opts['test_size']

        # ── 1. Chargement des propositions ────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 1/6 -- Chargement des propositions..."
        ))
        propositions = list(
            PropositionProfil.objects
            .select_related(
                'offre',
                'offre__entreprise',
                'offre__entreprise__secteurActiviteRef',
                'candidat',
                'candidat__informationPersonnelle',
            )
            .prefetch_related(
                'offre__typesCompetence',
                'candidat__competences__typeCompetence',
            )
        )
        self.stdout.write(f"  -> {len(propositions)} propositions trouvées.")

        if len(propositions) < seuil_min:
            self.stdout.write(self.style.ERROR(
                f"\nX Pas assez de données : {len(propositions)} propositions, "
                f"minimum requis {seuil_min}."
            ))
            self.stdout.write(self.style.WARNING(
                "\nLabels par action :\n"
                "  invite   -> 100   contacte -> 85   vu       -> 60\n"
                "  propose  -> 30    ignore   -> 10\n"
                f"\nLaissez les recruteurs interagir avec les profils proposés, "
                f"puis relancez la commande."
            ))
            return

        # ── 2. Construction des features (X, y) ───────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 2/6 -- Construction du dataset (X, y)..."
        ))
        X_list, y_list = [], []
        nb_erreurs = 0
        repartition = {a: 0 for a in LABEL_PAR_ACTION}

        for p in propositions:
            try:
                label = LABEL_PAR_ACTION.get(p.action)
                if label is None:
                    continue
                # On ré-utilise le score ATS persisté + cosinus reconstitué
                # (au pire score brut sans cosinus si non dispo)
                features = ats_ml.construire_features(
                    p.offre, p.candidat,
                    score_ats_brut=p.scoreATS,
                    cosinus=p.scoreATS / 100.0,  # approximation
                )
                v = ats_ml.vecteur(features)
                if v is None:
                    continue
                X_list.append(v)
                y_list.append(label)
                repartition[p.action] += 1
            except Exception as e:
                nb_erreurs += 1
                logger.warning("Skip proposition #%s : %s", p.id, e)

        if not X_list:
            raise CommandError("Aucune feature exploitable.")
        if nb_erreurs:
            self.stdout.write(self.style.WARNING(
                f"  ! {nb_erreurs} propositions ignorées (erreur d'extraction)."
            ))

        self.stdout.write("  -> Répartition des labels :")
        for action, nb in repartition.items():
            self.stdout.write(f"     {action:10s} : {nb}")

        X = np.vstack(X_list)
        y = np.array(y_list)
        self.stdout.write(
            f"  -> X shape = {X.shape}, y range = [{y.min():.0f} ; {y.max():.0f}]"
        )

        # ── 3. Split train / test ─────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 3/6 -- Split train / test..."
        ))
        n_test = max(2, min(int(len(X) * test_size), len(X) // 5))
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=n_test, random_state=42,
        )
        self.stdout.write(f"  -> train: {len(X_train)} | test: {len(X_test)}")

        # ── 4. Entraînement ───────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 4/6 -- Entraînement (GradientBoostingRegressor)..."
        ))
        modele = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.08,
            random_state=42,
        )
        modele.fit(X_train, y_train)
        self.stdout.write(self.style.SUCCESS("  -> OK"))

        # ── 5. Évaluation ─────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            "> 5/6 -- Évaluation sur jeu de test..."
        ))
        y_pred = modele.predict(X_test)
        mae  = mean_absolute_error(y_test, y_pred)
        rmse = mean_squared_error(y_test, y_pred) ** 0.5
        r2   = r2_score(y_test, y_pred)
        self.stdout.write(f"  MAE   : {mae:.2f}")
        self.stdout.write(f"  RMSE  : {rmse:.2f}")
        self.stdout.write(f"  R²    : {r2:.3f}")

        # Importance des features (dict complet pour metadata + top 5 affiché)
        importances = dict(zip(ats_ml.FEATURE_NAMES, modele.feature_importances_.tolist()))
        top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
        self.stdout.write("\n  Top 5 features :")
        for name, imp in top5:
            self.stdout.write(f"     {name:30s}  {imp*100:5.1f}%")

        # ── 6. Persistance ────────────────────────────────────────────────
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n[--dry-run] Modèle NON enregistré."
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n> 6/6 -- Sauvegarde du modèle..."
        ))
        out_dir = Path(settings.MEDIA_ROOT) / 'ml_models'
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            'modele': modele,
            'metadata': {
                'date_entrainement': datetime.now().isoformat(),
                'nb_exemples':       int(len(X)),
                'feature_names':     ats_ml.FEATURE_NAMES,
                'metriques': {
                    'mae': float(mae), 'rmse': float(rmse), 'r2': float(r2),
                },
                'importances':         importances,
                'repartition_actions': repartition,
                'version':             '1.0',
            },
        }
        path_current = out_dir / 'ats_current.joblib'
        joblib.dump(payload, path_current)

        # Snapshot daté
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot = out_dir / f'ats_{stamp}.joblib'
        joblib.dump(payload, snapshot)

        # Vider le cache pour que les workers chargent le nouveau modèle
        ats_ml.vider_cache()

        self.stdout.write(self.style.SUCCESS(
            f"  -> {path_current}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  -> Snapshot : {snapshot}"
        ))
        self.stdout.write(self.style.SUCCESS(
            "\nOK Modèle ATS entraîné et activé."
        ))
