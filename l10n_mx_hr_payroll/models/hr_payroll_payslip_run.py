import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _name = "hr.payslip.run"
    _inherit = ["hr.payslip.run", "mail.thread", "mail.activity.mixin"]

    payroll_type_id = fields.Many2one("hr.payroll.period.type", string="Payroll Type")
    payroll_period_id = fields.Many2one("hr.payroll.period", string="Payroll Period")
    payroll_period_line_id = fields.Many2one(
        "hr.payroll.period.line", string="Payroll Period line"
    )
    structure_id = fields.Many2one("hr.payroll.structure", string="Payroll Structure")
    payment_day = fields.Date()

    @api.onchange("payroll_type_id", "payroll_period_id", "payroll_period_line_id")
    def _onchange_employee(self):
        if (
            (self.payroll_type_id)
            and (self.payroll_period_id)
            and (self.payroll_period_line_id)
        ):
            self.date_start = self.payroll_period_line_id.date_start
            self.date_end = self.payroll_period_line_id.date_end
            self.payment_day = self.payroll_period_line_id.date_pay
            self.structure_id = self.payroll_period_id.structure_id
            self.name = "Payroll [ " + self.payroll_period_line_id.name + " ]"
            return
        return

    def action_validate(self):
        # OVERRIDE
        if self.structure_id.journal_id.edi_format_ids.code != "cfdi_1_2":
            return super().action_validate()
        self.mapped("slip_ids").filtered(
            lambda slip: slip.state != "cancel"
        ).action_payslip_done()
        self.action_close()
        self.payroll_period_line_id.state = "closed"

    def action_stamp_payroll_pac(self):
        self.mapped("slip_ids").filtered(
            lambda slip: slip.state != "cancel"
        ).action_stamp_payroll_pac()
        _logger.info("action_stamp_payroll_pac")
        return

    def confirm_payroll(self):
        # OVERRIDE
        return

    def send_by_email(self):
        # OVERRIDE
        return
