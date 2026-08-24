import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { formatFloat } from "@web/core/utils/numbers";
import {
    convertCurrency,
    getCurrencyRecord,
    getPaymentMethodCurrency,
} from "../../utils/payment_currency_utils";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { ConnectionLostError } from "@web/core/network/rpc";
import { deduceUrl } from "@point_of_sale/utils";

ClosePosPopup.props = [...ClosePosPopup.props, "cash_details?"];

patch(ClosePosPopup.prototype, {
    setup() {
        this.moneyDetailsByMethod = {};
        super.setup();
    },

    getCashDetailsList() {
        if (this.props.cash_details?.length) {
            return this.props.cash_details;
        }
        if (this.props.default_cash_details?.id) {
            return [this.props.default_cash_details];
        }
        return [];
    },

    _getClosingPaymentMethodData(paymentId) {
        const normalizedId = Number(paymentId);
        const cashDetails = this.getCashDetailsList().find((pm) => pm.id === normalizedId);
        if (cashDetails) {
            return cashDetails;
        }
        if (this.props.default_cash_details?.id === normalizedId) {
            return this.props.default_cash_details;
        }
        return this.props.non_cash_payment_methods.find((pm) => pm.id === normalizedId);
    },

    _getPaymentCurrencyRecord(paymentMethodData) {
        if (!paymentMethodData) {
            return null;
        }
        const fromDetails = getCurrencyRecord(
            this.pos.models,
            paymentMethodData.payment_currency_id
        );
        if (fromDetails) {
            return fromDetails;
        }
        const paymentMethod = this.pos.models["pos.payment.method"].get(paymentMethodData.id);
        return getPaymentMethodCurrency(paymentMethod, this.pos.models, null);
    },

    getCurrencySymbol(paymentMethodData) {
        const currency =
            this._getPaymentCurrencyRecord(paymentMethodData) || this.pos.currency;
        return currency?.symbol || currency?.name || "";
    },

    _parseClosingCountedAmount(paymentId) {
        const counted = this.state.payments[paymentId]?.counted;
        if (!this.env.utils.isValidFloat(counted)) {
            return NaN;
        }
        return this.env.utils.parseValidFloat(counted);
    },

    getExpectedClosingCount(paymentMethodData) {
        if (!paymentMethodData) {
            return 0;
        }
        // Cash boxes already store full expected in `amount` (opening + payments + moves).
        if (paymentMethodData.type === "cash" || Array.isArray(paymentMethodData.moves)) {
            return paymentMethodData.amount ?? 0;
        }
        if (!paymentMethodData.has_foreign_currency) {
            return paymentMethodData.amount ?? 0;
        }
        if (paymentMethodData.amount_payment_currency != null) {
            return paymentMethodData.amount_payment_currency;
        }
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        if (!paymentCurrency) {
            return paymentMethodData.amount ?? 0;
        }
        return convertCurrency(
            paymentMethodData.amount,
            this.pos.currency,
            paymentCurrency,
            this.pos.models
        );
    },

    getForeignCountDifference(paymentMethodData, paymentId) {
        const counted = this._parseClosingCountedAmount(paymentId);
        if (Number.isNaN(counted)) {
            return NaN;
        }
        return counted - this.getExpectedClosingCount(paymentMethodData);
    },

    formatClosingCountInput(paymentMethodData) {
        if (!paymentMethodData) {
            return "0";
        }
        if (paymentMethodData.has_foreign_currency) {
            const amount = this.getExpectedClosingCount(paymentMethodData);
            const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
            const decimalPlaces =
                paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
            return formatFloat(amount, { digits: [true, decimalPlaces] });
        }
        return this.env.utils.formatCurrency(paymentMethodData.amount, false);
    },

    formatClosingPaymentAmount(paymentMethodData) {
        if (!paymentMethodData) {
            return "";
        }
        if (paymentMethodData.type === "cash" || paymentMethodData.moves) {
            return this.formatClosingCashExpected(paymentMethodData);
        }
        const orderAmount = this.env.utils.formatCurrency(paymentMethodData.amount);
        if (!paymentMethodData.has_foreign_currency) {
            return orderAmount;
        }
        const symbol =
            paymentMethodData.payment_currency_symbol ||
            paymentMethodData.payment_currency_name ||
            "";
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formattedForeign = formatFloat(this.getExpectedClosingCount(paymentMethodData), {
            digits: [true, decimalPlaces],
        });
        const foreignAmount = `${formattedForeign} ${symbol}`.trim();
        return `${foreignAmount} (${orderAmount})`;
    },

    formatClosingCashExpected(paymentMethodData) {
        if (!paymentMethodData?.has_foreign_currency) {
            return this.env.utils.formatCurrency(paymentMethodData.amount);
        }
        const symbol =
            paymentMethodData.payment_currency_symbol ||
            paymentMethodData.payment_currency_name ||
            "";
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formattedForeign = formatFloat(this.getExpectedClosingCount(paymentMethodData), {
            digits: [true, decimalPlaces],
        });
        return `${formattedForeign} ${symbol}`.trim();
    },

    formatClosingCashOpening(paymentMethodData) {
        if (!paymentMethodData?.has_foreign_currency) {
            return this.env.utils.formatCurrency(paymentMethodData.opening);
        }
        const symbol =
            paymentMethodData.payment_currency_symbol ||
            paymentMethodData.payment_currency_name ||
            "";
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formatted = formatFloat(paymentMethodData.opening || 0, {
            digits: [true, decimalPlaces],
        });
        return `${formatted} ${symbol}`.trim();
    },

    formatClosingPaymentSubAmount(paymentMethodData) {
        if (!paymentMethodData?.has_foreign_currency) {
            return this.env.utils.formatCurrency(
                Math.abs(paymentMethodData?.payment_amount || 0)
            );
        }
        const symbol =
            paymentMethodData.payment_currency_symbol ||
            paymentMethodData.payment_currency_name ||
            "";
        const orderAmount = this.env.utils.formatCurrency(
            Math.abs(paymentMethodData.payment_amount || 0)
        );
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formattedForeign = formatFloat(
            Math.abs(paymentMethodData.payment_amount_payment_currency || 0),
            { digits: [true, decimalPlaces] }
        );
        const foreignAmount = `${formattedForeign} ${symbol}`.trim();
        return `${foreignAmount} (${orderAmount})`;
    },

    formatClosingCountedDisplay(paymentMethodData, counted) {
        if (!paymentMethodData?.has_foreign_currency) {
            return this.env.utils.formatCurrency(counted);
        }
        const symbol =
            paymentMethodData.payment_currency_symbol ||
            paymentMethodData.payment_currency_name ||
            "";
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formattedCounted = formatFloat(counted, { digits: [true, decimalPlaces] });
        return `${formattedCounted} ${symbol}`.trim();
    },

    formatClosingDifferenceDisplay(paymentMethodData, paymentId) {
        const paymentMethod = paymentMethodData || this._getClosingPaymentMethodData(paymentId);
        const normalizedId = Number(paymentId);
        if (!paymentMethod?.has_foreign_currency) {
            return this.env.utils.formatCurrency(this.getDifference(normalizedId));
        }
        const diffForeign = this.getForeignCountDifference(paymentMethod, normalizedId);
        const symbol =
            paymentMethod.payment_currency_symbol ||
            paymentMethod.payment_currency_name ||
            "";
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethod);
        const decimalPlaces =
            paymentCurrency?.decimal_places ?? this.pos.currency.decimal_places;
        const formattedDiff = formatFloat(diffForeign, { digits: [true, decimalPlaces] });
        const orderDiff = this.env.utils.formatCurrency(
            this._convertForeignCountDifferenceToOrderCurrency(diffForeign, paymentMethod)
        );
        return `${formattedDiff} ${symbol} (${orderDiff})`.trim();
    },

    _convertForeignCountDifferenceToOrderCurrency(diffForeign, paymentMethodData) {
        const paymentCurrency = this._getPaymentCurrencyRecord(paymentMethodData);
        if (!paymentCurrency) {
            return diffForeign;
        }
        return convertCurrency(
            diffForeign,
            paymentCurrency,
            this.pos.currency,
            this.pos.models
        );
    },

    getCashMoveData(cashDetails) {
        const details = cashDetails || this.props.default_cash_details;
        const { total, moves } = (details?.moves || []).reduce(
            (acc, move, i) => {
                acc.total += move.amount;
                acc.moves.push({
                    id: i,
                    name: move.name,
                    amount: move.amount,
                });
                return acc;
            },
            { total: 0, moves: [] }
        );
        return { total, moves };
    },

    get cashMoveData() {
        return this.getCashMoveData(this.props.default_cash_details);
    },

    getInitialState() {
        const initialState = { notes: "", payments: {} };
        if (this.pos.config.cash_control) {
            for (const cashDetails of this.getCashDetailsList()) {
                initialState.payments[cashDetails.id] = {
                    counted: this.formatClosingCountInput(cashDetails),
                };
            }
        }
        this.props.non_cash_payment_methods.forEach((pm) => {
            if (pm.type === "bank") {
                initialState.payments[pm.id] = {
                    counted: pm.has_foreign_currency
                        ? this.formatClosingCountInput(pm)
                        : this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });
        return initialState;
    },

    autoFillCashCount(cashDetails) {
        const details = cashDetails || this.getCashDetailsList()[0];
        if (!details) {
            return;
        }
        this.state.payments[details.id].counted = this.formatClosingCountInput(details);
        this.setManualCashInput(this.getExpectedClosingCount(details), details.id);
    },

    setManualCashInput(amount, paymentMethodId) {
        if (this.env.utils.isValidFloat(amount)) {
            const methodId = paymentMethodId || this.props.default_cash_details?.id;
            if (methodId && this.moneyDetailsByMethod[methodId]) {
                this.state.notes = "";
                this.moneyDetailsByMethod[methodId] = null;
            } else if (this.moneyDetails) {
                this.state.notes = "";
                this.moneyDetails = null;
            }
        }
    },

    async openDetailsPopup(cashDetails) {
        const details = cashDetails || this.getCashDetailsList()[0];
        if (!details) {
            return;
        }
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetailsByMethod[details.id] || null,
            action: action,
            getPayload: (payload) => {
                const { total, moneyDetailsNotes, moneyDetails } = payload;
                this.state.payments[details.id].counted = details.has_foreign_currency
                    ? formatFloat(total, {
                          digits: [
                              true,
                              this._getPaymentCurrencyRecord(details)?.decimal_places ?? 2,
                          ],
                      })
                    : this.env.utils.formatCurrency(total, false);
                if (moneyDetailsNotes) {
                    this.state.notes = moneyDetailsNotes;
                }
                this.moneyDetailsByMethod[details.id] = moneyDetails;
            },
            context: "Closing",
        });
    },

    getDifference(paymentId) {
        const normalizedId = Number(paymentId);
        const paymentMethodData = this._getClosingPaymentMethodData(normalizedId);
        if (Number.isNaN(this._parseClosingCountedAmount(normalizedId))) {
            return NaN;
        }
        if (paymentMethodData?.has_foreign_currency) {
            const diffForeign = this.getForeignCountDifference(
                paymentMethodData,
                normalizedId
            );
            return this._convertForeignCountDifferenceToOrderCurrency(
                diffForeign,
                paymentMethodData
            );
        }
        const counted = this._parseClosingCountedAmount(normalizedId);
        const expectedAmount = this.getExpectedClosingCount(paymentMethodData);
        return counted - expectedAmount;
    },

    async closeSession() {
        this.pos._resetConnectedCashier();
        if (this.pos.config.customer_display_type === "proxy") {
            const proxyIP = this.pos.getDisplayDeviceIP();
            fetch(`${deduceUrl(proxyIP)}/hw_proxy/customer_facing_display`, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ params: { action: "close" } }),
                targetAddressSpace: odoo.use_lna ? "local" : undefined,
            }).catch(() => {
                console.log("Failed to send data to customer display");
            });
        }
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }
        if (this.pos.config.cash_control) {
            const cashDetailsList = this.getCashDetailsList();
            const primary = cashDetailsList[0] || this.props.default_cash_details;
            const countedCashByMethod = {};
            for (const cashDetails of cashDetailsList) {
                countedCashByMethod[cashDetails.id] = this.env.utils.parseValidFloat(
                    this.state.payments[cashDetails.id].counted
                );
            }
            const response = await this.pos.data.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.session.id],
                {
                    counted_cash: countedCashByMethod[primary.id],
                    counted_cash_by_method: countedCashByMethod,
                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.pos.data.call("pos.session", "update_closing_control_state_session", [
                this.pos.session.id,
                this.state.notes,
            ]);
        } catch (error) {
            if (!error.data && error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        try {
            const bankPaymentMethodDiffPairs = this.props.non_cash_payment_methods
                .filter((pm) => pm.type == "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);
            const response = await this.pos.data.call(
                "pos.session",
                "close_session_from_ui",
                [this.pos.session.id, bankPaymentMethodDiffPairs],
                {
                    context: {
                        login_number: odoo.login_number,
                    },
                }
            );
            if (!response.successful) {
                return this.handleClosingError(response);
            }
            localStorage.removeItem(`pos.session.${odoo.pos_config_id}`);
            location.reload();
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                throw error;
            }
            await this.handleClosingControlError();
        }
    },
});
