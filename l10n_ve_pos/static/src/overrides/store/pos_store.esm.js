import {PosStore} from "@point_of_sale/app/store/pos_store";
import {SelectionPopup} from "@point_of_sale/app/utils/input_popups/selection_popup";
import {_t} from "@web/core/l10n/translation";
import {makeAwaitable} from "@point_of_sale/app/store/make_awaitable_dialog";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

function isRifLike(value) {
    const term = (value || "").trim();
    if (!term) {
        return false;
    }
    if (/^[VEJPGC]/i.test(term) && /\d/.test(term)) {
        return true;
    }
    const digits = term.replace(/\D/g, "");
    return /^[\d.\-\sVEJPGC]+$/i.test(term) && digits.length >= 6;
}

patch(PosStore.prototype, {
    _l10nVePosHasZeroQtyLines(order) {
        return (order?.lines || []).some(
            (line) =>
                !line.combo_parent_id && this.isProductQtyZero(line.get_quantity())
        );
    },
    async pay() {
        const currentOrder = this.get_order();
        if (isVenezuelaCompany(this) && this._l10nVePosHasZeroQtyLines(currentOrder)) {
            this.notification.add(
                _t("Cannot go to payment while there are order lines with quantity 0."),
                {type: "danger"}
            );
            return;
        }
        return await super.pay(...arguments);
    },
    selectOrderLine(order, line) {
        super.selectOrderLine(...arguments);
        if (!isVenezuelaCompany(this)) {
            return;
        }
        if (line?.product_id?.l10n_ve_pos_allow_price_change) {
            this.numpadMode = "price";
        } else {
            this.numpadMode = "quantity";
        }
    },
    createNewOrder(data = {}) {
        const order = super.createNewOrder(data);
        if (!isVenezuelaCompany(this)) {
            return order;
        }
        const defaultJournal =
            this.config.invoice_journal_id ||
            this.models["account.journal"]?.find((journal) => journal.type === "sale");
        if (
            defaultJournal &&
            typeof defaultJournal === "object" &&
            !order.invoice_journal_id
        ) {
            order.setInvoiceJournal(defaultJournal);
        }
        return order;
    },
    getAvailableInvoiceJournals() {
        const currencyId = this.currency?.id;
        const journals = this.models["account.journal"] || [];
        return journals.filter((journal) => {
            if (journal.type !== "sale") {
                return false;
            }
            if (!journal.currency_id) {
                return true;
            }
            return journal.currency_id.id === currencyId;
        });
    },
    async selectInvoiceJournal(order = this.get_order()) {
        if (!order || !isVenezuelaCompany(this)) {
            return;
        }
        if (
            typeof order.canChangeInvoiceJournal === "function" &&
            !order.canChangeInvoiceJournal()
        ) {
            this.notification.add(
                _t(
                    "The invoice journal of a refund cannot be changed; it must match the original order."
                ),
                {type: "warning"}
            );
            return;
        }
        const journals = this.getAvailableInvoiceJournals();
        if (!journals.length) {
            return;
        }
        const currentJournal = order.invoice_journal_id;
        const selectedJournal = await makeAwaitable(this.dialog, SelectionPopup, {
            list: journals.map((journal) => ({
                id: journal.id,
                label: journal.display_name || journal.name,
                isSelected: currentJournal ? journal.id === currentJournal.id : false,
                item: journal,
            })),
            title: _t("Diario de facturación"),
        });
        if (!selectedJournal) {
            return;
        }
        order.setInvoiceJournal(selectedJournal);
        if (typeof this.syncAllOrders === "function" && order) {
            this.addPendingOrder?.([order.id]);
            try {
                await this.syncAllOrders({orders: [order]});
            } catch (error) {
                this.notification.add(
                    error.message || _t("Could not sync the order."),
                    {type: "warning"}
                );
            }
        }
        return selectedJournal;
    },
    async allowProductCreation() {
        if (isVenezuelaCompany(this)) {
            return false;
        }
        return await super.allowProductCreation(...arguments);
    },
    async editProduct(product) {
        if (!product && isVenezuelaCompany(this)) {
            this.notification.add(
                _t("Creating products from the Point of Sale is not allowed."),
                {type: "warning"}
            );
            return;
        }
        return await super.editProduct(...arguments);
    },
    async setDiscountFromUI(line, val) {
        if (isVenezuelaCompany(this)) {
            const n =
                typeof val === "number"
                    ? val
                    : parseFloat(String(val ?? "").replace(",", "."));
            if (!Number.isNaN(n) && n >= 100) {
                this.notification.add(_t("A discount of 100% is not allowed."), {
                    type: "warning",
                });
                return;
            }
        }
        return await super.setDiscountFromUI(...arguments);
    },
    editPartnerContext(partner) {
        const context = super.editPartnerContext(...arguments);
        if (partner || !isVenezuelaCompany(this)) {
            return context;
        }

        const query = (this.l10n_ve_partner_create_query || "").trim();
        if (!query) {
            return context;
        }

        if (isRifLike(query)) {
            return {
                ...context,
                default_name: query,
                default_vat: query,
            };
        }

        return {
            ...context,
            default_name: query,
        };
    },
});
