On a payment or in the **Register Payment** wizard, enable **Apply IGTF** only
after confirming that the transaction is subject to the tax. Review the rate
and calculated amount before posting.

The option is only offered, and only accepted on save or import, when the
payment:

- is in a foreign currency or cryptoasset currency. Payments in bolivars (ISO
  codes VES, VED and the former VEF) never carry IGTF, whatever the company
  currency is.
- settles invoices or bills, which is the case for payments created from the
  **Register Payment** wizard. Advances registered as standalone payments do
  not carry IGTF.

The selection is stored on the payment: correcting the amount, date or journal
of a draft payment never re-enables IGTF on a payment left unchecked as exempt.

For an outgoing payment, Odoo debits the configured IGTF expense account and
increases the payment liquidity credit. For an incoming payment, Odoo credits
the perception liability account and increases the payment liquidity debit.

Odoo 19 cannot combine native withholding lines and payment-difference
write-offs in one payment. When applying IGTF, keep any payment difference open
and record the difference separately.
