This module replaces OCA ``auditlog`` (same technical models ``auditlog.*``).
Do not keep both installed.

When you install or upgrade ``l10n_ve_audit`` / ``l10n_ve_auditlog``,
``pre_init_hook`` automatically:

1. Reassigns XML-IDs from OCA ``auditlog`` (if installed) and from the former
   ``l10n_ve_audit`` content to ``l10n_ve_auditlog``.
2. Links existing ``l10n.ve.db.audit.table`` rows so data files update them
   instead of inserting duplicates.
3. Marks ``auditlog`` as uninstalled without dropping ``auditlog.*`` tables.

After the upgrade, review subscribed rules and security groups.
