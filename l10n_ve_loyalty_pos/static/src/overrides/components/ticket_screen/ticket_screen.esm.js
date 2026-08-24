import {TicketScreen} from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import {patch} from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    _isEWalletGiftCard(orderline) {
        if (!orderline?.product_id) {
            return false;
        }
        const programs = this.pos.models?.["loyalty.program"];
        if (!programs || typeof programs.some !== "function") {
            return false;
        }
        const productId = orderline.product_id.id;
        return programs.some((program) => {
            if (!["gift_card", "ewallet"].includes(program.program_type)) {
                return false;
            }
            const triggers = program.trigger_product_ids;
            if (!triggers || typeof triggers.map !== "function") {
                return false;
            }
            return triggers.map((product) => product.id).includes(productId);
        });
    },
});
