This addon generates the Venezuelan VAT sales and purchase books required by
articles 70 through 78 of the VAT Law Regulations. XLSX amounts are expressed in
VES using the exchange rate applicable on each document date.

It provides:

* Detailed sales and purchase books with 8%, 16%, and combined 31% VAT columns.
* Sales separation by the emission medium captured on each posted document.
* Daily POS summaries for non-taxpayer sales and document-level contingency sales.
* Authorized fiscal-paper batches, range validation, duplicate detection, and
  low-paper warnings.
* Optional VAT withholding columns when a compatible integration is installed.

The addon relies on `l10n_ve_fiscal_document` for control numbers, emission
media, posted-document snapshots, and fiscal-data immutability.
