from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hr_expense_reimbursement_debit_account_id = fields.Many2one(
        "account.account",
        related="company_id.hr_expense_reimbursement_debit_account_id",
        string="Employee reimbursement debit account",
        readonly=False,
    )
    hr_expense_reimbursement_credit_account_id = fields.Many2one(
        "account.account",
        related="company_id.hr_expense_reimbursement_credit_account_id",
        string="Miscellaneous payables - employees",
        readonly=False,
    )
    hr_expense_employee_payment_journal_id = fields.Many2one(
        "account.journal",
        related="company_id.hr_expense_employee_payment_journal_id",
        string="Employee expense payment journal",
        readonly=False,
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
    )
