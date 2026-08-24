import {Component, onMounted, onWillUnmount, useState} from "@odoo/owl";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {_t} from "@web/core/l10n/translation";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import {useService} from "@web/core/utils/hooks";

const EXCHANGE_RATES_RPC_KEY = "l10n_ve_pos_exchange_rates_rpc";
const EXCHANGE_RATES_DATA_KEY = "l10n_ve_pos_exchange_rates_data";

async function fetchExchangeRatesOnce(pos, orm) {
    if (pos[EXCHANGE_RATES_DATA_KEY]) {
        return pos[EXCHANGE_RATES_DATA_KEY];
    }
    if (!pos[EXCHANGE_RATES_RPC_KEY]) {
        pos[EXCHANGE_RATES_RPC_KEY] = orm
            .call("res.currency", "get_exchange_rates", [], {})
            .then((data) => {
                pos[EXCHANGE_RATES_DATA_KEY] = data;
                return data;
            })
            .catch((err) => {
                pos[EXCHANGE_RATES_RPC_KEY] = null;
                throw err;
            });
    }
    return pos[EXCHANGE_RATES_RPC_KEY];
}

export class PosExchangeRatesDropdown extends Component {
    static components = {Dropdown, DropdownItem};
    static template = "l10n_ve_pos.PosExchangeRatesDropdown";
    static props = {};

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        const d = new Date();
        this.currentDate = d.toLocaleString();
        this.state = useState({
            rates: [],
            company_currency: null,
            featured: null,
            loading: true,
            exchangeLabelRevision: 0,
        });
        this._onExchangeCurrencyChange = () => {
            this.state.exchangeLabelRevision++;
        };
        onMounted(() => {
            this.pos.currencyEventBus?.addEventListener(
                "change:exchange_currency_id",
                this._onExchangeCurrencyChange
            );
            this.loadRates();
        });
        onWillUnmount(() => {
            this.pos.currencyEventBus?.removeEventListener(
                "change:exchange_currency_id",
                this._onExchangeCurrencyChange
            );
        });
    }

    async loadRates() {
        this.state.loading = true;
        try {
            const data = await fetchExchangeRatesOnce(this.pos, this.orm);
            this.state.rates = data.rates || [];
            this.state.company_currency = data.company_currency;
            this.state.featured = data.featured || null;
        } catch {
            this.state.rates = [];
            this.state.company_currency = null;
            this.state.featured = null;
        } finally {
            this.state.loading = false;
        }
    }

    _formatRateWithSymbol(rateValue, symbol) {
        if (!rateValue) {
            return "";
        }
        const suffix = symbol ? ` ${symbol}` : "";
        return `${Number(rateValue).toFixed(4)}${suffix}`;
    }

    _rateFromPosCurrency(fromPos, companyCurrencySymbol) {
        if (!fromPos) {
            return "";
        }
        return this._formatRateWithSymbol(
            fromPos.inverse_rate || fromPos.rate,
            companyCurrencySymbol
        );
    }

    _rateFromFeaturedName(featuredName, companyCurrencySymbol) {
        if (!featuredName) {
            return "";
        }
        const currencies = this.pos.models?.["res.currency"];
        const featuredCurrency = currencies?.find(
            (currency) => currency.name === featuredName
        );
        return this._formatRateWithSymbol(
            featuredCurrency?.inverse_rate || featuredCurrency?.rate,
            companyCurrencySymbol
        );
    }

    get displayCurrencyName() {
        if (this.state.exchangeLabelRevision < 0) {
            return "";
        }
        const fromPos = this.pos.getExchangeCurrencyForDisplay?.();
        if (fromPos?.name) {
            return fromPos.name;
        }
        return this.state.featured?.name || "";
    }

    get displayCurrencyRate() {
        if (this.state.exchangeLabelRevision < 0) {
            return "";
        }
        const fromPos = this.pos.getExchangeCurrencyForDisplay?.();
        const companyCurrencySymbol = this.pos.company?.currency_id?.symbol || "";
        const fromPosRate = this._rateFromPosCurrency(fromPos, companyCurrencySymbol);
        if (fromPosRate) {
            return fromPosRate;
        }
        const featuredRate = this._rateFromFeaturedName(
            this.state.featured?.name,
            companyCurrencySymbol
        );
        if (featuredRate) {
            return featuredRate;
        }
        return this._formatRateWithSymbol(
            this.state.featured?.rate,
            this.state.featured?.company_currency_symbol
        );
    }

    get loadingLabel() {
        return _t("Loading rates...");
    }

    get emptyLabel() {
        return _t("No active exchange rates are configured.");
    }

    get dateLine() {
        return `${_t("Date:")} ${this.currentDate}`;
    }

    get ratesRefLine() {
        return _t("Exchange rates (Ref: %s)", this.state.company_currency || "");
    }

    get ratesColonLabel() {
        return _t("Tasas:");
    }

    get exchangeRatesTitle() {
        return _t("Exchange rates");
    }
}
