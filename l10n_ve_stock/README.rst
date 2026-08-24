=====================================
Venezuela SENIAT - Stock/Inventory
=====================================

Venezuelan stock localization for SENIAT dispatch guides, delivery notes,
and fiscal locks on products that already have completed stock moves.

The module issues dispatch guides with control numbers, transfer reasons,
and portal PDF downloads. It can split deliveries by journal line limits
and show uninvoiced dispatch guides on the invoice dashboard.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

Venezuelan companies must print dispatch guides with SENIAT control
numbers when goods leave the warehouse. Deliveries without a linked sale
order also need a transfer reason, a pricelist, and a documented total.

This module keeps that fiscal information on the picking and blocks
unsafe changes on products that already moved in stock.

Configuration
=============

1. Open **Inventory → Configuration → Settings**.
2. Enable **Dispatch guides** for the Venezuelan company.
3. Set the SENIAT booklet section on each warehouse that must assign
   control numbers.
4. Create transfer reasons under **Inventory → Configuration → Transfer
   reasons**.

Usage
=====

To print a dispatch guide:

1. Open an outgoing picking for a Venezuelan company.
2. Fill the transfer reason when the delivery has no sale order.
3. Validate the picking and confirm the control number if asked.
4. Print the dispatch guide from the picking or the customer portal.

Product sales taxes and internal references cannot be changed after the
product has completed stock moves, unless the user belongs to the SENIAT
override group.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_stock%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical
issues.

Credits
=======

Authors
-------

* andyengit
* Anderson Armeya

Contributors
------------

* andyengit
* Anderson Armeya

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_stock>`_ project
on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
