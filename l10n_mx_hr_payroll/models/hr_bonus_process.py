import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HrBonusProcess(models.Model):
    _name = "hr.bonus.process"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Bonus process"

    name = fields.Char(
        default=lambda self: _("New"),
    )
    date = fields.Date()
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
        return super().create(vals)

    def write(self, vals):
        return super().write(vals)

    def unlink(self):
        return super().unlink()

    @api.depends("date")
    def _compute_new_bonus_process(self):
        for process in self:
            _("")
            process.name = process.date

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

    def approved_bonus_process(self):
        for bonus_process in self:
            if bonus_process.name == _("New"):
                bonus_process.name = self.env["ir.sequence"].next_by_code(
                    "hr.payroll.bonus_process"
                ) or _("New")
            bonus_process.state = "approved"
            self.message_post(
                body=_(
                    "Payroll PTU Process with folio <b>%(ptu_process.name)s</b>\
                        has been changed to Approve status"
                )
            )
            return True

    def done_bonus_process(self):
        for bonus_process in self:
            status = bonus_process.state
            bonus_process.state = "done"
            self.message_post(
                body=_(
                    "Payroll Bonus Process has been changed <b>%s</b> to Done status",
                    status,
                )
            )
            return True

    def draft_bonus_process(self):
        for bonus_process in self:
            status = bonus_process.state
            bonus_process.state = "draft"
            self.message_post(
                body=_(
                    "Payroll Bonus Process has been changed <b>%s</b> to Draft status",
                    status,
                )
            )
            return True

    def cancel_bonus_process(self):
        for bonus_process in self:
            status = bonus_process.state
            bonus_process.state = "cancel"
            self.message_post(
                body=_(
                    "Payroll Bonus Process has been changed <b>%s</b> to Cancel status",
                    status,
                )
            )
            return True
