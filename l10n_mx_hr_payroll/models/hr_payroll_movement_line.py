from odoo import _, fields, models


class HrPayrollMovementLine(models.Model):
    _name = "hr.payroll.movement.line"
    _description = "Payroll Movement - Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    line_id = fields.Many2one(
        "hr.payroll.movement", string="Movement", ondelete="cascade"
    )
    multi_form = fields.Boolean(string="Multi_Form")
    name = fields.Char(required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date()
    payslip_input_id = fields.Many2one(
        "hr.payslip.input.type", string="Payslip Input", required=True
    )
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    amount = fields.Float(string="Import", required=True)
    total_amount = fields.Float(string="Total Import")
    final_amount = fields.Float(string="Final Import")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
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
                    "Payroll movement has been modify amount with $ <b>%.4f</b>",
                    vals.get("amount"),
                )
            )
        write_result = super().write(vals)
        return write_result

    def approved_movement(self):
        for movement in self:
            status = movement.state
            movement.state = "approved"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Approve status",
                    status,
                )
            )
            return True

    def done_movement(self):
        for movement in self:
            status = movement.state
            movement.state = "done"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Done status", status
                )
            )
            return True

    def draft_movement(self):
        for movement in self:
            status = movement.state
            movement.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Draft status", status
                )
            )
            return True

    def cancel_movement(self):
        for movement in self:
            status = movement.state
            movement.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
