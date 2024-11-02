{
    "name": "Payroll EDI for Mexico",
    "icon": "/l10n_mx/static/description/icon.png",
    "summary": "Mexican Localization for Payroll EDI documents",
    "author": "e-maanu, "
    "Open Source Integrators, "
    "Asociacion Mexicana de Odoo (AMOdoo), "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Human Resources/Payroll",
    "version": "17.0.1.0.0",
    "depends": [
        "l10n_mx_edi_40",
        "l10n_mx_hr_payroll",
    ],
    "external_dependencies": {
        "python": ["pyOpenSSL", "zeep"],
    },
    "data": [
        "data/1.2/cfdi.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/hr_payslip.xml",
        "data/account_edi_data.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "development_status": "Beta",
}
