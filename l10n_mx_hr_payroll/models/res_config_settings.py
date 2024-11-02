# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hr_payroll_smg_l10n_mx = fields.Many2one(
        "hr.payroll.ms",
        related="company_id.hr_payroll_smg_l10n_mx",
        readonly=False,
        string="SMG",
    )
    hr_payroll_uma_l10n_mx = fields.Many2one(
        "hr.payroll.uma",
        related="company_id.hr_payroll_uma_l10n_mx",
        readonly=False,
        string="UMA",
    )
    hr_payroll_umi_l10n_mx = fields.Many2one(
        "hr.payroll.umi",
        related="company_id.hr_payroll_umi_l10n_mx",
        readonly=False,
        string="UMI",
    )
    hr_payroll_email = fields.Char(string="email")
    hr_payroll_email_template = fields.Many2one(
        "mail.template", string="email Template"
    )
    hr_payroll_mx_isr_anual = fields.Boolean("ISR anual")

    employee_names_order = fields.Selection(
        selection="_employee_names_order_selection",
        help="Order to compose employee fullname",
        config_parameter="employee_names_order",
        default=lambda a: a._employee_names_order_default(),
        required=True,
    )
    hr_payroll_settlement_structure_l10n_mx = fields.Many2one(
        "hr.payroll.structure",
        related="company_id.hr_payroll_settlement_structure_l10n_mx",
        readonly=False,
        string="Structure",
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_mx_isr_anual", self.hr_payroll_mx_isr_anual
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_smg_l10n_mx", self.hr_payroll_smg_l10n_mx.id
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_uma_l10n_mx", self.hr_payroll_uma_l10n_mx.id
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_umi_l10n_mx", self.hr_payroll_umi_l10n_mx.id
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_email", self.hr_payroll_email
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_hr_payroll.hr_payroll_email_template",
            self.hr_payroll_email_template.id,
        )
        return

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        value = self.env["ir.config_parameter"].sudo()
        hr_payroll_smg_l10n_mx = value.get_param(
            "l10n_mx_hr_payroll.hr_payroll_smg_l10n_mx"
        )
        hr_payroll_uma_l10n_mx = value.get_param(
            "l10n_mx_hr_payroll.hr_payroll_uma_l10n_mx"
        )
        hr_payroll_umi_l10n_mx = value.get_param(
            "l10n_mx_hr_payroll.hr_payroll_umi_l10n_mx"
        )
        hr_payroll_mx_isr_anual = value.get_param(
            "l10n_mx_hr_payroll.hr_payroll_mx_isr_anual"
        )
        template_id = value.get_param("l10n_mx_hr_payroll.hr_payroll_email_template")
        res.update(
            hr_payroll_smg_l10n_mx=int(hr_payroll_smg_l10n_mx) or False,
            hr_payroll_uma_l10n_mx=int(hr_payroll_uma_l10n_mx) or False,
            hr_payroll_umi_l10n_mx=int(hr_payroll_umi_l10n_mx) or False,
            hr_payroll_mx_isr_anual=hr_payroll_mx_isr_anual or False,
            hr_payroll_email=value.get_param("l10n_mx_hr_payroll.hr_payroll_email")
            or False,
            hr_payroll_email_template=int(template_id) or False,
        )
        return res

    def _employee_names_order_selection(self):
        return [
            ("last_first", "Lastname Firstname Second Lastname"),
            ("last_first_comma", "Lastname, Firstname"),
            ("first_last", "Firstname Lastname"),
        ]

    def _employee_names_order_default(self):
        return self.env["hr.employee"]._names_order_default()
