import {Navbar} from "@point_of_sale/app/navbar/navbar";
import {PosExchangeRatesDropdown} from "./pos_exchange_rates_dropdown.esm";
import {patch} from "@web/core/utils/patch";

Navbar.components = {
    ...Navbar.components,
    PosExchangeRatesDropdown,
};

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(Navbar.prototype, {
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
});
