/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useTrackedAsync } from "@point_of_sale/app/utils/hooks";
import {
    l10nVeFiscalSerialPosExecutePrint,
    l10nVeFiscalSerialPosIsFiscalMachine,
    l10nVeFiscalSerialPosOrderFiscalNumber,
} from "../../fiscal_serial_pos_print";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.l10nVeFiscalReprint = useTrackedAsync(() =>
            this._l10nVeFiscalReprintDocument()
        );
    },
    get l10nVeShowFiscalReprint() {
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return false;
        }
        return Boolean(l10nVeFiscalSerialPosOrderFiscalNumber(this.currentOrder));
    },
    get l10nVeFiscalReprintLabel() {
        return _t("Reprint document");
    },
    async _l10nVeFiscalReprintDocument() {
        const order = this.currentOrder;
        if (!order) {
            return;
        }
        await l10nVeFiscalSerialPosExecutePrint({
            pos: this.pos,
            env: this.env,
            orderId: order.id,
            order,
        });
    },
});
