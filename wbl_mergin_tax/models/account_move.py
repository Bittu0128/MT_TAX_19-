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

from odoo import models, api
from collections import defaultdict

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        res = super()._post(soft=soft)

        for move in self:
            if move.move_type != 'out_invoice':
                continue

            # Group data by tax
            tax_data = defaultdict(lambda: {
                'tax': None,
                'total_margin': 0.0,
                'lines': []
            })

            # Step 1: Aggregate margins per tax
            for line in move.invoice_line_ids:
                cost = line.product_id.standard_price * line.quantity
                sale = line.price_unit * line.quantity
                margin = sale - cost
                margin_tax_ids = line.tax_ids.filtered(lambda t: t.margin_tax_bool)

                if margin_tax_ids:
                    for tax in margin_tax_ids:
                        tax_data[tax.id]['tax'] = tax
                        tax_data[tax.id]['total_margin'] += margin
                        tax_data[tax.id]['lines'].append({
                            'line': line,
                            'cost': cost,
                            'sale': sale,
                            'margin': margin
                        })

            # Step 2: Apply tax adjustments once per tax
            for data in tax_data.values():
                tax = data['tax']
                total_margin = data['total_margin']
                tax_rate = tax.amount / 100.0
                total_tax = (total_margin * tax_rate) / (1 + tax_rate)

                # Assign once to tax line
                tax_line = move.line_ids.filtered(lambda l: l.tax_repartition_line_id and l.tax_line_id == tax)
                if tax_line:
                    tax_line = tax_line[0]
                    tax_line.with_context(check_move_validity=False).balance = -total_tax
                    tax_line.debit = 0.0
                    tax_line.credit = total_tax

                # Adjust revenue lines proportionally
                for ldata in data['lines']:
                    line = ldata['line']
                    cost = ldata['cost']
                    sale = ldata['sale']
                    margin = ldata['margin']
                    line_share = margin / total_margin if total_margin else 0.0
                    line_tax = total_tax * line_share

                    revenue_line = move.line_ids.filtered(
                        lambda l: l.account_id.account_type == 'income' and l.name == line.name
                    )
                    for rl in revenue_line:
                        rl.with_context(check_move_validity=False).balance = -(sale - line_tax)
                        rl.debit = 0.0
                        rl.credit = sale - line_tax

        return res
