1. Open **Invoicing > Municipal Tax (VE)**, or **Accounting > Accounting >
   Municipal Tax (VE)** when the full accounting features are enabled.
2. Select the company and period.
3. Compute the taxable base and the tax determined. When a withholdings suffered
   account is configured, the wizard also shows the withholdings deducted and
   the net payable.
4. Generate the draft provision entry.

The entry debits the expense account for the tax determined, credits the
withholdings suffered account for the deduction, and credits the payable account
for the net. Lines with a zero amount are omitted. The deduction is the posted
balance of the withholdings account at the end of the period, capped at the tax
determined; any excess stays in the account for the next period. Post each
provision before computing the next period, otherwise the same withholdings are
deducted twice.

Only accounting administrators can use the wizard and manage municipalities.
