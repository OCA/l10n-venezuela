This addon provides a provider-neutral electronic invoicing workflow for
Venezuelan customer documents issued through digital billing.

It defines a neutral document payload, a four-method provider contract, an
outbound state machine, asynchronous control-number fetching, cancellation,
scheduled processing, and an immutable audit log. Concrete provider adapters
can be installed separately without changing the fiscal payload builder.

A dummy provider is included for testing. It does not contact an external
service and must not be selected in production.

The addon relies on `l10n_ve_fiscal_document` for the emission-medium snapshot
and its trusted, in-process control-number assignment API.
