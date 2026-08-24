1. Point --addons-path to this clone instead of the live l10n-venezuela tree.
2. Create an empty database.
3. Install l10n_ve_test (it pulls every l10n_ve_* addon).
4. Run: odoo --test-enable --stop-after-init --test-tags=/l10n_ve_test
