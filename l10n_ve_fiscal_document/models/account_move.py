# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError

from .account_journal import EMISSION_MEDIUM_SELECTION

_INTERNAL_OPERATION = object()
_INTERNAL_OPERATION_CONTEXT_KEY = "l10n_ve_fiscal_document_posting"
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

    def _l10n_ve_lock_fiscal_data(self, emission_medium=False):
        values = {"l10n_ve_fiscal_data_locked": True}
        if emission_medium:
            values["l10n_ve_emission_medium"] = emission_medium
        return self.with_context(
            **{_INTERNAL_OPERATION_CONTEXT_KEY: _INTERNAL_OPERATION}
        ).write(values)

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
        protected_fields = _TECHNICAL_FIELDS | {
            "l10n_ve_control_number",
            "l10n_ve_control_date",
        }
        if protected_fields.intersection(vals) or "state" in vals:
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
