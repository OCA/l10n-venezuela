/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.AccountPortalSidebar.include({
    _updateIframeSize($el) {
        if (!$el || !$el.length || !$el[0]) {
            return;
        }
        let hasWrapwrap = false;
        try {
            hasWrapwrap = Boolean($el.contents().find("div#wrapwrap").length);
        } catch {
            hasWrapwrap = false;
        }
        if (!hasWrapwrap) {
            const h = Math.max(720, Math.min(globalThis.innerHeight - 120, 1400));
            $el.height(0);
            $el.height(h);
            return;
        }
        return this._super(...arguments);
    },
});
