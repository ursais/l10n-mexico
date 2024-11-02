# Copyright (C) 2024 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, SUPERUSER_ID

XMLIDS = [
    "l10n_mx_hr_payroll.hr_salary_rule_slyn_groceries",
    "l10n_mx_hr_payroll.hr_salary_rule_slyn_christmas_bonus",
    "l10n_mx_hr_payroll.hr_salary_rule_slyn_liquidaciones_de_savings_fund",
    "l10n_mx_hr_payroll.hr_salary_rule_weekly_10000",
    "l10n_mx_hr_payroll.hr_salary_rule_weekly_sp_10000",
    "l10n_mx_hr_payroll.hr_salary_rule_biweekly_10000",
    "l10n_mx_hr_payroll.hr_salary_rule_biweekly_sp_10000",
    "l10n_mx_hr_payroll.hr_salary_rule_ptu_sp_10000",
    "l10n_mx_hr_payroll.hr_salary_rule_bonus_sp_10000",
]


def _set_account_in_rules(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    rules = env["hr.salary.rule"]
    for xmlid in XMLIDS:
        rules += env.ref(xmlid)
    rules.write(
        {
            "account_credit": env.company.account_journal_payment_credit_account_id.id,
        }
    )
