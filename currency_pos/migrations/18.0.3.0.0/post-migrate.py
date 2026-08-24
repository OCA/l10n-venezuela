import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _migrate_legacy_currency_pos_fields(env):
    cr = env.cr
    if not _column_exists(cr, "pos_payment", "currency_pos_payment_currency_id"):
        return

    _logger.info("Migrating currency_pos legacy payment fields to payment_currency_*")

    if _column_exists(cr, "pos_payment", "payment_currency_id"):
        cr.execute(
            """
            UPDATE pos_payment
               SET payment_currency_id = COALESCE(
                       payment_currency_id,
                       currency_pos_payment_currency_id
                   ),
                   payment_currency_amount = COALESCE(
                       payment_currency_amount,
                       currency_pos_payment_amount_currency
                   )
             WHERE currency_pos_payment_currency_id IS NOT NULL
                OR currency_pos_payment_amount_currency IS NOT NULL
            """
        )
        for column in (
            "currency_pos_payment_currency_id",
            "currency_pos_payment_amount_currency",
            "currency_pos_payment_rate",
        ):
            if _column_exists(cr, "pos_payment", column):
                cr.execute(
                    'ALTER TABLE pos_payment DROP COLUMN IF EXISTS "%s"' % column
                )
    else:
        cr.execute(
            """
            ALTER TABLE pos_payment
                RENAME COLUMN currency_pos_payment_currency_id
                TO payment_currency_id
            """
        )
        if _column_exists(cr, "pos_payment", "currency_pos_payment_amount_currency"):
            cr.execute(
                """
                ALTER TABLE pos_payment
                    RENAME COLUMN currency_pos_payment_amount_currency
                    TO payment_currency_amount
                """
            )
        if _column_exists(cr, "pos_payment", "currency_pos_payment_rate"):
            cr.execute(
                """
                ALTER TABLE pos_payment
                    RENAME COLUMN currency_pos_payment_rate
                    TO payment_currency_rate
                """
            )

    if _column_exists(cr, "pos_payment_method", "currency_pos_payment_currency_id"):
        cr.execute(
            'ALTER TABLE pos_payment_method '
            'DROP COLUMN IF EXISTS "currency_pos_payment_currency_id"'
        )


def _recompute_payment_rates(env):
    Payment = env["pos.payment"].sudo()
    if "payment_currency_id" not in Payment._fields:
        return
    payments = Payment.search(
        [
            ("payment_currency_id", "!=", False),
            ("currency_id", "!=", False),
        ]
    )
    for payment in payments:
        if payment.payment_currency_id == payment.currency_id:
            payment.write({"payment_currency_rate": 1.0})
            continue
        payment_date = (
            payment.payment_date.date()
            if payment.payment_date
            else fields.Date.context_today(payment)
        )
        rate = env["res.currency"]._get_conversion_rate(
            payment.payment_currency_id,
            payment.currency_id,
            payment.company_id,
            payment_date,
        )
        payment.write({"payment_currency_rate": rate})


def _retire_rt_module(cr):
    cr.execute(
        """
        SELECT id, state
          FROM ir_module_module
         WHERE name = 'rt_pos_payment_currency'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    _logger.info(
        "Retiring rt_pos_payment_currency after merge into currency_pos (was %s)",
        row[1],
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'currency_pos'
         WHERE module = 'rt_pos_payment_currency'
           AND name NOT IN (
               SELECT name
                 FROM ir_model_data
                WHERE module = 'currency_pos'
           )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'rt_pos_payment_currency'
        """
    )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled'
         WHERE name = 'rt_pos_payment_currency'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
         WHERE name = 'rt_pos_payment_currency'
            OR module_id IN (
                   SELECT id FROM ir_module_module
                    WHERE name = 'rt_pos_payment_currency'
               )
        """
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_legacy_currency_pos_fields(env)
    _recompute_payment_rates(env)
    _retire_rt_module(cr)
