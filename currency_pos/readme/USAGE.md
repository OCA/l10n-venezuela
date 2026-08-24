1. Open the POS configuration, enable **Pricelists**, and add every pricelist
   the cashiers must switch between (for example USD and USD BCV), even if their
   currency differs from the company currency.
2. Enable **Allow Payments in Other Currencies**.
3. Configure payment methods linked to bank or cash journals in the desired currencies.
   You can add several cash methods (one journal / currency per cash register).
   On each cash method, set **Incoming** / **Outgoing Payment Method** lines so cash in/out
   posts against the outstanding receipts / payments accounts from Accounting
   (see CONFIGURE.md).
4. Open a POS session. The opening popup shows an opening amount for each cash method.
5. Use **Cash In/Out** and select the target cash register when more than one cash method exists.
   Amounts are recorded on that method's journal and currency; the counterpart account comes
   from the payment method line configured on that POS payment method.
6. Pay orders normally. For a foreign cash or bank method, enter the amount in the payment currency.
7. On closing, the closing popup shows a cash count block per cash method (opening, payments,
   cash in/out, counted, difference) plus the usual bank counts. With **pos_hr** enabled, every
   cash register still appears in the overview (for example EFECTIVO BS and Efectivo USD), not
   only the primary one. Differences are posted to each cash journal's profit/loss account.
8. In the POS, open **Actions** and use the pricelist button to switch between the
   configured lists (USD, USD BCV, etc.).
9. Product cards and list view show prices using the POS **Tax Display** setting
   (tax included or excluded). Secondary amounts in other currencies use the same base.
10. On the product screen, above the order total, the POS shows the equivalent
   totals for the other available pricelists (informational only; lines are not
   changed).
11. Use the **Moneda** button on product and payment screens to change the display currency.
12. Review payment details, applied rates, and audit messages from **Point of Sale > Multi-Currency Payments**.
