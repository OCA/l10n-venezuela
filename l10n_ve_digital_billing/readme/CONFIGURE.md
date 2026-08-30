On the Venezuelan sales journal that issues customer documents through a
digital printing house, set its emission medium (provided by
`l10n_ve_fiscal_document`) to "Digital billing".

In Accounting Settings, under "Venezuela - Digital Billing", set the
provider, its username and password, the series and branch of the emitting
company, and whether to use the provider's test environment. Leave "Test
environment" checked until SENIAT has authorized the issuer; while checked,
the addon always talks to the provider's own demo environment regardless of
the URL configured, so a test run can never reach production by mistake.

The connector cron ("VE Digital billing: send and query documents") ships
inactive: activate it only once a provider is under contract, otherwise it
only fills the log with authentication errors.
