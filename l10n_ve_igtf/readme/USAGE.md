On a payment or in the **Register Payment** wizard, enable **Apply IGTF** only
after confirming that the transaction is subject to the tax. Review the rate
and calculated amount before posting.

For an outgoing payment, Odoo debits the configured IGTF expense account and
increases the payment liquidity credit. For an incoming payment, Odoo credits
the perception liability account and increases the payment liquidity debit.

Odoo 19 cannot combine native withholding lines and payment-difference
write-offs in one payment. When applying IGTF, keep any payment difference open
and record the difference separately.
