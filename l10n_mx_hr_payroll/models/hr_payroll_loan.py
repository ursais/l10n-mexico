# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models


# Payroll Loans
class HrPayrollLoan(models.Model):
    _name = "hr.payroll.loan"
    _description = "Payroll loan"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="_New")
    date_start = fields.Date(required=True)
    date_end = fields.Date()
    total_amount = fields.Float()
    total_paid = fields.Float()
    amount = fields.Float(required=True)
    periods = fields.Integer()
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    employee_id = fields.Many2one("hr.employee", required=True)
    loan_type_mx = fields.Many2one("hr.payslip.input.type", required=True)
    payment_ids = fields.One2many("hr.payroll.loan.line", "line_id")
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    def approved_loan(self):
        for loan in self:
            if loan.name == "_New":
                loan.name = self.env["ir.sequence"].next_by_code("hr.payroll.loan")
            status = loan.state
            loan.state = "approved"
            self.message_post(
                body=_(
                    "Payroll Loan has been changed <b>%s</b> to approve status", status
                )
            )
            return True

    def done_loan(self):
        for loan in self:
            status = loan.state
            loan.state = "done"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to done status", status
                )
            )
            return True

    def draft_loan(self):
        for loan in self:
            status = loan.state
            loan.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to draft status", status
                )
            )
            return True

    def cancel_loan(self):
        for loan in self:
            status = loan.state
            loan.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to cancel status",
                    status,
                )
            )
            return True

    @api.model_create_multi
    def create(self, vals_list):
        loans = super().create(vals_list)
        return loans

    def write(self, vals):
        if vals.get("amount"):
            self.message_post(
                body=_(
                    "Payroll loan has been modify amount with $ <b>%.4f</b>",
                    vals.get("amount"),
                )
            )
        write_result = super().write(vals)
        return write_result
