from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    hr_expense_reimbursement_debit_account_id = fields.Many2one(
        "account.account",
        string="Employee reimbursement debit account",
        domain=[("deprecated", "=", False)],
        help="Account used for the debit line on employee reimbursement bills.",
    )
    hr_expense_reimbursement_credit_account_id = fields.Many2one(
        "account.account",
        string="Miscellaneous payables - employees",
        domain=[("deprecated", "=", False)],
        help="Account used for the credit line on employee reimbursement bills.",
    )
    hr_expense_employee_payment_journal_id = fields.Many2one(
        "account.journal",
        string="Employee expense payment journal",
        check_company=True,
        domain="[('type', '=', 'bank'), ('company_id', '=', id)]",
        help=(
            "Bank journal used to pay vendors when an employee expense "
            "report is posted."
        ),
    )
