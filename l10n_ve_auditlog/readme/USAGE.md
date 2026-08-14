ORM rules
=========

Go to *Auditoría > Rules* to subscribe rules. A rule defines which operations
to log for a given data model.

Then check logs in *Auditoría > Logs*. You can group them by user sessions,
date, data model or HTTP requests.

A scheduled action exists to delete ORM logs older than 6 months (180 days)
but is not enabled by default.

External database changes
=========================

After installing or upgrading the module, PostgreSQL triggers are created on
the configured tables (see *Auditoría > Audited Tables*).

Changes made outside Odoo appear under *Auditoría > External DB Changes*.

Only connections whose PostgreSQL ``application_name`` does **not** start with
``odoo-`` are logged. Normal Odoo operations are ignored to avoid duplicating
ORM audit entries.

Fiscal document events
======================

Business events such as draft invoice creation from a sale order, invoice
posting, credit note emission, fiscal machine printing and digital dispatch are
recorded in *Auditoría > Fiscal Document Events*.

Each event stores a readable description in ``auditlog.log``. You can print a
PDF report from the list view using *Print > Fiscal Document Events List*.

Adding more tables
==================

#. Go to *Auditoría > Audited Tables*.
#. Create a record with the PostgreSQL table name (for example ``account_move``).
#. Click *Install Triggers* if they were not applied automatically.

Maintenance
===========

A daily cron removes external audit log entries older than 90 days.

To reinstall triggers after a module upgrade, open any audited table record
and click *Install Triggers*, or upgrade the module again.

Security groups
===============

* **Auditlog User**: read-only access to audit logs.
* **Auditlog Manager**: configure audit rules and manage audit data.
