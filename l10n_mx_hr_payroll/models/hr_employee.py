import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    total_overtime = fields.Float(
        compute="_compute_total_overtime",
        compute_sudo=True,
        groups="hr_attendance.group_hr_attendance_kiosk,hr_attendance.group_hr_attendance,hr.group_hr_user,base.group_user",
    )

    @api.model
    def _names_order_default(self):
        return "first_last"

    @api.model
    def _get_names_order(self):
        """Get names order configuration from system parameters.
        You can override this method to read configuration from language,
        country, company or other"""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("employee_names_order", self._names_order_default())
        )

    @api.model
    def _get_name(self, firstname, lastname, second_lastname):
        order = self._get_names_order()
        if order == "last_first_comma":
            return ", ".join(p for p in (lastname, firstname) if p)
        elif order == "first_last":
            return " ".join(p for p in (firstname, lastname, second_lastname) if p)
        else:
            return " ".join(p for p in (lastname, firstname) if p)

    @api.onchange("firstname", "lastname", "second_lastname")
    def _onchange_firstname_lastname(self):
        if self.firstname or self.lastname or self.second_lastname:
            self.name = self._get_name(
                self.firstname, self.lastname, self.second_lastname
            )

    @api.model_create_multi
    def create(self, vals):
        self._prepare_vals_on_create_firstname_lastname(vals)
        res = super().create(vals)
        return res

    def write(self, vals):
        self._prepare_vals_on_write_firstname_lastname(vals)
        res = super().write(vals)
        return res

    def _prepare_vals_on_create_firstname_lastname(self, vals):
        for val in vals:
            if val.get("firstname") or val.get("lastname"):
                val["name"] = self._get_name(
                    val.get("firstname"),
                    val.get("lastname"),
                    val.get("second_lastname"),
                )
            elif val.get("name"):
                val["lastname"] = self.split_name(val["name"])["lastname"]
                if "second_lastname" in vals:
                    val["second_lastname"] = self.split_name(val["name"])[
                        "second_lastname"
                    ]
                val["firstname"] = self.split_name(val["name"])["firstname"]
            elif val.get("user_id"):
                val["name"] = self.env["res.users"].browse(val.get("user_id")).name
            else:
                raise ValidationError(_("No name set."))

    def _prepare_vals_on_write_firstname_lastname(self, vals):
        if "firstname" in vals or "lastname" in vals or "second_lastname" in vals:
            if "lastname" in vals:
                lastname = vals.get("lastname")
            else:
                lastname = self.lastname
            if "second_lastname" in vals:
                second_lastname = vals.get("second_lastname")
            else:
                second_lastname = self.second_lastname
            if "firstname" in vals:
                firstname = vals.get("firstname")
            else:
                firstname = self.firstname
            vals["name"] = self._get_name(firstname, lastname, second_lastname)
        elif vals.get("name"):
            if "lastname" in vals:
                vals["lastname"] = self.split_name(vals["name"])["lastname"]
            if "second_lastname" in vals:
                vals["second_lastname"] = self.split_name(vals["name"])[
                    "second_lastname"
                ]
            if "firstname" in vals:
                vals["firstname"] = self.split_name(vals["name"])["firstname"]

    @api.model
    def _get_whitespace_cleaned_name(self, name, comma=False):
        """Remove redundant whitespace from :param:`name`.
        Removes leading, trailing and duplicated whitespace.
        """
        try:
            name = " ".join(name.split()) if name else name
        except UnicodeDecodeError:
            name = " ".join(name.decode("utf-8").split()) if name else name

        if comma:
            name = name.replace(" ,", ",").replace(", ", ",")
        return name

    @api.model
    def _get_inverse_name(self, name):
        """Compute the inverted name.
        This method can be easily overriden by other submodules.
        You can also override this method to change the order of name's
        attributes
        When this method is called, :attr:`~.name` already has unified and
        trimmed whitespace.
        """
        order = self._get_names_order()
        # Remove redundant spaces
        name = self._get_whitespace_cleaned_name(
            name, comma=(order == "last_first_comma")
        )
        parts = name.split("," if order == "last_first_comma" else " ", 1)
        if len(parts) > 1:
            if order == "first_last":
                parts = [" ".join(parts[1:]), parts[0]]
            else:
                parts = [parts[0], " ".join(parts[1:])]
        else:
            while len(parts) < 2:
                parts.append(False)
        return {"lastname": parts[0], "firstname": parts[1]}

    @api.model
    def split_name(self, name):
        clean_name = " ".join(name.split(None)) if name else name
        return self._get_inverse_name(clean_name)

    def _inverse_name(self):
        """Try to revert the effect of :meth:`._compute_name`."""
        for record in self:
            parts = self._get_inverse_name(record.name)
            record.lastname = parts["lastname"]
            record.firstname = parts["firstname"]

    @api.model
    def _install_employee_firstname(self):
        """Save names correctly in the database.
        Before installing the module, field ``name`` contains all full names.
        When installing it, this method parses those names and saves them
        correctly into the database. This can be called later too if needed.
        """
        # Find records with empty firstname and lastname
        records = self.search([("firstname", "=", False), ("lastname", "=", False)])

        # Force calculations there
        records._inverse_name()
        _logger.info("%d employees updated installing module.", len(records))

    def _update_partner_firstname(self):
        for employee in self:
            partners = employee.mapped("user_id.partner_id")
            partners |= employee.mapped("address_home_id")
            partners.write(
                {
                    "firstname": employee.firstname,
                    "lastname": employee.lastname,
                    "second_lastname": employee.second_lastname,
                }
            )

    @api.constrains("firstname", "lastname")
    def _check_name(self):
        """Ensure at least one name is set."""
        for record in self:
            if not (record.firstname or record.lastname):
                raise ValidationError(_("No name set."))
