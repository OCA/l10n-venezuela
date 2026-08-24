# Copyright 2023 Luis Pinzón
# Copyright 2026 Anderson Armeya
# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from lxml import etree

from odoo import fields, models

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = (10, 60)
CURRENCIES = {
    "EUR": "euro",
    "CNY": "yuan",
    "TRY": "lira",
    "RUB": "rublo",
    "USD": "dolar",
}
CARACAS_TZ = ZoneInfo("America/Caracas")
BCV_URL = "http://www.bcv.org.ve/"


class ResCurrencyRateProvider(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("bcv", "BCV scraping")],
        ondelete={"bcv": "set default"},
    )

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != "bcv":
            return super()._get_supported_currencies()
        return list(CURRENCIES.keys())

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "bcv":
            return super()._obtain_rates(base_currency, currencies, date_from, date_to)

        _logger.info(
            "BCV provider id=%s: request rates base=%s currencies=%s " "from=%s to=%s",
            self.id,
            base_currency,
            currencies,
            date_from,
            date_to,
        )

        content = defaultdict(dict)
        bcv_data = self._scrap(currencies)
        if not bcv_data:
            _logger.warning(
                "BCV provider id=%s: no rates obtained (check network, "
                "BCV HTML or xpath)",
                self.id,
            )

        for currency_name, (rate, timestamp) in bcv_data.items():
            rate_date = timestamp.date() if hasattr(timestamp, "date") else timestamp
            content[rate_date.isoformat()][currency_name] = rate

        _logger.info(
            "BCV provider id=%s: response with %s quotation date(s)",
            self.id,
            len(content),
        )
        return content

    def _scrap(self, available_currencies):
        result = {}
        _logger.info("BCV: GET %s timeout=%s", BCV_URL, REQUEST_TIMEOUT)
        try:
            fetched_data = requests.get(BCV_URL, verify=False, timeout=REQUEST_TIMEOUT)
        except Exception:
            _logger.warning(
                "BCV provider id=%s: network or timeout error contacting %s",
                self.id,
                BCV_URL,
                exc_info=True,
            )
            return result

        if fetched_data.status_code != 200:
            _logger.warning(
                "BCV provider id=%s: HTTP %s fetching %s",
                self.id,
                fetched_data.status_code,
                BCV_URL,
            )
            return result

        try:
            html_elem = etree.fromstring(fetched_data.content, etree.HTMLParser())
        except Exception:
            _logger.warning(
                "BCV provider id=%s: could not parse HTML (body size=%s)",
                self.id,
                len(fetched_data.content or b""),
                exc_info=True,
            )
            return result

        timestamp = datetime.now(CARACAS_TZ)
        for currency_name in available_currencies:
            try:
                if currency_name in ("Bs", "VES", "VEF", "VED"):
                    result[currency_name] = (1.0, timestamp)
                    continue
                if currency_name not in CURRENCIES:
                    continue
                raw_value = html_elem.xpath(
                    f".//div[@id='{CURRENCIES[currency_name]}']/div/div/div[2]/strong"
                )[0].text
                value = float(raw_value.replace(" ", "").replace(",", "."))
                result[currency_name] = (1.0 / value, timestamp)
            except Exception as err:
                _logger.warning(
                    "BCV provider id=%s: could not read rate for %s: %s",
                    self.id,
                    currency_name,
                    err,
                )

        _logger.info(
            "BCV provider id=%s: scrape OK for currencies %s",
            self.id,
            list(result.keys()),
        )
        return result
