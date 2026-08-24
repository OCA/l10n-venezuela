Multi-currency support for Point of Sale:

* Convert product prices and pricelists to the POS currency for display and sale,
  including products loaded later via search, variants, or product edit.
* Convert pricelist and supplier amounts in the product info popup to the POS
  currency (standard Odoo leaves them in the pricelist/supplier currency).
* Show product card and list prices with tax included or excluded according to
  the POS **Tax Display** setting.
* Keep all pricelists configured on the POS available in the pricelist selector,
  including those in a currency different from the company currency.
* On the product screen, show above the order total the equivalent totals for
  every other available pricelist (lines stay unchanged).
* Show exchange rates and an optional display currency in the POS UI.
* Allow payments in a currency different from the order currency, using the daily
  exchange rate configured in Odoo.
* Manage multiple cash registers (one journal/currency each) with opening, cash
  in/out, and closing counts per cash method.
