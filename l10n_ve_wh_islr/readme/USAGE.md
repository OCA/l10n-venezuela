Register a payment from a posted vendor bill. When the vendor has an ISLR
concept, the payment wizard calculates the untaxed base, rate, subtrahend, and
withholding. The base and withholding remain editable before confirming the
payment.

Confirming the payment creates the withholding counterpart on the configured
liability account and issues one voucher for each affected invoice. A voucher
is also issued when the calculated withholding is zero, as required by the
SENIAT completeness rule.

Use Accounting > Vendors > Comprobantes ISLR to review and print vouchers. Use
Accounting > Vendors > XML Retenciones ISLR (SENIAT) to export a monthly
declaration.

If another installed addon provides `l10n_ve_control_number` on vendor bills,
the export uses that value. Otherwise, it exports `NA` and does not require that
optional addon.
