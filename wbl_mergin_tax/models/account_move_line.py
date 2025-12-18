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

from odoo import models, api, fields
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    cost_price = fields.Float(string="Unit Cost", compute="_compute_cost_price", store=True)
    margin = fields.Float(string="Margin", compute='_compute_margin_and_subtotal', store=True)

    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_margin_and_subtotal', store=True)
    price_tax = fields.Monetary(string='Tax (on Margin)', compute='_compute_margin_and_subtotal', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_margin_and_subtotal', store=True)

    @api.depends('product_id')
    def _compute_cost_price(self):
        for line in self:
            line.cost_price = line.product_id.standard_price if line.product_id else 0.0

    @api.depends('quantity', 'price_unit', 'cost_price', 'tax_ids')
    def _compute_margin_and_subtotal(self):
        for line in self:
            quantity = line.quantity or 0.0
            sale_price = line.price_unit or 0.0
            cost_price = line.cost_price or 0.0
            unit_margin = sale_price - cost_price
            total_margin = unit_margin * quantity
            total_price = sale_price * quantity

            has_margin_tax = any(tax.margin_tax_bool for tax in line.tax_ids)

            if has_margin_tax:
                total_tax = 0.0
                for tax in line.tax_ids:
                    if tax.amount_type == 'percent' and tax.margin_tax_bool:
                        tax_rate = tax.amount / 100.0
                        tax_amount = (total_margin * tax_rate) / (1 + tax_rate)
                        total_tax += tax_amount

                line.margin = total_margin
                line.price_tax = total_tax
                cost_tax = cost_price * quantity
                line.price_subtotal = (total_price - total_tax) - (cost_price * quantity)
                line.price_total = line.price_subtotal + total_tax + cost_tax

            else:
                # Default Odoo tax computation
                taxes = line.tax_ids.compute_all(
                    sale_price,
                    line.move_id.currency_id,
                    quantity,
                    product=line.product_id,
                    partner=line.move_id.partner_id
                )
                line.margin = total_margin
                line.price_tax = taxes['total_included'] - taxes['total_excluded']
                line.price_total = taxes['total_included']
                line.price_subtotal = taxes['total_excluded']


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        print("Account Move Line custom logic added!")
        self._check_amount_is_positive()
        invoices = self._create_invoices(self.sale_order_ids)

 # ------------------- Revenue Account (Tax Free Amount Ledger Attach / Adjustment Ledger Attact) ---------------

        for order in self.sale_order_ids:
            for line in order.order_line:
                product_account = line.product_id.revenue_account
                if product_account:
                    account = product_account
                else:
                    # Fallback to account code 4200
                    account = self.env['account.account'].search([('code', '=', '500000')], limit=1)
                    if not account:
                        raise UserError("Expense account not found!")

                print("Using account:", account.name)

    # ------------------- Product Ledger Configer ---------------
        for invoice in invoices:
            if invoice.state == 'draft':
                invoice.action_post()

            total_cost = 0 # Toatal cost calculate

            for line in invoice.invoice_line_ids:
                product = line.product_id
                quantity = line.quantity
                product_cost = product.standard_price
                line_total_cost = product_cost * quantity

                line_total = product_cost * quantity
                total_cost += line_total

                revenue_account = product.property_account_income_id
                if not revenue_account:
                    revenue_account = self.env['account.account'].search([('code', '=', '600000')], limit=1)
                    if not revenue_account:
                        raise UserError(f"Revenue account not found for product {product.name}!")

                # Filter invoice lines using product and dynamic account
                revenue_line = invoice.line_ids.filtered(
                    lambda l: l.product_id == product and l.account_id == revenue_account and l.credit > 0
                )[:1]

                if revenue_line:
                    new_credit = revenue_line.credit - line_total_cost
                    if new_credit < 0:
                        new_credit = 0

                    revenue_line.update({
                        'credit': new_credit,
                        'balance': revenue_line.debit - new_credit,
                    })

                    print(f"Revenue line updated for product {product.name}:",
                          revenue_line.credit, revenue_line.balance)

            self.env['account.move.line'].create({
                'move_id': invoice.id,
                'account_id': account.id,
                'name': 'Custom Adjustment',
                'debit': -total_cost,
                'credit': 0.0,
                'partner_id': invoice.partner_id.id,
                'currency_id': invoice.currency_id.id,
                'date': invoice.invoice_date or fields.Date.today(),
            })

        return self.sale_order_ids.action_view_invoice(invoices=invoices)
