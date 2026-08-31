Posting a customer document from a journal configured for digital billing
queues it when the company has a provider selected.

Use **Send Electronic Document** to send it immediately. Synchronous providers
assign the control number in that operation. Asynchronous providers leave the
document in **Sent, Awaiting Control Number** until **Fetch Control Number** or
the scheduled action retrieves it.

Use **Cancel Electronic Document** to request cancellation from the provider.
This operation does not cancel the accounting entry in Odoo.

Every provider call creates a read-only log. Accounting users only see logs for
their currently allowed companies. Common secret-bearing keys are redacted
before request or response values are persisted.

Provider addons inherit `l10n.ve.edoc.provider` and implement `_edoc_send`,
`_edoc_fetch`, `_edoc_cancel`, and `_edoc_test_connection`. Send and fetch must
return a mapping with `external_id`, `control_number`, and `control_date`.
