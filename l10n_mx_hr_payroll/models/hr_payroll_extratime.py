import logging

from pytz import timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
tzmx = timezone("America/Mexico_City")


class HrPayrollExtraTime(models.Model):
    _name = "hr.payroll.extratime"
    _description = "Payroll Extratime"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Folio", default="New")
    date = fields.Date()
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    contract_id = fields.Many2one("hr.contract", string="Contract")
    period_id = fields.Many2one("hr.payroll.period", string="Period")
    period_line_id = fields.Many2one("hr.payroll.period.line", string="Period Line")
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")
    line_ids = fields.One2many(
        "hr.payroll.extratime.line", "line_id", string="Extratimes"
    )
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

    # --------------------------------------------------------------------------
    #                Onchange Functions
    # --------------------------------------------------------------------------

    @api.onchange("employee_id")
    def onchange_employee(self):
        for move in self:
            if move.employee_id:
                contract_id = self.env["hr.contract"].search(
                    [("employee_id", "=", move.employee_id.id), ("state", "=", "open")],
                    limit=1,
                )
                move.contract_id = contract_id
                structure_id = self.env["hr.payroll.structure"].search(
                    [("type_id", "=", contract_id.structure_type_id.id)], limit=1
                )
                move.period_id = self.env["hr.payroll.period"].search(
                    [("structure_id", "=", structure_id.id)], limit=1
                )

    @api.onchange("period_line_id")
    def onchange_period_line_id(self):
        for move in self:
            if move.period_line_id:
                move.date_from = move.period_line_id.date_start
                move.date_to = move.period_line_id.date_end

    # --------------------------------------------------------------------------
    #                Main Functions
    # --------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        return result

    def write(self, vals):
        write_result = super().write(vals)
        return write_result

    def unlink(self):
        for move in self:
            if move.state != "draft":
                raise UserError(_("You can not delete this move."))
        return super().unlink()

    def str_to_datetime(self, dt_str, tz=tzmx):
        return tz.localize(fields.Datetime.from_string(dt_str))

    def approved_extratime(self):
        for extratime in self:
            extratime.period_line_id.date_start.strftime("%Y-%m-%d")
            extratime.period_line_id.date_end.strftime("%Y-%m-%d")
            for line in extratime.line_ids:
                if (
                    extratime.period_line_id.date_start <= line.date
                    and extratime.period_line_id.date_end >= line.date
                ):
                    _logger.info("date", line.date)
                else:
                    raise UserError(
                        _(
                            "Some lines have a different date than the selected "
                            "period."
                        )
                    )
                line.state = "approved"
            extratime.name = self.env["ir.sequence"].next_by_code(
                "hr.contract.extratime"
            ) or _("New")
            extratime.state = "approved"

    def done_extratime(self):
        for extratime in self:
            extratime.state = "done"
            return True

    def draft_extratime(self):
        for extratime in self:
            extratime.state = "draft"
            return True

    def cancel_extratime(self):
        for extratime in self:
            extratime.state = "cancel"
            return True
