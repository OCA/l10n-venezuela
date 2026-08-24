=======================
Venezuela EDI Queue Job
=======================

Queues Venezuelan digital invoicing sends through ``queue_job`` instead
of running them in the user request.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

When many invoices, dispatch guides or withholding vouchers are sent at
once, a synchronous EDI call can time out. This module enqueues each
send so the worker processes it in the background.

Configuration
=============

1. Install ``l10n_ve_edi`` and ``queue_job``.
2. Install ``l10n_ve_edi_queue_job``.
3. Configure a ``queue_job`` worker for channel ``root``.

Usage
=====

1. Send a customer invoice, dispatch guide or withholding voucher from
   the EDI tab as usual.
2. The chatter records that the digital invoicing request was queued.
3. The worker sends the document and updates the EDI state.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_edi_queue_job%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

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

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_edi_queue_job>`_
project on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
