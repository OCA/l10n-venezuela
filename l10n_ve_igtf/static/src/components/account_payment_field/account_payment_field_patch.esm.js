import {AccountPaymentField} from "@account/components/account_payment_field/account_payment_field";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

patch(AccountPaymentField.prototype, {
    onInfoClick(ev, line) {
        this.popover.open(ev.currentTarget, {
            title: _t("Journal Entry Info"),
            ...line,
            l10n_ve_igtf_amount_formatted: line.l10n_ve_igtf_amount_formatted,
            l10n_ve_igtf_amount_company_currency_formatted:
                line.l10n_ve_igtf_amount_company_currency_formatted,
            l10n_ve_net_amount_formatted: line.l10n_ve_net_amount_formatted,
            _onRemoveMoveReconcile: this.removeMoveReconcile.bind(this),
            _onOpenMove: this.openMove.bind(this),
        });
    },

    async removeMoveReconcile(moveId, partialId) {
        const action = await this.orm.call(
            this.props.record.resModel,
            "l10n_ve_igtf_get_unreconcile_action",
            [moveId, partialId],
            {}
        );
        if (action) {
            this.popover.close();
            let reloaded = false;
            await this.action.doAction(action, {
                onClose: async () => {
                    if (!reloaded) {
                        reloaded = true;
                        await this.props.record.model.root.load();
                    }
                },
            });
            if (!reloaded) {
                await this.props.record.model.root.load();
            }
            return;
        }
        this.popover.close();
        await this.orm.call(
            this.props.record.resModel,
            "js_remove_outstanding_partial",
            [moveId, partialId],
            {}
        );
        await this.props.record.model.root.load();
    },
});
