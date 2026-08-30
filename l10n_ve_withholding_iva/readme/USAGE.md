For VAT withheld from a vendor, post the vendor bill. When the
company is a special taxpayer on the bill accounting date, the vendor has a Tax
ID and a withholding percentage, the bill has VAT and it is not flagged as
excluded, posting issues the withholding voucher and its reconciled journal
entry. The bill residual becomes the net amount to pay; register the payment as
usual.

To exclude an operation under article 3, set **Excluded from VAT withholding**
in the **Other Info** tab of the draft bill before posting.

Resetting the bill to draft or cancelling it cancels the voucher, keeping its
number, and cancels or reverses the withholding entry. Posting it again issues a
new voucher.

Voucher numbers come from the company sequence and cannot be entered or
changed, with one exception: a voucher issued outside the system can be
registered by an accounting manager by checking **Emitido fuera del sistema**
when creating it and entering its own 14-digit number (`AAAAMM` of its issue
date plus an 8-digit sequence). That number does not consume the company
sequence, must be unique per company, and can be corrected only while the
voucher is a draft. Vouchers issued from bills always take the sequence
number. An issued voucher, manual ones included, never returns to draft: the
only way out of the issued state is cancelling it, which keeps its number. A
mistaken voucher is cancelled and a new one issued. Only draft vouchers can be
deleted.

For a vendor credit note, set the bill it corrects (as the reversal wizard
does) and post it. In the voucher's fortnight a partial credit note is added to
the voucher and a total one cancels it; in a later fortnight it is not
withheld. Resetting a partial credit note to draft removes it from the voucher
and undoes its adjustment entry; posting it again adds it back. A credit note
that cancelled a voucher cannot be reset to draft, cancelled or reversed, as
the cancelled voucher number cannot be reused: register a new vendor bill
instead. Reversing a bill with the "modify" option (cancel and re-create) is
only allowed in the voucher's fortnight; afterwards, issue a credit note.

For bills posted before the addon was configured, use **Create VAT withholding**
on the posted bill.

For VAT withheld by a customer, register the customer payment and enter the
withheld VAT amount and the 14-digit voucher number. The payment posts the net
cash amount and the withholding write-off.

Use Accounting > Vendors > VAT Withholding Vouchers to review and print
vouchers. Use **Export VAT Withholdings TXT (99035)** from the same menu to
generate the SENIAT file for a half-month period.

The printed voucher shows the content required by article 16 of PA
SNAT/2025/000054, including the vendor email and the date the voucher was
delivered to the vendor. Set **Fecha de Entrega al Proveedor** on the voucher, even
after it is issued; it is the only field that stays editable. Without it, the
printed voucher leaves a blank space to fill in by hand. The voucher form warns
when the vendor has no email; posting the bill is not blocked.
