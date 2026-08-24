from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_is_zero


class PosSession(models.Model):
    _inherit = "pos.session"

    cash_box_ids = fields.One2many(
        "pos.session.cash.box",
        "session_id",
        string="Cash Boxes",
    )

    @api.model
    def _load_pos_data_models(self, config_id):
        models_list = super()._load_pos_data_models(config_id)
        if "res.currency.rate" not in models_list:
            models_list.append("res.currency.rate")
        # Load currencies before payment methods so many2one links resolve on first pass.
        if "res.currency" in models_list and "pos.payment.method" in models_list:
            models_list = [model for model in models_list if model != "res.currency"]
            method_index = models_list.index("pos.payment.method")
            models_list.insert(method_index, "res.currency")
        return models_list

    def _oca_cash_payment_methods(self):
        self.ensure_one()
        return self.payment_method_ids.filtered(lambda pm: pm.type == "cash")

    def _oca_primary_cash_payment_method(self):
        return self._oca_cash_payment_methods()[:1]

    def _oca_payment_method_currency(self, payment_method):
        return payment_method.payment_currency_id or self.currency_id

    def _oca_is_foreign_payment_method(self, payment_method):
        payment_currency = self._oca_payment_method_currency(payment_method)
        return bool(payment_currency and payment_currency != self.currency_id)

    def _oca_get_cash_box(self, payment_method):
        self.ensure_one()
        return self.cash_box_ids.filtered(
            lambda box: box.payment_method_id == payment_method
        )[:1]

    def _oca_primary_cash_statement_lines(self):
        """Cash in/out / differences of the primary cash journal only."""
        self.ensure_one()
        primary = self._oca_primary_cash_payment_method()
        journal = primary.journal_id if primary else self.cash_journal_id
        if not journal:
            return self.env["account.bank.statement.line"]
        return self.sudo().statement_line_ids.filtered(
            lambda line: line.journal_id == journal
        )

    @api.depends(
        "payment_method_ids",
        "order_ids",
        "cash_register_balance_start",
        "statement_line_ids",
        "statement_line_ids.amount",
        "statement_line_ids.journal_id",
        "cash_real_transaction",
    )
    def _compute_cash_balance(self):
        """Exclude foreign cash journals from the primary cash register balance."""
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered("is_cash_count")[:1]
            if cash_payment_method:
                captured_cash_payments_domain = session._get_captured_payments_domain() + [
                    ("payment_method_id", "=", cash_payment_method.id)
                ]
                result = self.env["pos.payment"]._read_group(
                    captured_cash_payments_domain, aggregates=["amount:sum"]
                )
                total_cash_payment = result[0][0] or 0.0
                primary_moves = session._oca_primary_cash_statement_lines()
                if session.state == "closed":
                    total_cash = session.cash_real_transaction + total_cash_payment
                else:
                    total_cash = sum(primary_moves.mapped("amount")) + total_cash_payment
                session.cash_register_balance_end = (
                    session.cash_register_balance_start + total_cash
                )
                session.cash_register_difference = (
                    session.cash_register_balance_end_real
                    - session.cash_register_balance_end
                )
            else:
                session.cash_register_balance_end = 0.0
                session.cash_register_difference = 0.0

    def _validate_session(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        result = super()._validate_session(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        if self.sudo().statement_line_ids:
            self.cash_real_transaction = sum(
                self._oca_primary_cash_statement_lines().mapped("amount")
            )
        return result

    def _post_statement_difference(self, amount):
        primary = self._oca_primary_cash_payment_method()
        if primary:
            self._oca_ensure_cash_boxes()
            primary_box = self._oca_get_cash_box(primary)
            if primary_box:
                amount = primary_box.closing_difference
        super()._post_statement_difference(amount)
        self._oca_post_secondary_cash_box_differences()

    def _oca_previous_cash_box_balance(self, payment_method):
        self.ensure_one()
        previous_session = self.search(
            [
                ("config_id", "=", self.config_id.id),
                ("id", "!=", self.id),
                ("state", "=", "closed"),
            ],
            order="stop_at desc, id desc",
            limit=1,
        )
        if not previous_session:
            return 0.0
        previous_box = previous_session.cash_box_ids.filtered(
            lambda box: box.payment_method_id == payment_method
        )[:1]
        if previous_box:
            return previous_box.balance_end_real
        if payment_method == previous_session._oca_primary_cash_payment_method():
            return previous_session.cash_register_balance_end_real
        return 0.0

    def _oca_ensure_cash_boxes(self, init_from_previous=False):
        for session in self:
            cash_methods = session._oca_cash_payment_methods()
            existing_by_method = {
                box.payment_method_id.id: box for box in session.cash_box_ids
            }
            to_create = []
            for payment_method in cash_methods:
                if payment_method.id in existing_by_method:
                    continue
                balance_start = 0.0
                if init_from_previous:
                    balance_start = session._oca_previous_cash_box_balance(payment_method)
                elif payment_method == session._oca_primary_cash_payment_method():
                    balance_start = session.cash_register_balance_start
                to_create.append(
                    {
                        "session_id": session.id,
                        "payment_method_id": payment_method.id,
                        "balance_start": balance_start,
                    }
                )
            if to_create:
                self.env["pos.session.cash.box"].create(to_create)

    def _oca_sync_cash_box_opening_balances(self):
        """Fill suggested openings from last closed session while still in opening control."""
        for session in self.filtered(lambda record: record.state == "opening_control"):
            session._oca_ensure_cash_boxes(init_from_previous=True)
            primary = session._oca_primary_cash_payment_method()
            for cash_box in session.cash_box_ids:
                if cash_box.payment_method_id == primary:
                    cash_box.balance_start = session.cash_register_balance_start
                else:
                    cash_box.balance_start = session._oca_previous_cash_box_balance(
                        cash_box.payment_method_id
                    )

    def _oca_get_cash_box_opening_map(self):
        self.ensure_one()
        self._oca_sync_cash_box_opening_balances()
        return {
            cash_box.payment_method_id.id: cash_box.balance_start
            for cash_box in self.cash_box_ids
        }

    def _load_pos_data(self, data):
        result = super()._load_pos_data(data)
        if result.get("data"):
            # Prefixed with "_" so POS Base.setup exposes it on the session record.
            result["data"][0]["_oca_cash_box_openings"] = self._oca_get_cash_box_opening_map()
        return result

    def _oca_normalize_cashbox_values(self, cashbox_values):
        if not cashbox_values:
            return {}
        if isinstance(cashbox_values, dict):
            return {int(key): value for key, value in cashbox_values.items()}
        return {int(pm_id): amount for pm_id, amount in cashbox_values}

    def _oca_amount_in_payment_method_currency(self, payments, payment_method):
        currency = self._oca_payment_method_currency(payment_method)
        order_currency = self.currency_id
        total = 0.0
        for payment in payments:
            if payment.payment_method_id != payment_method:
                continue
            if currency == order_currency:
                total += payment.amount
                continue
            if payment.payment_currency_amount not in (False, None):
                total += payment.payment_currency_amount
                continue
            total += payment.currency_id._convert(
                payment.amount,
                currency,
                payment.company_id,
                payment.payment_date.date() if payment.payment_date else fields.Date.today(),
            )
        return currency.round(total), currency

    def _oca_get_journal_cash_moves(self, payment_method):
        self.ensure_one()
        journal = payment_method.journal_id
        moves = []
        cash_in_count = 0
        cash_out_count = 0
        for cash_move in self.sudo().statement_line_ids.filtered(
            lambda line: line.journal_id == journal
        ).sorted("create_date"):
            if cash_move.amount > 0:
                cash_in_count += 1
                name = f"Cash in {cash_in_count}"
            else:
                cash_out_count += 1
                name = f"Cash out {cash_out_count}"
            moves.append(
                {
                    "name": cash_move.payment_ref if cash_move.payment_ref else name,
                    "amount": cash_move.amount,
                }
            )
        return moves

    def _oca_build_cash_box_closing_details(self, payment_method, payments):
        self.ensure_one()
        self._oca_ensure_cash_boxes()
        cash_box = self._oca_get_cash_box(payment_method)
        method_payments = payments.filtered(
            lambda payment: payment.payment_method_id == payment_method
            and not payment.is_change
        )
        amount_payment_currency, payment_currency = self._oca_amount_in_payment_method_currency(
            method_payments,
            payment_method,
        )
        payment_amount_session = sum(method_payments.mapped("amount"))
        moves = self._oca_get_journal_cash_moves(payment_method)
        moves_amount = sum(move["amount"] for move in moves)
        opening = cash_box.balance_start if cash_box else self.cash_register_balance_start
        if self._oca_is_foreign_payment_method(payment_method):
            expected = payment_currency.round(opening + amount_payment_currency + moves_amount)
            amount = expected
            payment_amount = amount_payment_currency
        else:
            expected = self.currency_id.round(opening + payment_amount_session + moves_amount)
            amount = expected
            payment_amount = payment_amount_session
            amount_payment_currency = payment_amount_session
        details = {
            "name": payment_method.name,
            "id": payment_method.id,
            "amount": amount,
            "opening": opening,
            "payment_amount": payment_amount_session,
            "moves": moves,
            "amount_payment_currency": amount_payment_currency,
            "payment_amount_payment_currency": amount_payment_currency,
            "payment_currency_id": payment_currency.id if payment_currency else False,
            "payment_currency_name": payment_currency.name if payment_currency else "",
            "payment_currency_symbol": (
                payment_currency.symbol or payment_currency.name if payment_currency else ""
            ),
            "has_foreign_currency": self._oca_is_foreign_payment_method(payment_method),
            "type": "cash",
        }
        return details

    def _oca_get_foreign_bank_amounts(self, payment_method, payments=None):
        self.ensure_one()
        if payments is None:
            payments = self._get_closed_orders().payment_ids.filtered(
                lambda payment: (
                    payment.payment_method_id == payment_method
                    and not payment.is_change
                    and not float_is_zero(
                        payment.amount, precision_rounding=self.currency_id.rounding
                    )
                )
            )
        amount_foreign, _payment_currency = self._oca_amount_in_payment_method_currency(
            payments,
            payment_method,
        )
        amount_session = sum(payments.mapped("amount"))
        if self.is_in_company_currency:
            amount_converted = self.company_id.currency_id.round(amount_session)
        else:
            amount_converted = self._amount_converter(amount_session, self.stop_at, True)
        return {
            "amount": amount_foreign,
            "amount_converted": amount_converted,
        }

    def _oca_get_force_outstanding_account(self, payment_method, amounts):
        return (
            payment_method._oca_get_payment_outstanding_account_for_amount(
                amounts.get("amount") or 0.0
            )
            or payment_method.outstanding_account_id
        )

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        outstanding_account = self._oca_get_force_outstanding_account(
            payment_method, amounts
        )
        if outstanding_account == payment_method.outstanding_account_id:
            return super()._create_combine_account_payment(
                payment_method, amounts, diff_amount
            )

        destination_account = self._get_receivable_account(payment_method)
        payment_type = "inbound"
        if self.currency_id.compare_amounts(amounts["amount"], 0) < 0:
            payment_type = "outbound"

        account_payment = self.env["account.payment"].with_context(pos_payment=True).create(
            {
                "amount": abs(amounts["amount"]),
                "journal_id": payment_method.journal_id.id,
                "force_outstanding_account_id": outstanding_account.id,
                "destination_account_id": destination_account.id,
                "memo": _(
                    "Combine %(payment_method)s POS payments from %(session)s",
                    payment_method=payment_method.name,
                    session=self.name,
                ),
                "pos_payment_method_id": payment_method.id,
                "pos_session_id": self.id,
                "company_id": self.company_id.id,
                "payment_type": payment_type,
            }
        )
        self._ensure_payment_outstanding_account(account_payment, amounts["amount"])
        account_payment.action_post()

        if self.currency_id.compare_amounts(diff_amount, 0) != 0:
            self._apply_diff_on_account_payment_move(
                account_payment, payment_method, diff_amount
            )

        return account_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self._get_receivable_account(payment_method)
        )

    def _create_split_account_payment(self, payment, amounts):
        payment_method = payment.payment_method_id
        if not payment_method.journal_id:
            return self.env["account.move.line"]

        outstanding_account = self._oca_get_force_outstanding_account(
            payment_method, amounts
        )
        if outstanding_account == payment_method.outstanding_account_id:
            return super()._create_split_account_payment(payment, amounts)

        accounting_partner = self.env["res.partner"]._find_accounting_partner(
            payment.partner_id
        )
        destination_account = accounting_partner.property_account_receivable_id
        payment_type = "inbound"
        if self.currency_id.compare_amounts(amounts["amount"], 0) < 0:
            payment_type = "outbound"

        account_payment = self.env["account.payment"].create(
            {
                "amount": abs(amounts["amount"]),
                "partner_id": accounting_partner.id,
                "journal_id": payment_method.journal_id.id,
                "force_outstanding_account_id": outstanding_account.id,
                "destination_account_id": destination_account.id,
                "memo": _(
                    "%(payment_method)s POS payment of %(partner)s in %(session)s",
                    payment_method=payment_method.name,
                    partner=payment.partner_id.display_name,
                    session=self.name,
                ),
                "pos_payment_method_id": payment_method.id,
                "pos_session_id": self.id,
                "payment_type": payment_type,
            }
        )
        self._ensure_payment_outstanding_account(account_payment, amounts["amount"])
        account_payment.action_post()
        return account_payment.move_id.line_ids.filtered(
            lambda line: line.account_id
            == accounting_partner.property_account_receivable_id
        )

    def _oca_debit_amounts_payment_currency(
        self, partial_move_line_vals, amount, amount_converted, payment_currency
    ):
        return {
            "debit": amount_converted if amount_converted > 0.0 else 0.0,
            "credit": -amount_converted if amount_converted < 0.0 else 0.0,
            "amount_currency": amount,
            "currency_id": payment_currency.id,
            **partial_move_line_vals,
        }

    def _oca_credit_amounts_payment_currency(
        self, partial_move_line_vals, amount, amount_converted, payment_currency
    ):
        return {
            "debit": -amount_converted if amount_converted < 0.0 else 0.0,
            "credit": amount_converted if amount_converted > 0.0 else 0.0,
            "amount_currency": -amount,
            "currency_id": payment_currency.id,
            **partial_move_line_vals,
        }

    def _oca_post_cash_box_difference(self, payment_method, amount):
        self.ensure_one()
        if float_is_zero(amount, precision_rounding=self._oca_payment_method_currency(payment_method).rounding):
            return
        journal = payment_method.journal_id
        if not journal:
            return
        st_line_vals = {
            "journal_id": journal.id,
            "amount": amount,
            "date": self.statement_line_ids.filtered(
                lambda line: line.journal_id == journal
            ).sorted()[-1:].date
            or fields.Date.context_today(self),
            "pos_session_id": self.id,
        }
        if amount < 0.0:
            if not journal.loss_account_id:
                raise UserError(
                    _(
                        "Please go on the %s journal and define a Loss Account. "
                        "This account will be used to record cash difference.",
                        journal.name,
                    )
                )
            st_line_vals["payment_ref"] = _(
                "Cash difference observed during the counting (Loss) - closing"
            )
            st_line_vals["counterpart_account_id"] = journal.loss_account_id.id
        else:
            if not journal.profit_account_id:
                raise UserError(
                    _(
                        "Please go on the %s journal and define a Profit Account. "
                        "This account will be used to record cash difference.",
                        journal.name,
                    )
                )
            st_line_vals["payment_ref"] = _(
                "Cash difference observed during the counting (Profit) - closing"
            )
            st_line_vals["counterpart_account_id"] = journal.profit_account_id.id
        created_line = self.env["account.bank.statement.line"].create(st_line_vals)
        if created_line:
            created_line.move_id.message_post(
                body=_(
                    "Related Session: %(link)s",
                    link=self._get_html_link(),
                )
            )

    def _oca_post_secondary_cash_box_differences(self):
        self.ensure_one()
        if self.env.context.get("oca_skip_secondary_cash_diff"):
            return
        primary = self._oca_primary_cash_payment_method()
        for cash_box in self.cash_box_ids:
            if cash_box.payment_method_id == primary:
                continue
            self._oca_post_cash_box_difference(
                cash_box.payment_method_id,
                cash_box.closing_difference,
            )

    def action_pos_session_open(self):
        result = super().action_pos_session_open()
        self._oca_sync_cash_box_opening_balances()
        return result

    def oca_set_opening_control(self, cashbox_values, notes):
        """Open the session with opening cash amounts per cash payment method.

        :param cashbox_values: dict {payment_method_id: amount} or list of pairs
        :param notes: opening notes
        """
        self.ensure_one()
        if self.state != "opening_control":
            return
        values = self._oca_normalize_cashbox_values(cashbox_values)
        self._oca_ensure_cash_boxes()
        primary = self._oca_primary_cash_payment_method()
        for cash_box in self.cash_box_ids:
            if cash_box.payment_method_id.id in values:
                cash_box.balance_start = values[cash_box.payment_method_id.id]
        principal_amount = values.get(primary.id, 0.0) if primary else 0.0
        self.with_context(oca_cashbox_values=values).set_opening_control(
            principal_amount,
            notes,
        )

    def _set_opening_control_data(self, cashbox_value: int, notes: str):
        self._oca_ensure_cash_boxes()
        cashbox_values = self._oca_normalize_cashbox_values(
            self.env.context.get("oca_cashbox_values")
        )
        primary = self._oca_primary_cash_payment_method()
        for cash_box in self.cash_box_ids:
            if cash_box.payment_method_id == primary:
                continue
            if cash_box.payment_method_id.id in cashbox_values:
                cash_box.balance_start = cashbox_values[cash_box.payment_method_id.id]
        super()._set_opening_control_data(cashbox_value, notes)
        if primary:
            primary_box = self._oca_get_cash_box(primary)
            if primary_box:
                primary_box.balance_start = (
                    cashbox_values.get(primary.id, cashbox_value)
                    if cashbox_values
                    else cashbox_value
                )

    def _prepare_account_bank_statement_line_vals(self, session, sign, amount, reason, extras):
        vals = super()._prepare_account_bank_statement_line_vals(
            session, sign, amount, reason, extras
        )
        extras = extras or {}
        payment_method_id = extras.get("payment_method_id")
        if not payment_method_id:
            return vals
        payment_method = self.env["pos.payment.method"].browse(payment_method_id)
        if not payment_method.exists():
            return vals
        if payment_method.journal_id:
            vals["journal_id"] = payment_method.journal_id.id
        move_type = extras.get("cash_move_type") or ("in" if sign > 0 else "out")
        counterpart = payment_method._oca_get_cash_move_counterpart_account(move_type)
        if counterpart:
            vals["counterpart_account_id"] = counterpart.id
        return vals

    def try_cash_in_out(self, _type, amount, reason, extras):
        extras = dict(extras or {})
        extras["cash_move_type"] = _type
        payment_method_id = extras.get("payment_method_id")
        if payment_method_id:
            payment_method = self.env["pos.payment.method"].browse(payment_method_id)
            sessions = self.filtered(
                lambda session: payment_method in session._oca_cash_payment_methods()
            )
            if not sessions:
                raise UserError(_("There is no cash payment method for this PoS Session"))
            sign = 1 if _type == "in" else -1
            vals_list = [
                self._prepare_account_bank_statement_line_vals(
                    session, sign, amount, reason, extras
                )
                for session in sessions
            ]
            self.env["account.bank.statement.line"].create(vals_list)
            return
        return super().try_cash_in_out(_type, amount, reason, extras)

    def _oca_closing_payment_method_amounts(self, payment_method, payments):
        self.ensure_one()
        order_currency = self.currency_id
        method_currency = self._oca_payment_method_currency(payment_method)
        amount_payment_currency, payment_currency = self._oca_amount_in_payment_method_currency(
            payments,
            payment_method,
        )
        has_foreign_currency = bool(
            payment_currency
            and method_currency
            and payment_currency != order_currency
        )
        return {
            "amount_payment_currency": amount_payment_currency,
            "payment_amount_payment_currency": amount_payment_currency,
            "payment_currency_id": payment_currency.id if payment_currency else False,
            "payment_currency_name": payment_currency.name if payment_currency else "",
            "payment_currency_symbol": payment_currency.symbol or payment_currency.name
            if payment_currency
            else "",
            "has_foreign_currency": has_foreign_currency,
        }

    def _oca_aggregate_payments_amounts_by_employee(self, payments, payment_method):
        """Build pos_hr employee breakdown in the payment method currency when needed."""
        if not hasattr(self, "_aggregate_payments_amounts_by_employee"):
            return []
        if not self._oca_is_foreign_payment_method(payment_method):
            return self._aggregate_payments_amounts_by_employee(payments)

        payments_by_employee = []
        for employee, payments_group in payments.grouped("employee_id").items():
            amount_foreign, _currency = self._oca_amount_in_payment_method_currency(
                payments_group,
                payment_method,
            )
            payments_by_employee.append(
                {
                    "id": employee.id if employee else "others",
                    "name": employee.name if employee else _("Others"),
                    "amount": amount_foreign,
                }
            )
        return sorted(
            payments_by_employee,
            key=lambda item: (item["id"] == "others", item["name"]),
        )

    def _oca_aggregate_moves_by_employee(self, payment_method):
        if not hasattr(self, "_aggregate_moves_by_employee"):
            return []
        journal = payment_method.journal_id
        statement_lines = self.sudo().statement_line_ids.filtered(
            lambda line: line.journal_id == journal
        )
        moves_per_employee = {}
        for employee, moves in statement_lines.grouped("employee_id").items():
            if not employee:
                continue
            moves_per_employee[employee.id] = {
                "id": employee.id,
                "name": employee.name,
                "amount": sum(moves.mapped("amount")),
            }
        return sorted(moves_per_employee.values(), key=lambda item: -item["amount"])

    def get_closing_control_data(self):
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(
                _("You don't have the access rights to get the point of sale closing control data.")
            )
        self.ensure_one()
        data = super().get_closing_control_data()
        self._oca_ensure_cash_boxes()
        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(
            lambda payment: payment.payment_method_id.type != "pay_later"
        )
        cash_methods = self._oca_cash_payment_methods()
        cash_details = []
        for payment_method in cash_methods:
            details = self._oca_build_cash_box_closing_details(payment_method, payments)
            method_payments = payments.filtered(
                lambda payment, pm=payment_method: payment.payment_method_id == pm
                and not payment.is_change
            )
            details["amount_per_employee"] = self._oca_aggregate_payments_amounts_by_employee(
                method_payments,
                payment_method,
            )
            details["moves_per_employee"] = self._oca_aggregate_moves_by_employee(
                payment_method
            )
            cash_details.append(details)
        data["cash_details"] = cash_details
        if cash_details:
            data["default_cash_details"] = cash_details[0]
        data["non_cash_payment_methods"] = [
            method_data
            for method_data in data.get("non_cash_payment_methods", [])
            if method_data.get("type") != "cash"
        ]
        for payment_method_data in data["non_cash_payment_methods"]:
            payment_method = self.env["pos.payment.method"].browse(payment_method_data["id"])
            method_payments = payments.filtered(
                lambda payment, pm=payment_method: payment.payment_method_id == pm
            )
            payment_method_data.update(
                self._oca_closing_payment_method_amounts(payment_method, method_payments)
            )
        return data

    def post_closing_cash_details(self, counted_cash, counted_cash_by_method=None):
        self.ensure_one()
        result = super().post_closing_cash_details(counted_cash)
        if result.get("successful") is False:
            return result
        self._oca_ensure_cash_boxes()
        counted_map = self._oca_normalize_cashbox_values(counted_cash_by_method)
        primary = self._oca_primary_cash_payment_method()
        if primary and primary.id not in counted_map:
            counted_map[primary.id] = counted_cash
        for cash_box in self.cash_box_ids:
            counted = None
            if cash_box.payment_method_id.id in counted_map:
                counted = counted_map[cash_box.payment_method_id.id]
            elif cash_box.payment_method_id == primary:
                counted = counted_cash
            if counted is None:
                continue
            cash_box.balance_end_real = counted
            expected = cash_box._oca_get_expected_balance()
            cash_box.closing_difference = cash_box.currency_id.round(counted - expected)
        return result

    def _create_bank_payment_moves(self, data):
        combine_receivables_bank = data.get("combine_receivables_bank") or {}
        split_receivables_bank = data.get("split_receivables_bank") or {}
        for payment_method in list(combine_receivables_bank.keys()):
            if self._oca_is_foreign_payment_method(payment_method):
                combine_receivables_bank[payment_method] = self._oca_get_foreign_bank_amounts(
                    payment_method
                )
        for payment in list(split_receivables_bank.keys()):
            if self._oca_is_foreign_payment_method(payment.payment_method_id):
                split_receivables_bank[payment] = self._oca_get_foreign_bank_amounts(
                    payment.payment_method_id,
                    payments=payment,
                )
        return super()._create_bank_payment_moves(data)

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        combine_receivables_cash = data.get("combine_receivables_cash") or {}
        split_receivables_cash = data.get("split_receivables_cash") or {}
        for payment_method in list(combine_receivables_cash.keys()):
            if self._oca_is_foreign_payment_method(payment_method):
                combine_receivables_cash[payment_method] = self._oca_get_foreign_bank_amounts(
                    payment_method
                )
        for payment in list(split_receivables_cash.keys()):
            if self._oca_is_foreign_payment_method(payment.payment_method_id):
                split_receivables_cash[payment] = self._oca_get_foreign_bank_amounts(
                    payment.payment_method_id,
                    payments=payment,
                )
        return super()._create_cash_statement_lines_and_cash_move_lines(data)

    def _get_combine_statement_line_vals(self, journal_id, amount, payment_method):
        vals = super()._get_combine_statement_line_vals(journal_id, amount, payment_method)
        if self._oca_is_foreign_payment_method(payment_method):
            vals["amount"] = amount
        return vals

    def _get_split_statement_line_vals(self, journal_id, amount, payment):
        vals = super()._get_split_statement_line_vals(journal_id, amount, payment)
        if self._oca_is_foreign_payment_method(payment.payment_method_id):
            vals["amount"] = amount
        return vals

    def _get_combine_receivable_vals(self, payment_method, amount, amount_converted):
        partial_vals = {
            "account_id": self._get_receivable_account(payment_method).id,
            "move_id": self.move_id.id,
            "name": "%s - %s" % (self.name, payment_method.name),
            "display_type": "payment_term",
        }
        if self._oca_is_foreign_payment_method(payment_method):
            payment_currency = self._oca_payment_method_currency(payment_method)
            return self._oca_debit_amounts_payment_currency(
                partial_vals,
                amount,
                amount_converted,
                payment_currency,
            )
        return super()._get_combine_receivable_vals(payment_method, amount, amount_converted)

    def _get_split_receivable_vals(self, payment, amount, amount_converted):
        if not self._oca_is_foreign_payment_method(payment.payment_method_id):
            return super()._get_split_receivable_vals(payment, amount, amount_converted)
        accounting_partner = self.env["res.partner"]._find_accounting_partner(payment.partner_id)
        partial_vals = {
            "account_id": accounting_partner.property_account_receivable_id.id,
            "move_id": self.move_id.id,
            "partner_id": accounting_partner.id,
            "name": "%s - %s" % (self.name, payment.payment_method_id.name),
        }
        payment_currency = self._oca_payment_method_currency(payment.payment_method_id)
        return self._oca_debit_amounts_payment_currency(
            partial_vals,
            amount,
            amount_converted,
            payment_currency,
        )

    def _get_diff_vals(self, payment_method_id, diff_amount, outstanding_account=False):
        payment_method = self.env["pos.payment.method"].browse(payment_method_id)
        if not self._oca_is_foreign_payment_method(payment_method):
            return super()._get_diff_vals(payment_method_id, diff_amount, outstanding_account)

        diff_compare_to_zero = self.currency_id.compare_amounts(diff_amount, 0)
        source_account = payment_method.outstanding_account_id or outstanding_account
        if diff_compare_to_zero == 0 or not source_account:
            return False

        if diff_compare_to_zero > 0:
            destination_account = payment_method.journal_id.profit_account_id
        else:
            destination_account = payment_method.journal_id.loss_account_id

        payment_currency = self._oca_payment_method_currency(payment_method)
        diff_date = self.stop_at.date() if self.stop_at else fields.Date.context_today(self)
        if self.is_in_company_currency:
            amount_converted = diff_amount
        else:
            amount_converted = self._amount_converter(diff_amount, self.stop_at, True)
        amount_foreign = self.currency_id._convert(
            diff_amount,
            payment_currency,
            self.company_id,
            diff_date,
        )
        source_vals = self._oca_debit_amounts_payment_currency(
            {"account_id": source_account.id},
            amount_foreign,
            amount_converted,
            payment_currency,
        )
        dest_vals = self._oca_credit_amounts_payment_currency(
            {"account_id": destination_account.id},
            amount_foreign,
            amount_converted,
            payment_currency,
        )
        return [source_vals, dest_vals]
