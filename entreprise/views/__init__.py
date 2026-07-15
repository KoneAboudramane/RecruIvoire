"""entreprise.views — split into sub-modules for maintainability.

All public names are re-exported here so that ``from . import views``
followed by ``views.connexion``, ``views.offre_creer``, etc. continues
to work unchanged in ``entreprise/urls.py``.
"""
from .public import *          # noqa: F401,F403
from .auth import *            # noqa: F401,F403
from .profil import *          # noqa: F401,F403
from .offres import *          # noqa: F401,F403
from .candidatures import *    # noqa: F401,F403
from .entretiens import *      # noqa: F401,F403
from .membres import *         # noqa: F401,F403
from .notifications import *   # noqa: F401,F403
from .messagerie import *      # noqa: F401,F403
from .ia import *              # noqa: F401,F403
from .admin_panel import *     # noqa: F401,F403
