import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPtuProcess(models.Model):
    _name = "hr.ptu.process"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "PTU process"

    name = fields.Char(
        default=lambda self: _("New"),
    )
    date = fields.Date()
    amount_to_share = fields.Integer()
    payslip_run_id = fields.Many2one("hr.payslip.run", string="Payslip Batch")
    structure_id = fields.Many2one("hr.payroll.structure", string="Structure")
    payslip_count = fields.Integer(compute="_compute_payslip_count")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        default="draft",
    )
    note = fields.Html(string="Notes")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals):
        for values in vals:
            _logger.info(str(values))
            values.get("amount_to_share")
            if "amount_to_share" in values:
                if values.get("amount_to_share") < 1:
                    raise UserError(
                        _("You need to set amount value more than %s")
                        % str(values.get("amount_to_share"))
                    )
        # self.message_post(
        #         body=_(
        #             "Payroll PTU has been modify amount with $ <b>%.4f</b>",
        #             amount_to_share
        #         )
        #     )
        result = super(HrPtuProcess, self).create(vals)
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
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You cannot delete an PTU Process."))
        return super().unlink()

    def _compute_payslip_count(self):
        for payslip_run in self:
            if payslip_run.payslip_run_id:
                payslip_run.payslip_count = len(payslip_run.payslip_run_id.slip_ids)
            else:
                payslip_run.payslip_count = 0

    def action_open_payslips(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [
                [self.payslip_run_id.id, "in", self.payslip_run_id.slip_ids.ids]
            ],
            "context": {"default_payslip_run_id": self.id},
            "name": "Payslips",
        }

    def approved_ptu_process(self):
        for ptu_process in self:
            if ptu_process.name == _("New"):
                ptu_process.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.ptu_process"
                ) or _("New")
            ptu_process.state = "approved"
            self.message_post(
                body=_(
                    "Payroll PTU Process with folio <b>%(ptu_process.name)s</b>\
                        has been changed to Approve status"
                )
            )
            return True

    def done_ptu_process(self):
        for ptu_process in self:
            status = ptu_process.state
            ptu_process.state = "done"
            self.message_post(
                body=_(
                    "Payroll PTU Process has been changed <b>%s</b> to Done status",
                    status,
                )
            )
            return True

    def draft_ptu_process(self):
        for ptu_process in self:
            status = ptu_process.state
            ptu_process.state = "draft"
            self.message_post(
                body=_(
                    "Payroll PTU Process has been changed <b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def cancel_ptu_process(self):
        for ptu_process in self:
            status = ptu_process.state
            ptu_process.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll PTU Process has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
