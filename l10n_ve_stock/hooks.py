def post_init_hook(env):
    env["ir.actions.report"]._l10n_ve_unbind_all_stock_picking_report_bindings()
