# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    pedidosya_product_type = fields.Selection([
        ('STANDARD', 'Standard'),
        ('FRAGILE', 'Fragile'),
        ('COLD', 'Cold')
    ], string='PedidosYa Product Type', default='STANDARD',
    help='Product type category for PedidosYa Shipping')