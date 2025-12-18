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
from collections import defaultdict
from odoo.tools.float_utils import float_round


class AccountTax(models.Model):
    _inherit = 'account.tax'

    margin_tax_bool = fields.Boolean(string='Margin Tax', default=False)

    @api.model
    def _get_tax_totals_summary(self, base_lines, currency, company, cash_rounding=None):
        res = super()._get_tax_totals_summary(base_lines, currency, company, cash_rounding)
        if not res:
            res = {}

        total_base_amount = 0.0
        total_tax_amount = 0.0

        grouped_tax_data = defaultdict(lambda: {
            'tax_amount': 0.0,
            'base_amount': 0.0,
            'tax': None,
        })

        for base_line in base_lines:
            product = base_line.get('product_id')
            price_unit = base_line.get('price_unit', 0.0)
            quantity = base_line.get('quantity', 0.0)

            if not product or not isinstance(product, models.BaseModel):
                continue

            cost = product.standard_price or 0.0
            sale_total = price_unit * quantity
            margin_total = max(price_unit - cost, 0.0) * quantity

            taxes_data = base_line.get('tax_details', {}).get('taxes_data', [])
            line_has_margin_tax = any(t.get('tax') and t['tax'].margin_tax_bool for t in taxes_data)

            line_base_amount = 0.0
            line_tax_amount = 0.0

            for tax_data in taxes_data:
                tax = tax_data.get('tax')
                if not tax:
                    continue

                if tax.margin_tax_bool:
                    tax_rate = tax.amount / 100.0
                    tax_amount = (margin_total * tax_rate) / (1 + tax_rate)
                    base_amount = sale_total - tax_amount - (cost * quantity)

                else:
                    compute_res = tax.compute_all(
                        price_unit,
                        currency=currency,
                        quantity=quantity,
                        product=product,
                        partner=None
                    )
                    tax_amount = compute_res['total_included'] - compute_res['total_excluded']
                    base_amount = compute_res['total_excluded']

                grouped_tax_data[tax.id]['tax_amount'] += tax_amount
                grouped_tax_data[tax.id]['base_amount'] += base_amount
                grouped_tax_data[tax.id]['tax'] = tax

                line_tax_amount += tax_amount

                if tax.margin_tax_bool:
                    line_base_amount = base_amount
                elif not line_has_margin_tax:
                    line_base_amount = base_amount

            subtotal_val = base_line.get('price_subtotal')

            if subtotal_val is None:
                if line_has_margin_tax:
                    subtotal_val = line_base_amount
                else:
                    subtotal_val = sale_total

            total_base_amount += subtotal_val
            total_tax_amount += line_tax_amount

        res.setdefault('subtotals', [])

        subtotal = {
            'name': 'Untaxed Amount',
            'base_amount_currency': total_base_amount,
            'tax_amount_currency': total_tax_amount,
            'base_amount': total_base_amount,
            'tax_amount': total_tax_amount,
            'tax_groups': [],
        }

        for tax_id, tax_data in grouped_tax_data.items():
            if tax_data['tax_amount'] > 0:
                tax = tax_data['tax']
                subtotal['tax_groups'].append({
                    'name': tax.name,
                    'tax_group_name': tax.tax_group_id.name,
                    'group_key': f'tax_group_{tax.tax_group_id.id}',
                    'group_name': tax.tax_group_id.name,
                    'base_amount_currency': tax_data['base_amount'],
                    'tax_amount_currency': tax_data['tax_amount'],
                    'base_amount': tax_data['base_amount'],
                    'tax_amount': tax_data['tax_amount'],
                    'display_base_amount_currency': tax_data['base_amount'],
                    'display_base_amount': tax_data['base_amount'],
                    'involved_tax_ids': [tax.id],
                    'form_class': 'text-muted',
                })

        res['subtotals'] = [subtotal]

        total_sale_margin_tax = 0.0
        total_base_without_margin = 0.0
        total_tax_without_margin = 0.0

        for base_line in base_lines:
            product = base_line.get('product_id')
            quantity = base_line.get('quantity', 0.0)
            price_unit = base_line.get('price_unit', 0.0)
            if not product or not isinstance(product, models.BaseModel):
                continue

            taxes_data = base_line.get('tax_details', {}).get('taxes_data', [])
            line_has_margin_tax = any(t.get('tax') and t['tax'].margin_tax_bool for t in taxes_data)

            sale_total = price_unit * quantity

            if line_has_margin_tax:
                total_sale_margin_tax += sale_total
                
            else:
                line_tax_amount = 0.0
                line_base_amount = base_line.get('price_subtotal', sale_total)

                for t in taxes_data:
                    tax = t.get('tax')
                    if not tax or tax.margin_tax_bool:
                        continue

                    tax_res = tax.compute_all(price_unit, quantity=quantity, product=product, partner=None)
                    if tax.price_include:
                        line_base_amount = tax_res['total_excluded']
                        line_tax_amount += tax_res['total_included'] - tax_res['total_excluded']
                    else:
                        line_tax_amount += tax_res['total_included'] - tax_res['total_excluded']
                total_base_without_margin += line_base_amount
                total_tax_without_margin += line_tax_amount

        res.update({
            'base_amount_currency': total_base_without_margin + total_sale_margin_tax,
            'tax_amount_currency': total_tax_without_margin,
            'total_amount_currency': total_base_without_margin + total_tax_without_margin + total_sale_margin_tax,
            'base_amount': total_base_without_margin + total_sale_margin_tax,
            'tax_amount': total_tax_without_margin,
            'total_amount': total_base_without_margin + total_tax_without_margin + total_sale_margin_tax,
        })

        return res
