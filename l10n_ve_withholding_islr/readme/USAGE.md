On a vendor bill, each line shows its ISLR concept, proposed from the product
or the vendor; change or clear it while the bill is in draft. Lines without a
concept are not withheld. A bill whose line carries a concept that does not
apply to the person type of the vendor (no SENIAT code for that type, for
example royalties on a domiciled company or national freight on a
non-domiciled one) cannot be posted: the error names the concept, the vendor,
and the person type. The same check applies to the "Crear retención de ISLR"
button, to the net voucher re-issued by a credit note, and to issuing a
manual voucher. Each voucher keeps the SENIAT code it was issued with, and
the XML declares that code even if the concept changes later.

Posting the bill issues one voucher per concept, dated at the bill accounting
date. The tax unit and VES rate in force on that date are used
for the subtrahend of resident individuals. When the withholding is positive,
a withholding entry is posted in the configured journal and reconciled with
the bill: registering the payment afterwards pays only the net amount. When
the withholding is zero (below the subtrahend threshold), the voucher is still
issued, as required by the SENIAT completeness rule, without an entry.

For non-residents the withholding is computed on the taxable base, the
untaxed amount times the presumptive-base percentage of the concept for the
person type (for example 30 % for technical assistance, 50 % for
technological services, 90 % for royalties):

* Non-resident individual: the fixed rate of the concept on the taxable base,
  without subtrahend.
* Non-domiciled legal entity, fixed-rate concept (for example commercial
  commissions 5 % or interest paid to foreign financial institutions
  4.95 %): the rate on the taxable base.
* Non-domiciled legal entity, Tarifa N° 2 concept: the withholding of a bill
  is Tarifa N° 2 applied to the year-to-date taxable base of the vendor
  including the bill, minus Tarifa N° 2 applied to the year-to-date taxable
  base before it. The year-to-date base adds the issued Tarifa N° 2 vouchers
  of the same commercial partner and company in the calendar year of the bill
  (cancelled vouchers do not count), ordered by date, bill, and concept. Both
  terms use the tax unit in force at the bill date and the difference is
  rounded to cents in bolivars. The voucher stores the taxable base and the
  effective rate (withholding over taxable base), which is the rate reported
  in the XML. Accumulating per vendor and calendar year is an assumption of
  this module: the regulation sets the tariff but not the accumulation
  period.
* Double taxation treaty on the vendor: the treaty rate replaces the computed
  one and applies to the gross amount (no presumptive base, no Tarifa N° 2).
  The voucher records that the treaty was applied and the certificate
  reference. A 0 % treaty issues the voucher without an entry.

When a Tarifa N° 2 voucher is inserted before others of the same vendor and
month (a backdated bill) or replaced on a net base by a same-month credit
note, the issued Tarifa N° 2 vouchers of that vendor and month that follow it
are cancelled and re-issued in order, so the result does not depend on the
order in which bills and credit notes are posted. Vouchers of other months
are never recomputed, since they may already be declared. Resetting a bill
to draft does not recompute the vouchers that follow it until the bill is
posted again.

The withholding is computed in bolivars: on a bill in another currency, the
base is the bolivar amount of its lines (the company currency balance when the
company currency is VES, or its conversion at the VES rate of the bill date
otherwise), the withholding is rounded to cents in bolivars, and the result is
converted to the bill currency for the entry. A one-cent difference left in
the foreign currency when the bill is fully paid is settled by the standard
exchange difference; the voucher is never adjusted to absorb it.

Vendor credit notes linked to a bill (created from the bill with "Credit Note")
follow these rules:

* Dated in the same month as the bill voucher: the voucher of each concept
  of the credit note is cancelled (kept for audit, linked to the credit note)
  and its entry undone. If the net base of the concept (bill minus credit
  notes) is still positive, a new voucher is issued on the net base, with the
  rate and subtrahend applied to the net and the person type and treaty kept
  from the cancelled voucher; the XML then carries a single row
  with the bill invoice and control numbers and the net base. If the net is
  zero, nothing is declared. The bill, the credit note, and the new
  withholding entry are reconciled together.
* Dated in a later month: the voucher already declared is left untouched and
  no voucher or XML row is issued for the credit note.
* Not linked to a bill, linked to a bill without an issued voucher, or linked
  to a bill of another company or commercial partner: no ISLR effect.

The ISLR concept of a line cannot be changed once its bill or credit note is
posted; reset the document to draft to change it.

A credit note that adjusted a voucher cannot be reset to draft or cancelled:
restoring the previous voucher could reopen a period already declared to
SENIAT. Register a new vendor bill to correct it. Resetting the bill itself to
draft and posting it again issues the voucher on the net base again.

Resetting the bill to draft or cancelling it cancels its vouchers (the number
is kept) and undoes their entries; posting it again issues new vouchers. While
its voucher is issued, the withholding entry cannot be reset to draft,
cancelled, reversed, deleted, or unreconciled from the bill, whatever the
user's rights; cancel the voucher (or reset the bill) instead. Payments of the
bill can still be unreconciled as usual. For a
bill posted before the configuration was complete, or whose voucher was
cancelled, use the "Crear retención de ISLR" button.

Manual vouchers are created in draft: their number, state, links to bills,
credit notes and withholding entries, the SENIAT code, and the values the
module computes (taxable base and its percentage, Tarifa N° 2, treaty) cannot
be set or changed by users, even in draft; the number comes only from the
company sequence and issuing goes through the "Emitir" button. An issued
voucher, manual ones included, never returns to draft: the only way out of the
issued state is cancelling it, which keeps its number. A mistaken voucher is
cancelled and a new one issued. Only draft vouchers can be deleted.

Use Accounting > Vendors > Comprobantes ISLR to review and print vouchers. Use
Accounting > Vendors > XML Retenciones ISLR (SENIAT) to export a monthly
declaration.

If another installed addon provides `l10n_ve_control_number` on vendor bills,
the export uses that value. Otherwise, it exports `NA` and does not require that
optional addon.

Voucher numbers come from the company sequence (`AAAAMM` of the issue date
plus an 8-digit monthly sequence) and cannot be entered or changed, with one
exception: an accounting manager can register a voucher issued outside the
system by checking **Emitido fuera del sistema** when creating it and entering
its own 14-digit number in that format. That number does not consume the
sequence, must be unique per company, and can be corrected only while the
voucher is a draft.

The printed voucher shows the vendor email and the date it was delivered to the
vendor. Set **Fecha de Entrega al Proveedor** on the voucher, even after it is
issued; it is the only field that stays editable. Without it, the printed
voucher leaves a blank space to fill in by hand. The voucher form warns when the
vendor has no email; posting the bill is not blocked.
