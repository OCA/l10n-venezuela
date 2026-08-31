This module records the Venezuelan Financial Transactions Tax (IGTF) on
payments made in foreign currency or cryptoassets without financial
intermediation.

IGTF is added to the payment's own journal entry through Odoo's native
withholding-line hook. The payment amount continues to settle the receivable or
payable, while the liquidity line includes the additional IGTF amount.

Tax applicability is selected explicitly on each payment. The module does not
infer a counterparty's legal status from its currency or payment journal.

Legal references:

- The [IGTF Law amendment](https://avisavenezuela.org/wp-content/uploads/GO-6687-LEY-DE-REFORMA-PARCIAL-IGTF-1.pdf),
  Official Gazette Extraordinary 6,687 of February 25, 2022, articles 4(5),
  4(6), 13, and 24. Article 24 establishes the default 3% rate.
- [Decree 4,972](https://www.bancaynegocios.com/wp-content/uploads/2024/07/GOE-6.821.pdf),
  Official Gazette Extraordinary 6,821 of July 12, 2024, article 2, which
  preserved that rate for transactions under articles 4(5) and 4(6).
- [Administrative Ruling SNAT/2022/000013](https://finanzasdigital.com/gaceta-oficial-42339-seniat-sujetos-pasivos-especiales-igtf/),
  Official Gazette 42,339 of March 17, 2022, which governs perception by
  designated special taxpayers.

Transaction applicability must be determined by the user. This module does not
replace legal review or implement every SENIAT invoicing, reporting,
declaration, or remittance obligation.
