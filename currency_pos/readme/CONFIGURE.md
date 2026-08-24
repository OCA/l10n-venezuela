1. Open **Point of Sale > Configuration > Settings** and enable **Multi-Currency Payments**.
2. Under **Taxes**, set **Tax Display** to *Tax-Excluded Price* or *Tax-Included Price*.
   The same option controls prices shown on product cards and list view in the POS.
3. Open **Point of Sale > Configuration > Payment Methods**.
4. Select or create a cash (or bank) payment method and set its **Journal**.
   The **Payment Currency** is taken from the journal currency (or company currency).
5. Open the **Contabilidad** tab and review **Incoming Payment Method** / **Outgoing Payment Method**.
   They are filled from the journal's Accounting incoming / outgoing payment method lines
   (same as Contabilidad > Journals > Incoming / Outgoing Payments).
6. Optionally change the selected lines. The related outstanding receipts / payments accounts
   are shown read-only for verification.
7. At session close, bank/card payments use those outstanding accounts:
   payments (inbound) → incoming line account; refunds (outbound) → outgoing line account.
8. Cash in/out uses the same inbound/outbound accounts as counterpart.
   Leave the lines empty only if you want cash in/out to keep using the journal suspense account.
