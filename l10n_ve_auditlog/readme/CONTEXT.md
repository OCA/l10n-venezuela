Venezuela SENIAT localization needs ORM-level auditing of accounting and
fiscal documents, plus external DB change tracking and fiscal event history.

Depending on OCA ``auditlog`` from ``server-tools`` forced an extra repository
dependency. ``l10n_ve_auditlog`` keeps the same technical models
(``auditlog.rule``, ``auditlog.log``, HTTP session/request logs) and hosts the
full Venezuela audit features in one module.
