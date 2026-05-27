"""
hrms.setup package

Python resolves ``hrms.setup`` to this package (hrms/setup/) rather than to
the sibling hrms/setup.py module, because packages take precedence over
same-named modules.

All installation/migration helpers now live in hrms/setup/_install.py.
Everything is re-exported here so that all existing import paths continue to
work without changes:

  • hooks.py dotted paths  (hrms.setup.after_app_install, etc.)
  • direct imports         (from hrms.setup import after_install, ...)
"""

from ._install import *  # noqa: F401, F403
