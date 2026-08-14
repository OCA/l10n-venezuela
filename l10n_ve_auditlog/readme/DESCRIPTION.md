This module provides the Venezuela audit stack:

* ORM audit rules for data models (``create``, ``read``, ``write``, ``delete``).
* Login attempts, HTTP sessions (with IP), validation errors and report access
  logs.
* PostgreSQL triggers that record INSERT, UPDATE and DELETE operations executed
  outside Odoo on critical tables.
* Fiscal document event logs on ``auditlog.log`` with human-readable
  descriptions for invoices, credit/debit notes, fiscal printing, digital
  dispatch, retentions and cancellations.
* PDF report of fiscal document events.

It is based on OCA ``auditlog`` from `server-tools` and replaces that module
(same technical models ``auditlog.*``). Installing this module migrates and
uninstalls ``auditlog`` automatically when present.
