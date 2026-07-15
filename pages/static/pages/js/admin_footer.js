(function () {
    'use strict';

    var VISIBILITES = {
        CANDIDAT: [
            ['TOUJOURS', 'Toujours'],
            ['CANDIDAT_CONNECTE', 'Candidat connecté'],
            ['CANDIDAT_NON_CONNECTE', 'Candidat non connecté']
        ],
        ENTREPRISE: [
            ['TOUJOURS', 'Toujours'],
            ['ENTREPRISE', 'Entreprise connectée'],
            ['RECRUTEUR', 'Recruteur connecté'],
            ['ENTREPRISE_OU_RECRUTEUR', 'Entreprise ou Recruteur']
        ],
        LES_DEUX: [
            ['TOUJOURS', 'Toujours'],
            ['CANDIDAT_CONNECTE', 'Candidat connecté'],
            ['CANDIDAT_NON_CONNECTE', 'Candidat non connecté'],
            ['ENTREPRISE', 'Entreprise connectée'],
            ['RECRUTEUR', 'Recruteur connecté'],
            ['ENTREPRISE_OU_RECRUTEUR', 'Entreprise ou Recruteur']
        ]
    };

    function updateVisibilite(groupeSelect, visibiliteSelect) {
        var sel = groupeSelect.options[groupeSelect.selectedIndex];
        var cible = sel ? sel.getAttribute('data-cible') : null;
        var currentVal = visibiliteSelect.value;
        var choices = (cible && VISIBILITES[cible]) ? VISIBILITES[cible] : VISIBILITES.LES_DEUX;

        visibiliteSelect.innerHTML = '';
        choices.forEach(function (c) {
            var opt = document.createElement('option');
            opt.value = c[0];
            opt.textContent = c[1];
            if (c[0] === currentVal) opt.selected = true;
            visibiliteSelect.appendChild(opt);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var groupeSelect = document.getElementById('id_groupe');
        var visibiliteSelect = document.getElementById('id_visibilite');
        if (!groupeSelect || !visibiliteSelect) return;

        updateVisibilite(groupeSelect, visibiliteSelect);
        groupeSelect.addEventListener('change', function () {
            updateVisibilite(groupeSelect, visibiliteSelect);
        });
    });
})();
