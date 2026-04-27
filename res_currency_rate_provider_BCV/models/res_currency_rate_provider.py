import logging
from collections import defaultdict

import requests
from lxml import etree

from odoo import fields, models, _

_logger = logging.getLogger(__name__)

# Constants
TIMEOUT = 60
BCV_URL = "https://www.bcv.org.ve/"
MONEDAS_MAP = {
    "EUR": "euro",
    "CNY": "yuan",
    "TRY": "lira",
    "RUB": "rublo",
    "USD": "dolar",
    "VES": "bolivar",
}

class ResCurrencyRateProvider(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("bcv", "Central Bank of Venezuela (BCV)")],
        ondelete={"bcv": "set default"},
    )

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != "bcv":
            return super()._get_supported_currencies()
        return list(MONEDAS_MAP.keys())

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "bcv":
            return super()._obtain_rates(base_currency, currencies, date_from, date_to)

        content = defaultdict(dict)

        # Use company/user context date (UTC conversion handled by Odoo)
        # BCV Only return current value of currency rates
        today_str = fields.Date.to_string(fields.Date.context_today(self))
        
        # 1. Fetch prices from BCV (Price of 1 Unit in VES)
        # Result example: {'USD': 484.74, 'EUR': 567.40, 'VES': 1.0}
        bcv_data = self._scrap_bcv()
        
        # 2. Determine the price of our Odoo Base Currency in VES
        # If Odoo Base is USD, this will be ~484.74
        # If Odoo Base is VES, this will be 1.0
        base_currency_name = base_currency.name if hasattr(base_currency, 'name') else base_currency
        base_price_in_ves = bcv_data.get(base_currency_name)
        
        # Critical Check: If the base currency is not in BCV data
        # we can't calculate cross-rates.
        if not base_price_in_ves:
            _logger.error("Base currency %s not found in BCV data. Rates available: %s", 
                         base_currency_name, list(bcv_data.keys()))
            return content

        for iso_code in currencies:
            if iso_code == base_currency_name:
                continue
                
            target_price_in_ves = bcv_data.get(iso_code)
            if not target_price_in_ves or target_price_in_ves <= 0:
                _logger.warning("Currency %s not found in BCV scraping", iso_code)
                continue

            # --- THE UNIVERSAL FORMULA ---
            # Odoo Rate = (Amount of Target Currency) / (1 Unit of Base Currency)
            # Since everything is in VES:
            # Rate = Base_VES_Price / Target_VES_Price

            rate_value = base_price_in_ves / target_price_in_ves
            content[today_str][iso_code] = rate_value

        return content

    def _scrap_bcv(self):
        rslt = {}

        try:
            # First attempt with SSL verification enabled
            response = requests.get(BCV_URL, verify=True, timeout=TIMEOUT)
            response.raise_for_status()

        except requests.exceptions.SSLError:
            # BCV nodes often have misconfigured SSL chains or expired certificates.
            # Since this is the only legally binding source for exchange rates in Venezuela,
            # we fallback to unverified requests to ensure service availability.
            _logger.warning("SSL Verification failed for BCV. Retrying without verification...")
            response = requests.get(BCV_URL, verify=False, timeout=TIMEOUT)

        except Exception as e:
            _logger.error("Could not connect to BCV: %s", e)
            return rslt

        try:
            tree = etree.HTML(response.content)

        except Exception as e:
            _logger.error("Error parsing BCV HTML: %s", e)
            return rslt

        for code in MONEDAS_MAP.keys():
            if code == "VES":
                rslt[code] = 1.0
                continue
                
            moneda_id = MONEDAS_MAP.get(code)
            if not moneda_id:
                continue
                
            try:
                ################################################################
                # If BCV website DOM changed, this is the line you need update #
                ################################################################
                xpath_query = f"//div[@id='{moneda_id}']//strong"

                element = tree.xpath(xpath_query)
                if element and element[0].text:
                    raw_val = element[0].text.strip()
                    clean_val = raw_val.replace(".", "").replace(",", ".")
                    rslt[code] = float(clean_val)

            except Exception:
                continue

        return rslt
