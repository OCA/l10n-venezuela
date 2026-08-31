This addon manages Venezuelan income tax (ISLR) withholdings under Decree
1,808. It provides:

* The validated SENIAT withholding concepts, codes, and rates for resident
  individuals and domiciled legal entities.
* Historical tax unit (Unidad Tributaria) values used to calculate the
  applicable subtrahend.
* Automatic withholding when registering vendor-bill payments, posted to the
  configured withholding liability account.
* One withholding voucher per affected invoice, with a monthly company-specific
  sequence and a printable PDF report.
* The monthly `RelacionRetencionesISLR` XML export defined by SENIAT technical
  manual version 3.1, including zero-withholding details and declarations with
  no operations.

The withholding base excludes VAT and is prorated for partial and grouped
payments. Monetary values and legal codes are snapshotted on each voucher.
