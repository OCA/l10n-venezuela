# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    companies = env["res.company"].search([])
    companies._l10n_ve_fiscal_ensure_payment_methods()
    Method = env["l10n.ve.fiscal.payment.method"].sudo()
    for company in companies:
        if company.l10n_ve_fiscal_default_payment_method_id:
            continue
        default_method = Method.search(
            [("company_id", "=", company.id), ("code", "=", "01")],
            limit=1,
        )
        if default_method:
            company.l10n_ve_fiscal_default_payment_method_id = default_method
