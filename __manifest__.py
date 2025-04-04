# -*- coding: utf-8 -*-

{
    'name': 'PedidosYa Shipping Integration',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'summary': 'Integrate PedidosYa Courier delivery services with Odoo',
    'description': """
    PedidosYa Shipping Integration
    ==============================
    
    This module integrates PedidosYa Courier API services with Odoo.
    Features:
    - Create shipping orders
    - Track shipments
    - Calculate shipping costs
    - Get shipping labels
    - Automatic status updates through webhooks
    - Coverage checks
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['delivery', 'stock', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/delivery_pedidosya_view.xml',
        'views/res_config_settings_views.xml',
        'data/delivery_pedidosya_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}