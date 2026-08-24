=========================
Venezuela SENIAT - Sale
=========================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fl10n--venezuela-lightgray.png?logo=github
    :target: https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_seniat_sale
    :alt: OCA/l10n-venezuela
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/l10n-venezuela-18-0/l10n-venezuela-18-0-l10n_ve_seniat_sale
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/l10n-venezuela&target_branch=18.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

SENIAT sales localization for Venezuela.

This module extends sale orders for Venezuelan companies: SENIAT notes,
invoice line limits, discount invoicing, journal checks on confirmation,
and native report / portal markup (no fiscal credit).

**Table of contents**

.. contents::
   :local:

Usage
=====

1. Install this module after ``sale`` and ``l10n_ve_seniat``.
2. Confirm Venezuelan sale orders with a sales journal and valid prices,
   quantities and a single tax per line.
3. Create customer invoices from the sale order. Free-form journals split
   invoices when the SENIAT book line limit is reached.
4. Printed quotations and the customer portal show the SENIAT note and the
   "no fiscal credit" notice for Venezuelan companies.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_seniat_sale%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
-------

* Anderson Armeya
* andyengit

Contributors
------------

* Anderson Armeya
* andyengit

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

Current maintainer:

* andyengit

This module is part of the `OCA/l10n-venezuela <https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_seniat_sale>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
