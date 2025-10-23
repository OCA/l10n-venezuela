import logging
import requests
import pytz
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from lxml import etree
from odoo import fields, models, _
from odoo.exceptions import MissingError

_logger = logging.getLogger(__name__)

TIMEOUT = 5000
MONEDAS = {"USDT": "USDT", "USDC": "USDC"}
URL_BINANCE_P2P = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


class ResCurrencyRateProvider(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("bnb_p2p", "Binance P2P API")],
        ondelete={"bnb_p2p": "set default"},
    )

    p2p_transaction_type = fields.Selection(
        selection=[("BUY", "Buy"), ("SELL", "Sell")], default="BUY", string="P2P Transaction Type"
    )

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != "bnb_p2p":
            return super()._get_supported_currencies()
        return list(MONEDAS.keys())

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "bnb_p2p":
            return super()._obtain_rates(base_currency, currencies, date_from, date_to)

        content = defaultdict(dict)

        bnb_data = {}
        for currency in currencies:
            bnb_data[currency] = self.get_offers_p2p_avg(currency, self.p2p_transaction_type)

        for k, v in bnb_data.items():
            dt = v[1].isoformat()
            content[dt][k] = v[0]

        return content

    def get_offers_p2p_avg(self, to_currency=False, transaction_type="BUY", limit=5):
        if not to_currency:
            raise MissingError(_("You must specify the destination currency to obtain the P2P price."))
        try:
            fiat_currency = self.env.company.currency_id.name

            payload = {
                "fiat": fiat_currency,
                "asset": to_currency,
                "page": 1,
                "rows": limit,
                "payTypes": [],
                "tradeType": transaction_type,
                "publisherType": None,
                "countries": [],
                "proMerchantAds": False,
            }

            response = requests.post(URL_BINANCE_P2P, json=payload, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data and data.get("code") == "000000" and data.get("data"):
                prices = []
                for offer in data["data"]:
                    price_str = offer["adv"]["price"]
                    prices.append(Decimal(price_str))

                if prices:
                    avg_price = sum(prices) / len(prices)

                    return (1.0 / float(avg_price), datetime.now())
                else:
                    raise MissingError(_("No active P2P ads were found for the selected configuration."))
            else:
                raise MissingError(
                    _(f"API response error: {data.get('code', 'N/A')} - {data.get('message', 'No message')}")
                )

        except requests.exceptions.RequestException as e:
            raise MissingError(_(f"Error connecting to Binance P2P API: {e}"))
        except Exception as e:
            raise MissingError(f"Error getting prices to Binance P2P API: {e}")
