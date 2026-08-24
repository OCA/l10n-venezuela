import {deserializeDate, formatDate} from "@web/core/l10n/dates";
import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {formatMonetary} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

const EMPTY_ADVANCES_MESSAGE = _t("Sin anticipos pendientes");

export class AccountAdvancePaymentField extends Component {
    static props = {...standardFieldProps};
    static template = "l10n_ve_payment_advance.AccountAdvancePaymentField";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    getInfo() {
        const info = this.props.record.data[this.props.name] || {
            content: [],
            outstanding: false,
            title: "",
            empty_message: EMPTY_ADVANCES_MESSAGE,
            move_id: this.props.record.resId,
        };
        const content = info.content || [];
        for (const [key, value] of Object.entries(content)) {
            value.index = key;
            value.amount_formatted = formatMonetary(value.amount, {
                currencyId: value.currency_id,
            });
            if (value.date) {
                value.formattedDate = formatDate(deserializeDate(value.date));
            }
        }
        return {
            lines: content,
            outstanding: info.outstanding,
            title: info.title,
            emptyMessage: info.empty_message || EMPTY_ADVANCES_MESSAGE,
            moveId: info.move_id,
        };
    }

    async applyAdvance(moveId, lineId) {
        const action = await this.orm.call(
            this.props.record.resModel,
            "action_open_advance_apply_register",
            [[moveId], lineId],
            {context: this.props.record.context}
        );
        if (action && action.type) {
            await this.action.doAction(action, {
                onClose: async () => {
                    await this.props.record.model.root.load();
                },
            });
        }
    }

    async openMove(moveId) {
        const action = await this.orm.call(
            this.props.record.resModel,
            "action_open_business_doc",
            [moveId]
        );
        this.action.doAction(action);
    }
}

export const accountAdvancePaymentField = {
    component: AccountAdvancePaymentField,
    supportedTypes: ["char"],
};

registry.category("fields").add("advance_payment", accountAdvancePaymentField);
