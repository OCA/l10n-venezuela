# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..hooks import AUDITED_MODELS, ensure_audit_rules


@tagged("post_install", "-at_install")
class TestCompliance(TransactionCase):
    def _ve_rules(self):
        return self.env["auditlog.rule"].search(
            [("name", "=like", "VE Compliance - %")]
        )

    def test_audit_rules_created_and_confirmed(self):
        ensure_audit_rules(self.env)
        rules = self._ve_rules()
        self.assertEqual(len(rules), len(AUDITED_MODELS))
        for rule in rules:
            self.assertEqual(rule.state, "confirmed")
            self.assertTrue(rule.log_create)
            self.assertTrue(rule.log_write)
            self.assertTrue(rule.log_unlink)
            self.assertFalse(rule.log_read)
            self.assertEqual(rule.log_type, "full")

    def test_ensure_audit_rules_is_idempotent(self):
        ensure_audit_rules(self.env)
        ensure_audit_rules(self.env)
        rules = self._ve_rules()
        self.assertEqual(len(rules), len(AUDITED_MODELS))
        for rule in rules:
            self.assertEqual(rule.state, "confirmed")

    def test_write_on_audited_model_is_logged(self):
        ensure_audit_rules(self.env)
        partner = self.env["res.partner"].create({"name": "Audit test partner"})
        self.env.flush_all()
        logs = self.env["auditlog.log"].search(
            [
                ("model_id", "=", self.env["ir.model"]._get_id("res.partner")),
                ("res_id", "=", partner.id),
                ("method", "=", "create"),
            ]
        )
        self.assertTrue(logs)
