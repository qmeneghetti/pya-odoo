# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import requests
import datetime

_logger = logging.getLogger(__name__)

class PedidosYaWebhookConfig(models.Model):
    _name = 'pedidosya.webhook.config'
    _description = 'PedidosYa Webhook Configuration'
    
    name = fields.Char(string='Name', required=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Delivery Carrier', 
                                  domain=[('delivery_type', '=', 'pedidosya')],
                                  required=True)
    webhook_url = fields.Char(string='Webhook URL', required=True, 
                              help='URL that PedidosYa will call to send shipping status updates')
    webhook_key = fields.Char(string='Authorization Key', 
                              help='Security key for webhook authentication')
    is_test = fields.Boolean(string='Test Environment', 
                             help='If checked, this webhook is configured for the testing environment')
    active = fields.Boolean(string='Active', default=True)
    last_sync = fields.Datetime(string='Last Synchronization', readonly=True)
    
    @api.onchange('carrier_id')
    def _onchange_carrier_id(self):
        """Update webhook URL and key when carrier changes"""
        if self.carrier_id:
            self.webhook_url = self.carrier_id.pedidosya_webhook_url
            self.webhook_key = self.carrier_id.pedidosya_webhook_key
            self.is_test = self.carrier_id.pedidosya_environment == 'test'
    
    def sync_to_pedidosya(self):
        """Synchronize webhook configuration to PedidosYa"""
        self.ensure_one()
        
        if not self.webhook_url:
            raise UserError(_('Webhook URL is required to configure webhooks'))
            
        # Get auth token
        token = self.carrier_id._get_pedidosya_auth_token()
        
        # API request to configure webhook
        url = f"{self.carrier_id._get_pedidosya_api_url()}/v3/webhooks-configuration"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': token
        }
        
        data = {
            'webhooksConfiguration': [
                {
                    'isTest': self.is_test,
                    'notificationType': 'WEBHOOK',
                    'topic': 'SHIPPING_STATUS',
                    'urls': [
                        {
                            'url': self.webhook_url,
                            'authorizationKey': self.webhook_key or '',
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.put(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            # Update last sync time
            self.write({'last_sync': fields.Datetime.now()})
            
            # Update carrier configuration
            self.carrier_id.write({
                'pedidosya_webhook_url': self.webhook_url,
                'pedidosya_webhook_key': self.webhook_key
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Webhook configuration successfully synchronized with PedidosYa'),
                    'sticky': False,
                    'type': 'success',
                }
            }
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa webhook configuration error: {e}")
            raise UserError(_('Error configuring PedidosYa webhook: %s') % str(e))
    
    def sync_from_pedidosya(self):
        """Get webhook configuration from PedidosYa"""
        self.ensure_one()
        
        # Get auth token
        token = self.carrier_id._get_pedidosya_auth_token()
        
        # API request to get webhook configuration
        url = f"{self.carrier_id._get_pedidosya_api_url()}/v3/webhooks-configuration"
        headers = {
            'Authorization': token
        }
        
        params = {
            'isTest': self.is_test
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            result = response.json()
            
            webhook_configs = result.get('webhooksConfiguration', [])
            for config in webhook_configs:
                if config.get('topic') == 'SHIPPING_STATUS':
                    urls = config.get('urls', [])
                    if urls:
                        url_config = urls[0]
                        webhook_url = url_config.get('url')
                        webhook_key = url_config.get('authorizationKey')
                        
                        if webhook_url:
                            self.write({
                                'webhook_url': webhook_url,
                                'webhook_key': webhook_key,
                                'last_sync': fields.Datetime.now()
                            })
                            
                            # Update carrier configuration
                            self.carrier_id.write({
                                'pedidosya_webhook_url': webhook_url,
                                'pedidosya_webhook_key': webhook_key
                            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Webhook configuration successfully retrieved from PedidosYa'),
                    'sticky': False,
                    'type': 'success',
                }
            }
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa webhook retrieval error: {e}")
            raise UserError(_('Error retrieving PedidosYa webhook configuration: %s') % str(e))