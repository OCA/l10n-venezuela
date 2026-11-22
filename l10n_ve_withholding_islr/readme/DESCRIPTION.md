This addon manages Venezuelan income tax (ISLR) withholdings under Decree
1,808. It provides:

* The SENIAT withholding concepts, codes, rates, and presumptive-base
  percentages for the four person types of Decree 1,808 art. 9: resident and
  non-resident individuals, domiciled and non-domiciled legal entities.
  A concept applies only to the person types for which the SENIAT table gives
  it a code: royalties, international freight, and insurance premiums, for
  instance, only to non-domiciled or non-resident subjects.
* Non-resident individuals: fixed rate (34 % in general) on the presumptive
  base of the concept, without subtrahend. Non-domiciled legal entities:
  either a fixed rate or the progressive Tarifa N° 2 of the Income Tax Law
  (15 % up to 2,000 tax units, 22 % up to 3,000, 34 % on the excess),
  cumulative per vendor and calendar year.
* An optional double taxation treaty rate per non-resident vendor.
* Historical tax unit (Unidad Tributaria) values used to calculate the
  applicable subtrahend.
* A withholding concept on each vendor bill line, defaulted from the product
  or, failing that, from the vendor.
* Automatic withholding when a vendor bill is posted. Decree
  1,808 art. 1 makes the withholding arise on payment or "abono en cuenta",
  whichever comes first, and posting the bill is the abono en cuenta. A
  posted withholding entry moves the withheld amount from the vendor payable
  to the configured liability account and is reconciled with the bill, so
  the residual is the net to pay.
* One withholding voucher per bill and concept, with a monthly
  company-specific sequence and a printable PDF report. Issued vouchers are
  locked.
* The monthly `RelacionRetencionesISLR` XML export defined by SENIAT technical
  manual version 3.1, including zero-withholding details and declarations with
  no operations.

The withholding base is the untaxed amount of the lines of each concept (VAT
excluded), taken in bolivars from the amounts booked by the bill. The
withholding is computed and rounded in bolivars and only then converted to the
bill currency, so vouchers are always expressed in VES. Rates, subtrahend, and
amounts are snapshotted on each voucher.

Vendor credit notes never issue a voucher: the SENIAT XML rejects negative
amounts and has no document type field.
