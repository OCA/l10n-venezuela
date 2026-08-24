{
    "name": "Venezuela Bank Statement Import",
    "summary": "Importación de estados de cuenta bancarios para Venezuela",
    "version": "18.0.1.4.1",
    "category": "Accounting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "account_statement_import_sheet_file",
    ],
    "data": [
        "data/map_data.xml",
        "views/account_statement_import_sheet_mapping_views.xml",
    ],
    "installable": True,
}
