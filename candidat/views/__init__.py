"""candidat.views — split into sub-modules for maintainability.

All public names are re-exported here so that ``from . import views``
followed by ``views.accueil``, ``views.connexion``, etc. continues
to work unchanged in ``candidat/urls.py``.
"""
from .public import *          # noqa: F401,F403
from .auth import *            # noqa: F401,F403
from .profil import *          # noqa: F401,F403
from .candidatures import *    # noqa: F401,F403
from .notifications import *   # noqa: F401,F403
from .messagerie import *      # noqa: F401,F403
from .cv_ai import *           # noqa: F401,F403
