===============================
Venezuela - IGTF Point of Sale
===============================

Calculates IGTF on POS payments using currencies configured in
``l10n_ve_igtf`` and the payment method currency.

**Table of contents**

.. contents::
   :local:

Description
===========

Applies Venezuela IGTF on the Point of Sale when the company has the
feature enabled and the payment method currency is among the IGTF
currencies.

Usage
=====

* Enable IGTF and configure the IGTF account and currencies in Settings.
* Open a POS session and invoice an order paid with an IGTF currency.
* The payment screen shows the IGTF amount; accounting entries split IGTF
  when the payment is posted.

Credits
=======

Authors
-------

* andyengit

Contributors
------------

* andyengit
