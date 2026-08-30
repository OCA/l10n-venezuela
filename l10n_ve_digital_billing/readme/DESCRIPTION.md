Venezuelan taxpayers under the digital billing regime (SENIAT PA
SNAT/2024/000102) must have an authorized digital printing house assign the
fiscal control number of each customer document. This addon sends posted
Venezuelan customer documents on a "Digital billing" journal to such a
provider, applies the control number it returns through
`l10n_ve_fiscal_document`'s trusted write-back, and keeps a log of every call
(SENIAT PA SNAT/2024/000121).

All the fiscal logic (taxable base, exempt lines, VAT by rate, the document a
credit or debit note affects) is built into a provider-neutral payload on
`account.move`. A provider only translates that payload into its own
dialect, through a four-method contract (`_edoc_send`, `_edoc_fetch`,
`_edoc_cancel`, `_edoc_test_connection`) that supports both synchronous
providers (the control number comes back in the emission call, like The
Factory HKA) and asynchronous ones (it must be queried afterwards).

Ships with two providers: a simulated one for testing the whole connector
without a contract, and an adapter for **The Factory HKA Venezuela**, written
against its public REST API documentation.

This addon does not compute or print a bolivar-equivalent total, does not
allocate control numbers itself (`l10n_ve_fiscal_document` owns that data),
and does not manage paper batches, printed invoice layouts, or fiscal
machines.
