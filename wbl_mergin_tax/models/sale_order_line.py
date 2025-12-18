# -*- coding: utf-8 -*-
#
#################################################################################
# Author      : Weblytic Labs Pvt. Ltd. (<https://store.weblyticlabs.com/>)
# Copyright(c): 2023-Present Weblytic Labs Pvt. Ltd.
# All Rights Reserved.
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
##################################################################################

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cost_price = fields.Float(string='Unit Cost', compute='_compute_cost_price', store=True)
    margin = fields.Float(string="Margin", compute='_compute_margin', store=True)
    margin_percent = fields.Float(string="Margin %", compute='_compute_margin', store=True)

    price_tax = fields.Monetary(string='Tax (on Margin)', compute='_compute_amount', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_amount', store=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_amount', store=True)

    @api.depends('product_id')
    def _compute_cost_price(self):
        for line in self:
            line.cost_price = line.product_id.standard_price if line.product_id else 0.0

    @api.depends('price_unit', 'cost_price', 'product_uom_qty')
    def _compute_margin(self):
        for line in self:
            if not line.cost_price:
                line.margin = 0.0
                line.margin_percent = 0.0
                continue

            unit_margin = line.price_unit - line.cost_price
            line.margin = unit_margin * line.product_uom_qty

            if line.price_unit > 0:
                line.margin_percent = (unit_margin / line.price_unit)
            else:
                line.margin_percent = 0.0

    @api.depends('product_uom_qty', 'price_unit', 'cost_price', 'tax_id')
    def _compute_amount(self):
        for line in self:
            qty = line.product_uom_qty or 0.0
            price_unit = line.price_unit or 0.0
            cost_price = line.cost_price or 0.0
            total_price = price_unit * qty

            has_margin_tax = any(tax.margin_tax_bool for tax in line.tax_id)

            if has_margin_tax:
                unit_margin = price_unit - cost_price
                total_margin = unit_margin * qty
                total_tax = 0.0

                for tax in line.tax_id:
                    if tax.amount_type == 'percent' and tax.margin_tax_bool:
                        tax_rate = tax.amount / 100.0
                        tax_amount = (total_margin * tax_rate) / (1 + tax_rate)
                        total_tax += tax_amount

                line.price_tax = total_tax
                line.price_total = total_price
                line.price_subtotal = (total_price - total_tax) - cost_price * qty

            else:
                # Odoo default behavior
                taxes = line.tax_id.compute_all(price_unit, line.order_id.currency_id, qty, product=line.product_id,
                                                partner=line.order_id.partner_id)
                line.price_tax = taxes['total_included'] - taxes['total_excluded']
                line.price_total = taxes['total_included']
                line.price_subtotal = taxes['total_excluded']

    # @api.onchange('product_id')
    # def _onchange_product_id_margin_tax(self):
    #     if self.product_id:
    #         margin_taxes = self.env['account.tax'].search([('margin_tax_bool', '=', True)])
    #         if margin_taxes:
    #             self.tax_id = margin_taxes
    #         else:
    #             fpos = self.order_id.fiscal_position_id
    #             taxes = self.product_id.taxes_id
    #             if fpos:
    #                 taxes = fpos.map_tax(taxes, self.product_id, self.order_id.partner_id)
    #             self.tax_id = taxes

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         product_id = vals.get('product_id')
    #         price_unit = vals.get('price_unit')
    #
    #         if product_id:
    #             product = self.env['product.product'].browse(product_id)
    #
    #             # Check if cost price is zero or less
    #             if product.standard_price <= 0:
    #                 raise ValidationError(
    #                     "You cannot add the product '%s' to the order because its cost price is zero or less." % product.display_name
    #                 )
    #
    #             # Check if cost price is greater than sale price
    #             if price_unit is not None and product.standard_price > price_unit:
    #                 raise ValidationError(
    #                     "You cannot add the product '%s' to the order because its cost price (%.2f) is greater than the sale price (%.2f)." % (
    #                         product.display_name, product.standard_price, price_unit
    #                     )
    #                 )
    #
    #     return super().create(vals_list)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product_id = vals.get('product_id')
            price_unit = vals.get('price_unit')

            if product_id:
                product = self.env['product.product'].browse(product_id)

                if product.standard_price <= 0:
                    margin_taxes = self.env['account.tax'].search([('margin_tax_bool', '=', True)], limit=1)

                    has_margin_tax_applied = bool(product.taxes_id & margin_taxes)

                    if margin_taxes and has_margin_tax_applied:
                        raise ValidationError(
                            "You cannot add the product '%s' to the order because its cost price is zero or less, and it has a margin tax applied." % product.display_name
                        )

                if price_unit is not None and product.standard_price > price_unit:
                    raise ValidationError(
                        "You cannot add the product '%s' to the order because its cost price (%.2f) is greater than the sale price (%.2f)." % (
                            product.display_name, product.standard_price, price_unit
                        )
                    )

        return super().create(vals_list)
