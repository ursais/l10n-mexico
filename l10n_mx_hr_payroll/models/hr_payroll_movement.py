from odoo import _, api, fields, models


class HrPayrollMovement(models.Model):
    _name = "hr.payroll.movement"
    _description = "Payroll Movement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Description", required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date()
    payslip_input_id = fields.Many2one(
        "hr.payslip.input.type", string="Payslip Input", required=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    line_ids = fields.One2many(
        "hr.payroll.movement.line", "line_id", string="Movement Lines"
    )
    movements_count = fields.Integer(compute="_compute_movements_count")
    amount = fields.Float(string="Import")
    note = fields.Text(string="Notes")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )

    @api.onchange("payslip_input_id")
    def _onchange_payslip_input(self):
        for move in self:
            self.name = move.payslip_input_id.name

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

    def _compute_movements_count(self):
        for movements in self:
            movements.movements_count = len(movements.line_ids)

    def action_open_payroll_movements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payroll.movement.line",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", self.line_ids.ids]],
            "name": "Payroll Movements",
        }

    def approved_movement(self):
        for movement in self:
            status = movement.state
            for movement_line in movement.line_ids:
                movement_line.state = "approved"
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
            for movement_line in movement.line_ids:
                movement_line.state = "done"
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
            for movement_line in movement.line_ids:
                movement_line.state = "draft"
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
            for movement_line in movement.line_ids:
                movement_line.state = "cancel"
            movement.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Alimony has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
