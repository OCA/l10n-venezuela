This addon manages Venezuelan VAT withholding under Administrative Ruling
SNAT/2025/000054 in both directions.

When the company is designated as a special taxpayer (SPE), the withholding
arises on payment or crediting to the vendor's account, whichever happens first
(article 13). Posting the vendor bill is that crediting, so the withholding is
issued when an eligible vendor bill is posted:

- a legal voucher with a monthly, company-specific, no-gap sequence;
- a withholding journal entry that moves the withheld VAT from the vendor
  payable to the VAT withholding liability account, reconciled with the
  document's payable line.

The withholding is computed on the bill's VAT in company currency (bolivars)
and rounded there; for bills in a foreign currency the amount in that currency
is derived from it at the bill's rate, so the voucher ties to the bill's
bolivar figures.

The document residual is then the net amount to pay, and the standard payment
wizard needs no withholding logic. Vendors that are special taxpayers
themselves are also withheld. Documents expressly excluded by article 3 can be
flagged before posting. Purchase receipts are not subject to VAT withholding.

Vendor credit notes (article 11; article 58 of the VAT Law) never produce a
voucher with negative amounts. A credit note linked to a bill whose voucher is
issued, and dated in the same withholding period (fortnight) as that voucher:

- cancels the voucher and its withholding entry when it brings the bill's net
  VAT to zero; nothing is reported for it;
- otherwise is added to the same voucher, with an adjustment entry that returns
  its share of the withheld VAT to the vendor payable. The TXT reports the bill
  as document type 01 and the credit note as type 03 with the affected invoice,
  both with positive amounts.

A credit note of a later period, without a linked bill, or whose bill has no
issued voucher is not withheld and leaves any voucher untouched.

While a voucher is issued, its withholding and adjustment entries cannot be
reset to draft, cancelled, reversed, deleted or unreconciled by any user; the
voucher must be cancelled (or the source document reset) first.

When a customer acting as a special taxpayer withholds VAT, the received voucher
number and amount are recorded during payment registration. The withheld amount
is posted to the configured receivable withholding account.

The addon also provides the voucher PDF and the 16-column, tab-delimited TXT
export for Form 99035.

The supplier control number is included when another installed addon provides
the optional `l10n_ve_control_number` field. This addon does not require that
field or any unreleased localization addon.
