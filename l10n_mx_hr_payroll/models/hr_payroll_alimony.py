from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayrollAlimony(models.Model):
    _name = "hr.payroll.alimony"
    _description = "Payroll Alimony"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Folio",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    date_start = fields.Date(
        required=True,
        tracking=True,
    )
    date_end = fields.Date()
    proceeding = fields.Char(
        tracking=True,
    )
    folio = fields.Char(
        tracking=True,
    )
    beneficiary = fields.Char(
        required=True,
        tracking=True,
    )
    amount = fields.Float(
        string="amount / Percent",
        required=True,
        tracking=True,
    )
    amount_anual_increase = fields.Float(string="Amount for annual increase")
    payment_method = fields.Many2one("account.payment.method", required=True)
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, tracking=True
    )
    payslip_input_id = fields.Many2one(
        "hr.payslip.input.type",
        string="Input Alimony Rule",
        required=True,
        tracking=True,
    )
    payment_ids = fields.One2many(
        "hr.payroll.alimony.line", "line_id", string="Payment Lines"
    )
    amount_type = fields.Selection(
        [
            ("percent", "Percent"),
            ("amount_fixed", "Amount fixed"),
        ],
        string="Type of discount",
        tracking=True,
        default="percent",
    )
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

    @api.model_create_multi
    def create(self, vals):
        if "company_id" in vals:
            self = self.with_company(vals["company_id"])
        if "amount" in vals:
            if vals.get("amount") < 1:
                raise UserError(
                    _("You need to set amount value more than %s")
                    % str(vals.get("amount"))
                )
            if vals.get("amount") > 99.00 and vals.get("amount_type") == "percent":
                raise UserError(
                    _("You can not create an alimony with %s percent")
                    % str(vals.get("amount"))
                )
        result = super().create(vals)
        return result

    def write(self, vals):
        if vals.get("amount"):
            self.message_post(
                body=_(
                    "Payroll alimony has been modify amount with $ <b>%.4f</b>",
                    vals.get("amount"),
                )
            )
        return super().write(vals)

    def unlink(self):
        for _rec in self:
            raise UserError(_("You cannot delete an alimony movement."))
        return super().unlink()

    def approved_alimony(self):
        for alimony in self:
            if alimony.name == _("New"):
                alimony.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.alimony"
                ) or _("New")
            alimony.state = "approved"
            self.message_post(
                body=_(
                    "Payroll Alimony with folio <b>%(alimony.name)s</b> has "
                    "been changed <b>%(status)s</b> to Approve status."
                )
            )
            return True

    def done_alimony(self):
        for alimony in self:
            status = alimony.state
            alimony.state = "done"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Done status", status
                )
            )
            return True

    def draft_alimony(self):
        for alimony in self:
            status = alimony.state
            alimony.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Draft status", status
                )
            )
            return True

    def cancel_alimony(self):
        for alimony in self:
            status = alimony.state
            alimony.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
