==========================================
Venezuelan Reports - Stock Inventory Book
==========================================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fl10n--venezuela-lightgray.png?logo=github
    :target: https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_reports_stock
    :alt: OCA/l10n-venezuela
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/l10n-venezuela-18-0/l10n-venezuela-18-0-l10n_ve_reports_stock
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/l10n-venezuela&target_branch=18.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

Venezuelan inventory book report for SENIAT, based on the OCA account
report engine.

This module adds the Libro de Inventario with opening and closing
quantities and values, plus inbound, outbound, withdrawal and
self-consumption movements, as required by the ISLR regulation
(Art. 177).

Warehouse locations can be configured for withdrawals and
self-consumption so those movements are classified separately from
regular stock issues.

**Table of contents**

.. contents::
   :local:

Usage
=====

To generate the inventory book:

#. Go to **Inventory > Reporting > Libro de Inventario**, or to
   **SENIAT > Reports > Libro de Inventario**.
#. Select the date range and, if needed, filter one or more warehouses.
#. Optionally hide products whose quantities are zero in the period.
#. Review opening inventory, entries, issues, withdrawals,
   self-consumption and closing inventory, with quantities and values.
#. Export the report to PDF or XLSX using the standard report actions.

To classify withdrawals and self-consumption:

#. Go to **Inventory > Configuration > Warehouses**.
#. Open a warehouse and set the SENIAT locations for withdrawals and
   self-consumption.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us to smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_reports_stock%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical
issues.

Credits
=======

Authors
-------

* andyengit

Contributors
------------

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

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_reports_stock>`_
project on GitHub.

You are welcome to contribute. To learn how see
https://odoo-community.org/page/Contribute.
