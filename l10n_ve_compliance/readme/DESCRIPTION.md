This addon is the compliance umbrella of the Venezuelan fiscal localization.

Installing it pulls the published Venezuelan fiscal suite — fiscal document
identification, purchase and sales fiscal books, fiscal invoice layout, IGTF,
municipal tax and the IVA and ISLR withholdings — together with OCA
`auditlog`, and creates the audit trail expected from a fiscal localization:
full create/write/delete logging of the fiscal models, created and confirmed.

The audit set covers journal entries, journals, taxes, companies, partners and
the IVA and ISLR withholding vouchers. `account.move.line` is deliberately
excluded: it is the highest-volume model and its amounts are already protected
by the journal hash chain, which detects any later alteration. Read logging is
intentionally disabled: OCA auditlog documents that it is not reliable on
every model, and enabling it would give a false sense of coverage.

The addon does not enable the journal hash (inalterability) itself: that is an
irreversible accounting decision that must be taken by the accountant.

## Known limitation

Confirmed `full` rules currently crash the Odoo 19 ORM under test conditions
due to an upstream auditlog bug
([OCA/server-tools#3720](https://github.com/OCA/server-tools/issues/3720)).
Until it is fixed and released, this addon is excluded from the repository CI
through the `EXCLUDE` variable of the test workflow, and its rules are not
active during test runs. Production behavior is unaffected: rules are created
and confirmed at installation.
