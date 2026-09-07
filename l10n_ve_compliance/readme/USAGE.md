Once installed, every create, write and delete on the audited fiscal models
is logged with the previous field values.

To re-create or confirm the rules after adding new audited models or
restoring a database, run from `odoo-bin shell`:

```python
from odoo.addons.l10n_ve_compliance.hooks import ensure_audit_rules

ensure_audit_rules(env)
```

The call is idempotent: existing rules are only confirmed, never duplicated.
