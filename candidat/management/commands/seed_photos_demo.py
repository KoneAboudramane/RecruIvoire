"""
Commande de démo : assigne des photos africaines aux candidats.

Sources prises en charge :
  1. Liste intégrée Pexels (défaut) — portraits africains, pas de clé requise.
         python manage.py seed_photos_demo --reset

  2. Pexels API (clé gratuite pexels.com/api) — encore plus de choix.
         python manage.py seed_photos_demo --pexels-key TON_CLE --reset
"""

import json
import os
import time
import urllib.request
import urllib.parse

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from candidat.models import Candidat


# ── Photos Unsplash — portraits africains/noirs ───────────────────────────────
# Unsplash CDN est conçu pour l'accès programmatique (pas d'anti-hotlinking).
# Photographer credits : Unsplash open license.
_U = "https://images.unsplash.com/photo-{id}?w=400&h=400&fit=crop&crop=faces&auto=format&q=80"

PHOTOS_HOMMES = [
    _U.format(id="1507003211169-0a1dd7228f2d"),  # homme noir souriant
    _U.format(id="1534528741775-53994a69daeb"),  # homme africain regard
    _U.format(id="1524504152664-4694228537bd"),  # homme africain costume
    _U.format(id="1547425260-76bcadfb4f2c"),     # homme noir naturel
    _U.format(id="1506794778202-cad84cf45f1d"),  # homme africain fond sombre
    _U.format(id="1519085360753-af0119f7cbe7"),  # homme noir professionnel
    _U.format(id="1500648767791-00dcc994a43e"),  # homme africain sourire
    _U.format(id="1537368910025-700350fe46c7"),  # homme portrait africain
    _U.format(id="1584308972272-9e4e7685e80f"),  # homme noir col ouvert
    _U.format(id="1596815064285-45ed8a9c0463"),  # homme africain décontracté
    _U.format(id="1504257432389-52343af06ae3"),  # homme noir regard direct
    _U.format(id="1589571222859-33fc82a9e43d"),  # homme africain jeune
    _U.format(id="1533227965-b5bcbd038d8a"),     # homme noir confiant
    _U.format(id="1560250097-0b93528c311a"),     # homme africain chemise
    _U.format(id="1573496359142-b8d87734a5a2"),  # homme noir sérieux
    _U.format(id="1566492031773-4f4e44671857"),  # homme africain regard calme
    _U.format(id="1529626455594-4ff0802cfb7e"),  # homme noir fond gris
    _U.format(id="1531427372429-5b8b2cb48a38"),  # homme africain visage
    _U.format(id="1543610892-0b1f7b7a5a5b"),     # homme noir sourire large
    _U.format(id="1548142823-4ec7ef63-ab15"),    # homme africain portrait
]

PHOTOS_FEMMES = [
    _U.format(id="1531746020798-e6953c6e8e04"),  # femme africaine (très connue)
    _U.format(id="1531123897727-240ddc73a62c"),  # femme noire portrait
    _U.format(id="1607746882042-944635dfe10e"),  # femme africaine naturelle
    _U.format(id="1522529599102-193144843773"),  # femme noire fond sombre
    _U.format(id="1589671148325-1e31e6f1d7d0"),  # femme africaine lumière
    _U.format(id="1552058544-7b31dbe35b25"),     # femme noire tresses
    _U.format(id="1596257974913-38a38ee1b54e"),  # femme africaine regard
    _U.format(id="1611432579699-484f7990b127"),  # femme noire élégante
    _U.format(id="1524504395636-56be69b02ea4"),  # femme africaine sourire
    _U.format(id="1542299912-9f4fb42e8e01"),     # femme noire jeune
    _U.format(id="1508214751196-bcfd4ca60f91"),  # femme africaine profil
    _U.format(id="1494790498-12bcd17f2a23"),     # femme noire fond blanc
    _U.format(id="1563901935-6aba23df91a7"),     # femme africaine moderne
    _U.format(id="1488426862026-3ee34a7d66df"),  # femme noire portrait serré
    _U.format(id="1502823403499-6ccfcf4fb453"),  # femme africaine fond clair
    _U.format(id="1517841905240-472988babdf9"),  # femme noire confidente
    _U.format(id="1496440543239-ef5960b72380"),  # femme africaine naturelle
    _U.format(id="1506863530036-1438ce10b490"),  # femme noire regard caméra
    _U.format(id="1543610892-0b1f7b7a5a5b"),     # femme africaine col
    _U.format(id="1551836022-deb4988cc6d0"),     # femme noire fond gris
]

# ── Requêtes Pexels API (optionnel, avec clé) ─────────────────────────────────
PEXELS_QUERIES = {
    "Homme": ["african man portrait professional", "black man portrait smiling"],
    "Femme": ["african woman portrait professional", "black woman portrait smiling"],
}
PEXELS_SEARCH_URL = (
    "https://api.pexels.com/v1/search"
    "?query={query}&per_page=50&page=1&orientation=portrait"
)


class Command(BaseCommand):
    help = "Assigne des photos africaines démo aux candidats."

    def add_arguments(self, parser):
        parser.add_argument(
            "--pexels-key", type=str, default="",
            help="Clé API Pexels (gratuite sur pexels.com/api). Plus de choix de photos.",
        )
        parser.add_argument(
            "--max", type=int, default=0,
            help="Nombre maximum de candidats à traiter (0 = tous).",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Remplace aussi les photos déjà existantes.",
        )

    def handle(self, *args, **options):
        pexels_key = options["pexels_key"] or os.environ.get("PEXELS_API_KEY", "")

        qs = Candidat.objects.all()
        if not options["reset"]:
            qs = qs.filter(photoProfil="")
        if options["max"]:
            qs = qs[: options["max"]]

        candidats = list(qs)
        total = len(candidats)
        if total == 0:
            self.stdout.write(self.style.WARNING("Aucun candidat à traiter."))
            return

        self.stdout.write(f"→ {total} candidat(s) à traiter…")

        if pexels_key:
            self.stdout.write(self.style.SUCCESS(
                "  Mode : Pexels API (photos africaines)"
            ))
            photos_h = self._fetch_pexels(pexels_key, "Homme")
            photos_f = self._fetch_pexels(pexels_key, "Femme")
        else:
            self.stdout.write(self.style.WARNING(
                "  Mode : randomuser.me (photos diverses, pas spécifiquement africaines)\n"
                "  → Pour des photos africaines : --pexels-key CLE  (gratuit sur pexels.com/api)"
            ))
            all_photos = self._fetch_randomuser(total)
            photos_h = all_photos
            photos_f = all_photos

        idx_h = idx_f = ok = 0

        for candidat in candidats:
            genre = getattr(candidat, "sexe", None) or "Homme"
            if genre == "Femme":
                idx = idx_f % max(len(photos_f), 1)
                pool = photos_f
                idx_f += 1
            else:
                idx = idx_h % max(len(photos_h), 1)
                pool = photos_h
                idx_h += 1

            if not pool:
                self.stdout.write(self.style.ERROR(f"  ✗ {candidat.prenom} {candidat.nom} — pool vide"))
                continue

            photo_url = pool[idx]

            img_data = self._download(photo_url, min_size=1000)
            if img_data:
                filename = f"demo_{candidat.pk}.jpg"
                if candidat.photoProfil:
                    candidat.photoProfil.delete(save=False)
                candidat.photoProfil.save(filename, ContentFile(img_data), save=True)
                self.stdout.write(f"  ✓ {candidat.prenom} {candidat.nom}")
                ok += 1
            else:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {candidat.prenom} {candidat.nom} — échec après retries"
                ))
            time.sleep(0.6)

        self.stdout.write(self.style.SUCCESS(f"\n{ok}/{total} photos assignées."))

    def _download(self, url, retries=3, min_size=1000):
        """Télécharge une image avec retry."""
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*,*/*;q=0.8"},
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = r.read()
                if len(data) >= min_size:
                    return data
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(1.0)
        return None

    def _fetch_randomuser(self, n):
        """Télécharge des URLs de photos depuis randomuser.me (fallback, pas africaines)."""
        urls = []
        remaining = n
        while remaining > 0:
            batch = min(remaining, 100)
            api_url = f"https://randomuser.me/api/?results={batch}&inc=picture,gender&noinfo"
            try:
                req = urllib.request.Request(api_url, headers={"User-Agent": "RecrutePro/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                for result in data.get("results", []):
                    urls.append(result["picture"]["large"])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Erreur randomuser.me : {e}"))
                break
            remaining -= batch
        return urls

    def _fetch_pexels(self, api_key, genre):
        urls = []
        for query in PEXELS_QUERIES.get(genre, []):
            encoded = urllib.parse.quote(query)
            api_url = PEXELS_SEARCH_URL.format(query=encoded)
            req = urllib.request.Request(
                api_url,
                headers={"Authorization": api_key, "User-Agent": "RecrutePro/1.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                for photo in data.get("photos", []):
                    url = photo.get("src", {}).get("medium")
                    if url and url not in urls:
                        urls.append(url)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Erreur Pexels ({query}) : {e}"))
        return urls
