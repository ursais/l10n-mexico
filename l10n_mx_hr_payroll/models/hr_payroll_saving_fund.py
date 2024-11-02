# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models


# Payroll Saving Fund
class HrPayrollSavingFund(models.Model):
    _name = "hr.payroll.saving_fund"
    _description = "Payroll Saving Fund"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)
    employee_id = fields.Many2one("hr.employee")
    date_start = fields.Date()
    date_end = fields.Date()
    notes = fields.Text()
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    def write(self, vals):
        if vals.get("amount"):
            self.message_post(
                body=_(
                    "Payroll Saving Fund has been modify amount with $ <b>%.4f</b>",
                    vals.get("amount"),
                )
            )
        write_result = super(HrPayrollSavingFund, self).write(vals)
        return write_result

    def approved_saving_fund(self):
        for saving_fund in self:
            status = saving_fund.state
            saving_fund.state = "approved"
            self.message_post(
                body=_(
                    "Payroll Saving Fund has been changed <b>%s</b> to Approve status",
                    status,
                )
            )
            return True

    def done_saving_fund(self):
        for saving_fund in self:
            status = saving_fund.state
            saving_fund.state = "done"
            self.message_post(
                body=_(
                    "Payroll Saving fund has been changed <b>%s</b> to Done status",
                    status,
                )
            )
            return True

    def draft_saving_fund(self):
        for saving_fund in self:
            status = saving_fund.state
            saving_fund.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Saving Fund has been changed <b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def cancel_saving_fund(self):
        for saving_fund in self:
            status = saving_fund.state
            saving_fund.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Saving Fund has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
