from odoo import api, fields, models


class HrPayrollMinimumSalary(models.Model):
    _name = "hr.payroll.ms"
    _description = "Minimum Salary"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    date = fields.Date(required=True, index=True, default=fields.Date.context_today)
    zone1 = fields.Float(string="Zone 1")
    zone2 = fields.Float(string="Zone 2")
    zone3 = fields.Float(string="Zone 3")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals):
        if "company_id" in vals:
            self = self.with_company(vals["company_id"])
        if "name" in vals:
            vals["name"] = "SMG - " + vals.get("date")
        return super().create(vals)
