This addon connects the Odoo 19 Point of Sale and customer invoice form to an
external local bridge controlling a Venezuelan fiscal machine.

It provides:

* POS fiscal invoices and credit notes, including affected-document references.
* Browser-side bridge calls with a 90-second timeout.
* Recovery after an ambiguous invoice timeout, using the order UUID, the last
  fiscal ticket total, and an explicit cashier confirmation when needed.
* Fiscal number, machine serial, local timestamp, document type, and Z report
  capture.
* Backend fiscal printing for posted customer invoices and credit notes.
* Safe propagation of the fiscal number to the control-number fields supplied
  by `l10n_ve_fiscal_document`.
* Optional POS payload enrichment when another installed addon exposes the
  `l10n_ve_is_spe`, `l10n_ve_igtf_pct`, and `l10n_ve_igtf_applies` fields. No
  IGTF addon is required.

The fiscal printer bridge is external software and is not distributed with
this addon. Odoo's server never connects directly to the fiscal machine.

Paper batches, free-form stationery, and manual contingency books are not part
of this core addon. Those workflows require paper-range ownership, duplicate
controls, dedicated journals, and fiscal-book reporting and belong in a
separate integration addon depending on the corresponding fiscal-books module.
