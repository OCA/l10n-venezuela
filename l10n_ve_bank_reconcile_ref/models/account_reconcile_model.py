# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import fields, models
from odoo.osv import expression


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    match_ref_suffix_enabled = fields.Boolean(
        string="Match by reference suffix",
        default=True,
        help="After an exact reference match, try the last digits of the bank "
        "reference (for example last 6, then last 4).",
    )
    match_ref_suffix_lengths = fields.Char(
        string="Suffix lengths",
        default="6,4",
        help="Comma-separated suffix lengths to try in order, for example: 6,4",
    )
    match_payment_before_invoice = fields.Boolean(
        string="Match payments before invoices",
        default=True,
        help="Search open payments first, then open invoices/bills.",
    )

    def _get_invoice_matching_rules_map(self):
        rules_map = super()._get_invoice_matching_rules_map()
        rules_map[5].append(self._get_ref_suffix_amls_candidates)
        return rules_map

    def _get_ref_suffix_lengths(self):
        self.ensure_one()
        lengths = []
        for part in (self.match_ref_suffix_lengths or "").split(","):
            part = part.strip()
            if not part.isdigit():
                continue
            length = int(part)
            if length >= 4 and length not in lengths:
                lengths.append(length)
        return lengths or [6, 4]

    def _normalize_ref_digits(self, value):
        digits = re.sub(r"\D", "", value or "")
        if not digits or digits == "0" or set(digits) == {"0"}:
            return ""
        return digits.lstrip("0") or ""

    def _get_st_line_ref_candidates(self, st_line):
        self.ensure_one()
        texts = self._get_st_line_text_values_for_matching(st_line)
        refs = []
        for text in texts:
            digits = self._normalize_ref_digits(text)
            if digits and digits not in refs:
                refs.append(digits)
            for token in re.findall(r"\d{4,}", text or ""):
                token_digits = self._normalize_ref_digits(token)
                if token_digits and token_digits not in refs:
                    refs.append(token_digits)
        return refs

    def _aml_reference_digits(self, aml, source):
        values = []
        move = aml.move_id
        payment = aml.payment_id
        if source == "payment":
            if payment:
                values.extend(
                    [
                        payment.payment_reference,
                        payment.memo,
                        payment.move_id.ref,
                        payment.move_id.name,
                    ]
                )
            values.extend([move.ref, move.name, aml.name, aml.ref])
        else:
            values.extend(
                [
                    move.payment_reference,
                    move.ref,
                    move.name,
                    aml.name,
                    aml.ref,
                ]
            )
        refs = []
        for value in values:
            digits = self._normalize_ref_digits(value)
            if digits and digits not in refs:
                refs.append(digits)
        return refs

    def _ref_matches(self, st_ref, aml_refs, mode, suffix_len=None):
        for aml_ref in aml_refs:
            if mode == "exact" and st_ref == aml_ref:
                return True
            if mode == "suffix" and suffix_len:
                if len(st_ref) < suffix_len:
                    continue
                st_suffix = st_ref[-suffix_len:]
                if aml_ref == st_suffix:
                    return True
                if len(aml_ref) >= suffix_len and aml_ref[-suffix_len:] == st_suffix:
                    return True
        return False

    def _get_ref_match_amls_domain(self, st_line, partner, source):
        domain = self._get_invoice_matching_amls_domain(st_line, partner)
        if source == "payment":
            domain.append(("payment_id", "!=", False))
        else:
            domain.extend(
                [
                    ("payment_id", "=", False),
                    (
                        "move_id.move_type",
                        "in",
                        (
                            "out_invoice",
                            "out_refund",
                            "out_receipt",
                            "in_invoice",
                            "in_refund",
                            "in_receipt",
                        ),
                    ),
                ]
            )
        return domain

    def _get_ref_match_text_domains(self, source, st_refs, mode, suffix_len):
        patterns = []
        for st_ref in st_refs:
            if mode == "exact":
                patterns.append(st_ref)
            elif suffix_len and len(st_ref) >= suffix_len:
                patterns.append(st_ref[-suffix_len:])
        patterns = list(dict.fromkeys(patterns))
        if not patterns:
            return []

        field_names = (
            [
                "payment_id.payment_reference",
                "payment_id.memo",
                "move_id.ref",
                "move_id.name",
                "name",
                "ref",
            ]
            if source == "payment"
            else [
                "move_id.payment_reference",
                "move_id.ref",
                "move_id.name",
                "name",
                "ref",
            ]
        )
        text_domains = []
        for pattern in patterns:
            leaf_value = pattern if mode == "exact" else f"%{pattern}"
            for field_name in field_names:
                text_domains.append([(field_name, "ilike", leaf_value)])
        return text_domains

    def _amount_matches_st_line(self, st_line, aml):
        st_line_currency = st_line.foreign_currency_id or st_line.currency_id
        st_line_amount = st_line._prepare_move_line_default_vals()[1]["amount_currency"]
        counterpart = st_line._prepare_counterpart_amounts_using_st_line_rate(
            aml.currency_id,
            aml.amount_residual,
            aml.amount_residual_currency,
        )
        residual = st_line_currency.round(
            st_line_amount + counterpart["amount_currency"]
        )
        if st_line_currency.is_zero(residual):
            return True
        if not self.allow_payment_tolerance:
            return False
        if self.payment_tolerance_param == 0:
            return False
        amount_currency = abs(st_line_amount)
        if self.payment_tolerance_type == "percentage":
            max_gap = amount_currency * (self.payment_tolerance_param / 100.0)
        else:
            max_gap = self.payment_tolerance_param
        return abs(residual) <= st_line_currency.round(max_gap)

    def _filter_amls_by_amount(self, st_line, amls):
        return amls.filtered(lambda aml: self._amount_matches_st_line(st_line, aml))

    def _search_ref_match_amls(
        self, st_line, partner, source, st_refs, mode, suffix_len
    ):
        base_domain = self._get_ref_match_amls_domain(st_line, partner, source)
        text_domains = self._get_ref_match_text_domains(
            source, st_refs, mode, suffix_len
        )
        if not text_domains:
            return self.env["account.move.line"]
        domain = expression.AND([base_domain, expression.OR(text_domains)])
        amls = self.env["account.move.line"].search(domain, limit=200)
        matched = self.env["account.move.line"]
        for aml in amls:
            aml_refs = self._aml_reference_digits(aml, source)
            if not aml_refs:
                continue
            for st_ref in st_refs:
                if self._ref_matches(st_ref, aml_refs, mode, suffix_len=suffix_len):
                    matched |= aml
                    break
        return matched

    def _build_ref_match_result(self, st_line, amls):
        if not amls:
            return None
        amount_matched = self._filter_amls_by_amount(st_line, amls)
        if len(amount_matched) == 1:
            return {
                "allow_auto_reconcile": True,
                "amls": amount_matched,
            }
        if len(amls) == 1 and self._amount_matches_st_line(st_line, amls):
            return {
                "allow_auto_reconcile": True,
                "amls": amls,
            }
        if len(amount_matched) > 1:
            return {
                "allow_auto_reconcile": False,
                "amls": amount_matched,
            }
        if len(amls) > 1:
            return {
                "allow_auto_reconcile": False,
                "amls": amls,
            }
        return {
            "allow_auto_reconcile": False,
            "amls": amls,
        }

    def _get_ref_suffix_amls_candidates(self, st_line, partner):
        self.ensure_one()
        if self.rule_type != "invoice_matching" or not self.match_ref_suffix_enabled:
            return None
        if not (
            self.match_text_location_label
            or self.match_text_location_note
            or self.match_text_location_reference
        ):
            return None

        st_refs = self._get_st_line_ref_candidates(st_line)
        if not st_refs:
            return None

        sources = (
            ("payment", "invoice")
            if self.match_payment_before_invoice
            else ("invoice", "payment")
        )
        modes = [("exact", None)]
        if self.match_ref_suffix_enabled:
            modes.extend(
                ("suffix", length) for length in self._get_ref_suffix_lengths()
            )

        for source in sources:
            for mode, suffix_len in modes:
                if mode == "suffix" and not suffix_len:
                    continue
                amls = self._search_ref_match_amls(
                    st_line, partner, source, st_refs, mode, suffix_len
                )
                result = self._build_ref_match_result(st_line, amls)
                if result:
                    return result
        return None
