# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import UserError

from .account_journal import EMISSION_MEDIUM_SELECTION

_INTERNAL_OPERATION = object()
_INTERNAL_OPERATION_CONTEXT_KEY = "l10n_ve_fiscal_document_posting"
_CONTROL_DATA_ASSIGNMENT = object()
_CONTROL_DATA_ASSIGNMENT_CONTEXT_KEY = "l10n_ve_fiscal_document_control_assignment"
_CONTROL_DATA_FIELDS = {
    "l10n_ve_control_number",
    "l10n_ve_control_date",
}
_TECHNICAL_FIELDS = {
    "l10n_ve_emission_medium",
    "l10n_ve_fiscal_data_locked",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_control_number = fields.Char(
        string="Control Number",
        copy=False,
        tracking=True,
        index="btree_not_null",
        help="Fiscal control number assigned to the document.",
    )
    l10n_ve_control_date = fields.Date(
        string="Control Number Date",
        copy=False,
        tracking=True,
        help="Date on which the fiscal control number was assigned.",
    )
    l10n_ve_emission_medium = fields.Selection(
        selection=EMISSION_MEDIUM_SELECTION,
        string="Emission Medium",
        copy=False,
        readonly=True,
        help="Emission medium copied from the journal when the document is posted.",
    )
    l10n_ve_fiscal_data_locked = fields.Boolean(
        string="Fiscal Data Locked",
        copy=False,
        readonly=True,
        help="Technical field that preserves fiscal data immutability after posting.",
    )

    def _l10n_ve_check_fiscal_document_locked(self):
        if self.filtered("l10n_ve_fiscal_data_locked"):
            raise UserError(
                self.env._(
                    "Posted Venezuelan customer fiscal documents cannot be reset "
                    "to draft, deleted, or have their fiscal identification changed. "
                    "Correct the document with a credit or debit note."
                )
            )

    def _l10n_ve_is_internal_operation(self):
        return (
            self.env.context.get(_INTERNAL_OPERATION_CONTEXT_KEY) is _INTERNAL_OPERATION
        )

    def _l10n_ve_get_protected_fields(self):
        return _TECHNICAL_FIELDS | _CONTROL_DATA_FIELDS

    def _l10n_ve_is_control_data_assignment(self, vals):
        return set(vals) <= _CONTROL_DATA_FIELDS and (
            self.env.context.get(_CONTROL_DATA_ASSIGNMENT_CONTEXT_KEY)
            is _CONTROL_DATA_ASSIGNMENT
        )

    def _l10n_ve_lock_fiscal_data(self, emission_medium=False):
        values = {"l10n_ve_fiscal_data_locked": True}
        if emission_medium:
            values["l10n_ve_emission_medium"] = emission_medium
        return self.with_context(
            **{_INTERNAL_OPERATION_CONTEXT_KEY: _INTERNAL_OPERATION}
        ).write(values)

    def _l10n_ve_assign_control_data(self, control_number, control_date=None):
        self.ensure_one()
        if not isinstance(control_number, str) or not control_number.strip():
            raise UserError(self.env._("A fiscal control number is required."))
        control_number = control_number.strip()
        if control_date is not None and (
            not isinstance(control_date, date) or isinstance(control_date, datetime)
        ):
            raise UserError(self.env._("The fiscal control date must be a date."))
        if (
            self.state != "posted"
            or not self.is_sale_document(include_receipts=True)
            or not self.l10n_ve_fiscal_data_locked
        ):
            raise UserError(
                self.env._(
                    "Control data can only be assigned to posted, locked Venezuelan "
                    "customer documents."
                )
            )
        if self.l10n_ve_emission_medium not in {"digital", "fiscal_machine"}:
            raise UserError(
                self.env._(
                    "Control data can only be assigned after posting digital or "
                    "fiscal machine documents."
                )
            )
        if (
            self.l10n_ve_control_number
            and self.l10n_ve_control_number != control_number
        ):
            raise UserError(
                self.env._("A different fiscal control number is already assigned.")
            )
        if (
            control_date
            and self.l10n_ve_control_date
            and self.l10n_ve_control_date != control_date
        ):
            raise UserError(
                self.env._("A different fiscal control date is already assigned.")
            )

        values = {}
        if not self.l10n_ve_control_number:
            values["l10n_ve_control_number"] = control_number
        if control_date and not self.l10n_ve_control_date:
            values["l10n_ve_control_date"] = control_date
        if values:
            self.with_context(
                **{
                    _CONTROL_DATA_ASSIGNMENT_CONTEXT_KEY: _CONTROL_DATA_ASSIGNMENT,
                }
            ).write(values)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self._l10n_ve_is_internal_operation() and any(
            _TECHNICAL_FIELDS.intersection(vals) for vals in vals_list
        ):
            raise UserError(
                self.env._(
                    "The emission medium snapshot and fiscal lock are managed "
                    "automatically."
                )
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            _TECHNICAL_FIELDS.intersection(vals)
            and not self._l10n_ve_is_internal_operation()
        ):
            raise UserError(
                self.env._(
                    "The emission medium snapshot and fiscal lock are managed "
                    "automatically."
                )
            )
        protected_fields = self._l10n_ve_get_protected_fields()
        if (
            protected_fields.intersection(vals) or "state" in vals
        ) and not self._l10n_ve_is_control_data_assignment(vals):
            self._l10n_ve_check_fiscal_document_locked()
        if vals.get("state") == "posted" and not self._l10n_ve_is_internal_operation():
            fiscal_documents = self.filtered(
                lambda move: move.country_code == "VE"
                and move.is_sale_document(include_receipts=True)
            )
            if fiscal_documents:
                raise UserError(
                    self.env._(
                        "Venezuelan customer documents must be posted through the "
                        "standard posting action."
                    )
                )
        return super().write(vals)

    def unlink(self):
        self._l10n_ve_check_fiscal_document_locked()
        return super().unlink()

    def button_draft(self):
        self._l10n_ve_check_fiscal_document_locked()
        return super().button_draft()

    def _l10n_ve_set_control_number(self, control_number, control_date=False):
        """Compatibility wrapper for the original connector API."""
        self.ensure_one()
        if self.l10n_ve_control_number:
            raise UserError(
                self.env._(
                    "%(document)s already has a control number assigned.",
                    document=self.display_name,
                )
            )
        return self._l10n_ve_assign_control_data(
            control_number,
            control_date or fields.Date.context_today(self),
        )

    def _post(self, soft=True):
        moves_to_post = self
        if soft:
            today = fields.Date.context_today(self)
            moves_to_post = self.filtered(lambda move: move.date <= today)
        fiscal_documents = moves_to_post.filtered(
            lambda move: move.country_code == "VE"
            and move.is_sale_document(include_receipts=True)
        )
        missing_medium = fiscal_documents.filtered(
            lambda move: not move.journal_id.l10n_ve_emission_medium
        )
        if missing_medium:
            raise UserError(
                self.env._(
                    "Configure an emission medium on the following sales journals "
                    "before posting: %(journals)s",
                    journals=", ".join(
                        missing_medium.journal_id.mapped("display_name")
                    ),
                )
            )

        documents_to_snapshot = fiscal_documents.filtered(
            lambda move: not move.l10n_ve_fiscal_data_locked
        )
        posted_moves = super(
            AccountMove,
            self.with_context(**{_INTERNAL_OPERATION_CONTEXT_KEY: _INTERNAL_OPERATION}),
        )._post(soft)
        for move in posted_moves & documents_to_snapshot:
            move._l10n_ve_lock_fiscal_data(move.journal_id.l10n_ve_emission_medium)
        return posted_moves
