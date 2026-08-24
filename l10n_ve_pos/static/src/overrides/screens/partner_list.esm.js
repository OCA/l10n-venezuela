import {PartnerList} from "@point_of_sale/app/screens/partner_list/partner_list";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

patch(PartnerList.prototype, {
    onSearchInputKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.onEnter();
    },
    async onEnter() {
        const query = (this.state.query || "").trim();
        if (!query) {
            return;
        }

        const localPartners = this.getPartners();
        if (localPartners.length === 1) {
            this.clickPartner(localPartners[0]);
            return;
        }

        if (localPartners.length === 0) {
            await this.searchPartner();
            const partnersAfterSearchMore = this.getPartners();

            if (partnersAfterSearchMore.length === 1) {
                this.clickPartner(partnersAfterSearchMore[0]);
                return;
            }

            if (partnersAfterSearchMore.length === 0) {
                this.pos.l10n_ve_partner_create_query = query;
                try {
                    await this.editPartner();
                } finally {
                    this.pos.l10n_ve_partner_create_query = null;
                }
                return;
            }
        }

        this.notification.add(
            _t('%s customer(s) found for "%s".', this.getPartners().length, query),
            3000
        );
    },
});
