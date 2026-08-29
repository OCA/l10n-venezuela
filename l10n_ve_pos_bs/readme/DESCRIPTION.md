Odoo requires every bank payment method in a Point of Sale to use the POS
currency. Venezuelan businesses operating a foreign-currency POS can therefore
record the accounting value of a bolivar payment, but not the exact VES amount
shown by the bank.

This addon captures the exact VES amount, exchange rate, and optional transaction
reference on each POS payment. At session closing, it denominates only the bank
liquidity line in VES while preserving the company-currency balance calculated by
Odoo. The resulting line can be reconciled one-to-one with a VES bank statement.

Both aggregated and customer-split bank payment methods are supported. The addon
does not connect to a bank, payment processor, or fiscal printer.
