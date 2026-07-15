import json
from django import template
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from datetime import timedelta

register = template.Library()


@register.simple_tag
def nb_temoignages_en_attente():
    """Retourne le nombre de témoignages candidats en attente de validation."""
    try:
        from candidat.models import Temoignage
        return Temoignage.objects.filter(statut=Temoignage.STATUT_EN_ATTENTE).count()
    except Exception:
        return 0


@register.simple_tag
def nb_temoignages_entreprise_en_attente():
    """Retourne le nombre de témoignages clients entreprise en attente de validation."""
    try:
        from entreprise.models import TemoignageEntreprise
        return TemoignageEntreprise.objects.filter(statut=TemoignageEntreprise.STATUT_EN_ATTENTE).count()
    except Exception:
        return 0


@register.simple_tag
def get_admin_stats():
    """Stats globales pour le dashboard admin. Ne lève jamais d'exception."""
    zeros = {
        'total_candidats': 0, 'candidats_7j': 0, 'candidats_actifs': 0,
        'total_entreprises': 0, 'entreprises_verifiees': 0, 'entreprises_7j': 0,
        'total_offres': 0, 'offres_actives': 0, 'offres_7j': 0,
        'demandes_attente': 0, 'demandes_approuvees': 0,
        'total_abonnes': 0,
        'visiteurs_aujourd_hui': 0, 'visiteurs_7j': 0,
    }
    try:
        from django.db.models import Sum
        from candidat.models import Candidat, AbonneNewsletter, VisiteurJournalier
        from entreprise.models import Entreprise, OffreEmploi, DemandeVerification

        aujourd_hui = timezone.now().date()
        il_y_a_7j   = aujourd_hui - timedelta(days=7)

        total_candidats       = Candidat.objects.count()
        candidats_7j          = Candidat.objects.filter(date_joined__date__gte=il_y_a_7j).count()
        candidats_actifs      = total_candidats
        total_entreprises     = Entreprise.objects.count()
        entreprises_verifiees = Entreprise.objects.filter(statutVerification='VERIFIE').count()
        entreprises_7j        = Entreprise.objects.filter(dateCreationCompte__date__gte=il_y_a_7j).count()
        total_offres          = OffreEmploi.objects.count()
        offres_actives        = OffreEmploi.objects.filter(statutOffre='PUBLIEE').count()
        offres_7j             = OffreEmploi.objects.filter(
            datePublication__isnull=False,
            datePublication__date__gte=il_y_a_7j,
        ).count()
        demandes_attente      = DemandeVerification.objects.filter(statut='EN_ATTENTE').count()
        demandes_approuvees   = DemandeVerification.objects.filter(statut='APPROUVEE').count()
        total_abonnes         = AbonneNewsletter.objects.filter(actif=True).count()
        visiteurs_aujourd_hui = (
            VisiteurJournalier.objects.filter(date=aujourd_hui)
            .aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        )
        visiteurs_7j = (
            VisiteurJournalier.objects.filter(date__gte=il_y_a_7j)
            .aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        )

        return {
            'total_candidats':       total_candidats,
            'candidats_7j':          candidats_7j,
            'candidats_actifs':      candidats_actifs,
            'total_entreprises':     total_entreprises,
            'entreprises_verifiees': entreprises_verifiees,
            'entreprises_7j':        entreprises_7j,
            'total_offres':          total_offres,
            'offres_actives':        offres_actives,
            'offres_7j':             offres_7j,
            'demandes_attente':      demandes_attente,
            'demandes_approuvees':   demandes_approuvees,
            'total_abonnes':         total_abonnes,
            'visiteurs_aujourd_hui': visiteurs_aujourd_hui,
            'visiteurs_7j':          visiteurs_7j,
        }
    except Exception:
        return zeros


@register.simple_tag
def get_chart_data():
    """Retourne les données JSON pour les graphiques du dashboard admin."""
    MOIS_FR = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
               'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

    empty = {
        'labels': [], 'visiteurs': [], 'candidats_par_jour': [],
        'entreprises_par_jour': [],
        'labels_offres': [], 'valeurs_offres': [], 'couleurs_offres': [],
        'verifiees': 0, 'non_verifiees': 0,
        'mois_labels': [], 'mois_candidats': [], 'mois_entreprises': [], 'mois_offres': [],
        'labels_mob': [], 'data_mob': [],
        'labels_contrat_cand': [], 'data_contrat_cand': [],
        'candidats_30j': 0, 'entreprises_30j': 0, 'offres_30j': 0,
        'offres_vues': 0, 'offres_candidatures': 0,
        'visiteurs_30j': 0, 'visiteurs_total': 0,
    }
    try:
        from django.db.models import Count, Sum
        from candidat.models import Candidat, VisiteurJournalier
        from entreprise.models import Entreprise, OffreEmploi

        aujourd_hui = timezone.now().date()

        # ── 14 derniers jours ─────────────────────────────────────────
        dates  = [aujourd_hui - timedelta(days=i) for i in range(13, -1, -1)]
        labels = [d.strftime('%d/%m') for d in dates]

        vj_map = {
            v['date']: v['nb_visiteurs']
            for v in VisiteurJournalier.objects.filter(date__gte=dates[0]).values('date', 'nb_visiteurs')
        }
        visiteurs = [vj_map.get(d, 0) for d in dates]

        cand_map = {
            r['date_joined__date']: r['n']
            for r in Candidat.objects
                .filter(date_joined__date__gte=dates[0])
                .values('date_joined__date').annotate(n=Count('id'))
        }
        candidats_par_jour = [cand_map.get(d, 0) for d in dates]

        ent_map = {
            r['dateCreationCompte__date']: r['n']
            for r in Entreprise.objects
                .filter(dateCreationCompte__date__gte=dates[0])
                .values('dateCreationCompte__date').annotate(n=Count('id'))
        }
        entreprises_par_jour = [ent_map.get(d, 0) for d in dates]

        # ── Répartition offres par statut (donut) ─────────────────────
        TRAD = {'BROUILLON': 'Brouillon', 'PUBLIEE': 'Publiée',
                'EXPIREE': 'Expirée', 'POURVUE': 'Pourvue', 'FERMEE': 'Fermée'}
        COULEURS_OFFRES = {
            'PUBLIEE': '#009A44', 'BROUILLON': '#94a3b8',
            'EXPIREE': '#F77F00', 'POURVUE': '#2563EB', 'FERMEE': '#ef4444',
        }
        labels_offres, valeurs_offres, couleurs_offres = [], [], []
        for row in OffreEmploi.objects.values('statutOffre').annotate(n=Count('id')).order_by('statutOffre'):
            labels_offres.append(TRAD.get(row['statutOffre'], row['statutOffre']))
            valeurs_offres.append(row['n'])
            couleurs_offres.append(COULEURS_OFFRES.get(row['statutOffre'], '#94a3b8'))

        # ── Entreprises vérifiées vs non (donut) ──────────────────────
        verifiees     = Entreprise.objects.filter(statutVerification='VERIFIE').count()
        non_verifiees = Entreprise.objects.exclude(statutVerification='VERIFIE').count()

        # ── 6 derniers mois (barres) ───────────────────────────────────
        mois_labels = []
        mois_seq    = []
        y, m = aujourd_hui.year, aujourd_hui.month
        seq = []
        for _ in range(6):
            seq.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        for y2, m2 in reversed(seq):
            is_current = (y2 == aujourd_hui.year and m2 == aujourd_hui.month)
            jour = aujourd_hui.day if is_current else 1
            mois_labels.append(f"{jour} {MOIS_FR[m2]}")
            mois_seq.append((y2, m2))
        depuis_6m = aujourd_hui.replace(day=1)
        if len(mois_seq) > 0:
            y0, m0 = mois_seq[0]
            import datetime as _dt
            depuis_6m = _dt.date(y0, m0, 1)

        def _par_mois(qs, yf, mf):
            mp = {(r[yf], r[mf]): r['n'] for r in qs}
            return [mp.get(k, 0) for k in mois_seq]

        mois_candidats = _par_mois(
            Candidat.objects.filter(date_joined__date__gte=depuis_6m)
                .values('date_joined__year', 'date_joined__month').annotate(n=Count('id')),
            'date_joined__year', 'date_joined__month',
        )
        mois_entreprises = _par_mois(
            Entreprise.objects.filter(dateCreationCompte__date__gte=depuis_6m)
                .values('dateCreationCompte__year', 'dateCreationCompte__month').annotate(n=Count('id')),
            'dateCreationCompte__year', 'dateCreationCompte__month',
        )
        mois_offres = _par_mois(
            OffreEmploi.objects
                .filter(datePublication__isnull=False, datePublication__date__gte=depuis_6m)
                .values('datePublication__year', 'datePublication__month').annotate(n=Count('id')),
            'datePublication__year', 'datePublication__month',
        )

        il_y_a_30j = aujourd_hui - timedelta(days=30)

        # ── Mobilité candidats ────────────────────────────────────────
        from candidat.models import Mobilite
        mob_fk = {
            r['typeMobilite__libelle']: r['n']
            for r in Candidat.objects
                .filter(typeMobilite__isnull=False)
                .values('typeMobilite__libelle')
                .annotate(n=Count('id'))
        }
        for r in (Candidat.objects
                  .filter(typeMobilite__isnull=True)
                  .exclude(mobilite='')
                  .values('mobilite').annotate(n=Count('id'))):
            label = dict(Mobilite.choices).get(r['mobilite'], r['mobilite']) or '—'
            mob_fk[label] = mob_fk.get(label, 0) + r['n']
        mob_sorted = sorted(mob_fk.items(), key=lambda x: -x[1])
        labels_mob = [k for k, v in mob_sorted if v > 0]
        data_mob   = [v for k, v in mob_sorted if v > 0]

        # ── Contrats recherchés ───────────────────────────────────────
        from referentiel.models import Contrat as ContratRef
        contrat_qs = list(
            ContratRef.objects
            .filter(candidats_recherchant__isnull=False)
            .annotate(n=Count('candidats_recherchant'))
            .order_by('-n').values('libelle', 'n')
        )
        labels_contrat_cand = [r['libelle'] for r in contrat_qs if r['n'] > 0]
        data_contrat_cand   = [r['n']       for r in contrat_qs if r['n'] > 0]

        # ── KPIs supplémentaires ──────────────────────────────────────
        from django.db.models import Sum
        candidats_30j      = Candidat.objects.filter(date_joined__date__gte=il_y_a_30j).count()
        entreprises_30j    = Entreprise.objects.filter(dateCreationCompte__date__gte=il_y_a_30j).count()
        offres_30j         = OffreEmploi.objects.filter(datePublication__isnull=False, datePublication__date__gte=il_y_a_30j).count()
        offres_vues        = OffreEmploi.objects.aggregate(t=Sum('nbVues'))['t'] or 0
        offres_candidatures= OffreEmploi.objects.aggregate(t=Sum('nbCandidatures'))['t'] or 0
        from candidat.models import VisiteurJournalier as VJ
        visiteurs_30j  = VJ.objects.filter(date__gte=il_y_a_30j).aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        visiteurs_total= VJ.objects.aggregate(t=Sum('nb_visiteurs'))['t'] or 0

        data = {
            'labels':               labels,
            'visiteurs':            visiteurs,
            'candidats_par_jour':   candidats_par_jour,
            'entreprises_par_jour': entreprises_par_jour,
            'labels_offres':        labels_offres,
            'valeurs_offres':       valeurs_offres,
            'couleurs_offres':      couleurs_offres,
            'verifiees':            verifiees,
            'non_verifiees':        non_verifiees,
            'mois_labels':          mois_labels,
            'mois_candidats':       mois_candidats,
            'mois_entreprises':     mois_entreprises,
            'mois_offres':          mois_offres,
            'labels_mob':           labels_mob,
            'data_mob':             data_mob,
            'labels_contrat_cand':  labels_contrat_cand,
            'data_contrat_cand':    data_contrat_cand,
            'candidats_30j':        candidats_30j,
            'entreprises_30j':      entreprises_30j,
            'offres_30j':           offres_30j,
            'offres_vues':          offres_vues,
            'offres_candidatures':  offres_candidatures,
            'visiteurs_30j':        visiteurs_30j,
            'visiteurs_total':      visiteurs_total,
        }
        return mark_safe(json.dumps(data, default=str))

    except Exception:
        return mark_safe(json.dumps(empty, default=str))
