===============================
Venezuela EDI Digital Invoicing
===============================

Base module for Venezuelan digital invoicing. It tracks send state,
validates parties, builds the payload and dispatches customer invoices,
dispatch guides and withholding vouchers through a provider connector.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

Venezuelan companies that issue documents through a digital printer or
EDI connector need a shared flow: validate RIF data, queue the payload
and record the provider response. Provider-specific modules inherit this
base instead of duplicating the send lifecycle.

Configuration
=============

1. Install ``l10n_ve_edi`` and the connector for your provider
   (for example ``l10n_ve_edi_tfhka``).
2. On each sales journal used for digital emission, set the emission
   medium to digital and choose the EDI provider.
3. On withholding journals that must be sent digitally, set the same
   provider when the connector requires it.

Usage
=====

Customer invoices
-----------------

1. Confirm a customer invoice or credit note on a digital journal.
2. Open the EDI tab and send the document, or retry if the send failed.
3. When IGTF accrual applies on post, the module can enqueue the send
   automatically.

Dispatch guides
---------------

1. Validate an outgoing picking that requires a SENIAT dispatch guide
   and whose sales journal uses digital emission.
2. Send the guide from the EDI tab.
3. Print is blocked until the EDI state is sent.

Withholding vouchers
--------------------

1. Emit an IVA or ISLR supplier withholding.
2. Send it from the EDI tab after the voucher has a number and the
   related vendor bills have fiscal control and invoice numbers.

The accounting dashboard shows unsent invoices, dispatch guides and
withholding vouchers for Venezuelan companies.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_edi%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

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

.. |maintainer-andyengit| image:: https://github.com/andyengit.png?size=40px
   :target: https://github.com/andyengit
   :alt: andyengit

Current `maintainer <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-andyengit|

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_edi>`_ project
on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
