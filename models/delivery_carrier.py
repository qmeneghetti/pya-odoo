# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import datetime

_logger = logging.getLogger(__name__)

class DeliveryPedidosYa(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('pedidosya', 'PedidosYa')], ondelete={'pedidosya': 'set default'})
    pedidosya_api_key = fields.Char(string='API Key', help='PedidosYa API Key')
    pedidosya_api_secret = fields.Char(string='API Secret', help='PedidosYa API Secret')
    pedidosya_token = fields.Char(string='Auth Token', readonly=True, help='PedidosYa authentication token')
    pedidosya_token_expiry = fields.Datetime(string='Token Expiry', readonly=True)
    pedidosya_environment = fields.Selection([
        ('test', 'Testing'),
        ('prod', 'Production')
    ], string='Environment', default='test')
    pedidosya_service_type = fields.Selection([
        ('EXPRESS', 'Express (ASAP)'),
        ('SCHEDULED', 'Scheduled (Specific time frame)')
    ], string='Service Type', default='EXPRESS')
    pedidosya_webhook_url = fields.Char(string='Webhook URL', help='URL for PedidosYa to send shipping status updates')
    pedidosya_webhook_key = fields.Char(string='Webhook Authorization Key', help='Security key for webhook authentication')
    
    # URLs for API endpoints
    def _get_pedidosya_api_url(self):
        if self.pedidosya_environment == 'test':
            return 'https://courier-api-sandbox.pedidosya.com'
        return 'https://courier-api.pedidosya.com'

    # Authentication method
    def _get_pedidosya_auth_token(self):
        """
        Get authentication token from PedidosYa API
        If token exists and is not expired, return it
        Otherwise, request a new token
        """
        now = fields.Datetime.now()
        if self.pedidosya_token and self.pedidosya_token_expiry and self.pedidosya_token_expiry > now:
            return self.pedidosya_token
            
        url = f"{self._get_pedidosya_api_url()}/v3/authentication/token"
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            'apiKey': self.pedidosya_api_key,
            'apiSecret': self.pedidosya_api_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            token = result.get('access_token')
            
            # Set token expiry to 1 hour from now (assuming PedidosYa tokens last for this duration)
            expiry = now + datetime.timedelta(hours=1)
            
            # Save token and expiry
            self.write({
                'pedidosya_token': token,
                'pedidosya_token_expiry': expiry
            })
            
            return token
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa authentication error: {e}")
            raise UserError(_('Error connecting to PedidosYa: %s') % str(e))
    
    # Check coverage (if shipping is possible)
    def _check_pedidosya_coverage(self, pickup_address, delivery_address):
        """
        Check if PedidosYa covers the shipping route between pickup and delivery addresses
        Returns True if service is available, False otherwise
        """
        token = self._get_pedidosya_auth_token()
        
        # API request to check coverage
        url = f"{self._get_pedidosya_api_url()}/v3/estimates/coverage"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': token
        }
        
        data = {
            "waypoints": [
                {
                    "addressStreet": pickup_address.street,
                    "city": pickup_address.city,
                    "latitude": pickup_address.partner_latitude,
                    "longitude": pickup_address.partner_longitude,
                    "type": "PICK_UP"
                },
                {
                    "addressStreet": delivery_address.street,
                    "city": delivery_address.city,
                    "latitude": delivery_address.partner_latitude,
                    "longitude": delivery_address.partner_longitude,
                    "type": "DROP_OFF"
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            
            # Return True if status is 200 (OK)
            return result.get('status') == 200
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa coverage check error: {e}")
            return False
    
    # Rate shipment method
    def pedidosya_rate_shipment(self, order):
        """Get shipping rate for the order"""
        self.ensure_one()
        
        if not order.partner_shipping_id:
            return {'success': False, 'price': 0.0, 'error_message': _('No shipping address provided'), 'warning_message': False}
        
        # Check if warehouse and shipping address have coordinates
        warehouse_address = order.warehouse_id.partner_id
        shipping_address = order.partner_shipping_id
        
        if not (warehouse_address.partner_latitude and warehouse_address.partner_longitude and 
                shipping_address.partner_latitude and shipping_address.partner_longitude):
            return {'success': False, 'price': 0.0, 'error_message': _('Missing coordinates for warehouse or delivery address'), 'warning_message': False}
        
        # Check if PedidosYa service is available for these addresses
        if not self._check_pedidosya_coverage(warehouse_address, shipping_address):
            return {'success': False, 'price': 0.0, 'error_message': _('PedidosYa delivery service is not available for this route'), 'warning_message': False}
        
        # Get authentication token
        token = self._get_pedidosya_auth_token()
        
        # Prepare request data for shipping estimate
        order_items = []
        for line in order.order_line:
            if line.product_id.type in ['product', 'consu'] and not line.is_delivery:
                item = {
                    'type': line.product_id.pedidosya_product_type or 'STANDARD',
                    'value': line.price_unit * (1 - (line.discount or 0.0) / 100.0),
                    'description': line.product_id.name,
                    'sku': line.product_id.default_code or '',
                    'quantity': int(line.product_uom_qty),
                    'volume': line.product_id.volume * 1000000,  # Convert m³ to cm³
                    'weight': line.product_id.weight  # Weight in kg
                }
                order_items.append(item)
                
        if not order_items:
            return {'success': False, 'price': 0.0, 'error_message': _('No items to ship'), 'warning_message': False}
        
        # API request for shipping estimate
        url = f"{self._get_pedidosya_api_url()}/v3/shippings/estimates"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': token
        }
        
        waypoints = [
            {
                'type': 'PICK_UP',
                'addressStreet': warehouse_address.street or '',
                'addressAdditional': warehouse_address.street2 or '',
                'city': warehouse_address.city or '',
                'latitude': warehouse_address.partner_latitude,
                'longitude': warehouse_address.partner_longitude,
                'phone': warehouse_address.phone or warehouse_address.mobile or '',
                'name': warehouse_address.name,
                'instructions': ''
            },
            {
                'type': 'DROP_OFF',
                'addressStreet': shipping_address.street or '',
                'addressAdditional': shipping_address.street2 or '',
                'city': shipping_address.city or '',
                'latitude': shipping_address.partner_latitude,
                'longitude': shipping_address.partner_longitude,
                'phone': shipping_address.phone or shipping_address.mobile or '',
                'name': shipping_address.name,
                'instructions': ''
            }
        ]
        
        data = {
            'referenceId': order.name,
            'isTest': self.pedidosya_environment == 'test',
            'items': order_items,
            'waypoints': waypoints
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            
            if result.get('deliveryOffers'):
                # Find the delivery offer that matches our service type
                for offer in result.get('deliveryOffers', []):
                    if offer.get('deliveryMode') == self.pedidosya_service_type:
                        pricing = offer.get('pricing', {})
                        price = pricing.get('total', 0.0)
                        return {'success': True, 'price': price, 'error_message': False, 'warning_message': False}
                
                # If specific service not found, use the first offer
                pricing = result.get('deliveryOffers', [{}])[0].get('pricing', {})
                price = pricing.get('total', 0.0)
                return {'success': True, 'price': price, 'error_message': False, 'warning_message': False}
            else:
                return {'success': False, 'price': 0.0, 'error_message': _('No delivery offers available from PedidosYa'), 'warning_message': False}
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa rate calculation error: {e}")
            return {'success': False, 'price': 0.0, 'error_message': _('Error getting shipping rate: %s') % str(e), 'warning_message': False}
    
    # Ship method
    def pedidosya_send_shipping(self, pickings):
        """Create shipping orders in PedidosYa"""
        res = []
        for picking in pickings:
            # Get auth token
            token = self._get_pedidosya_auth_token()
            
            # Get addresses
            warehouse_address = picking.picking_type_id.warehouse_id.partner_id
            customer_address = picking.partner_id
            
            # Prepare items data
            order_items = []
            for move in picking.move_lines:
                item = {
                    'type': move.product_id.pedidosya_product_type or 'STANDARD',
                    'value': move.product_id.list_price,
                    'description': move.product_id.name,
                    'sku': move.product_id.default_code or '',
                    'quantity': int(move.product_uom_qty),
                    'volume': move.product_id.volume * 1000000,  # Convert m³ to cm³
                    'weight': move.product_id.weight  # Weight in kg
                }
                order_items.append(item)
            
            # Prepare waypoints
            waypoints = [
                {
                    'type': 'PICK_UP',
                    'addressStreet': warehouse_address.street or '',
                    'addressAdditional': warehouse_address.street2 or '',
                    'city': warehouse_address.city or '',
                    'latitude': warehouse_address.partner_latitude,
                    'longitude': warehouse_address.partner_longitude,
                    'phone': warehouse_address.phone or warehouse_address.mobile or '',
                    'name': warehouse_address.name,
                    'instructions': ''
                },
                {
                    'type': 'DROP_OFF',
                    'addressStreet': customer_address.street or '',
                    'addressAdditional': customer_address.street2 or '',
                    'city': customer_address.city or '',
                    'latitude': customer_address.partner_latitude,
                    'longitude': customer_address.partner_longitude,
                    'phone': customer_address.phone or customer_address.mobile or '',
                    'name': customer_address.name,
                    'instructions': ''
                }
            ]
            
            # API request to create shipping order
            url = f"{self._get_pedidosya_api_url()}/v3/shippings"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': token
            }
            
            data = {
                'referenceId': picking.name,
                'isTest': self.pedidosya_environment == 'test',
                'items': order_items,
                'waypoints': waypoints
            }
            
            # Add delivery time for scheduled shipments
            if self.pedidosya_service_type == 'SCHEDULED' and picking.scheduled_date:
                # Convert to UTC string format required by PedidosYa
                scheduled_date = fields.Datetime.to_string(picking.scheduled_date)
                data['deliveryTime'] = scheduled_date
            
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data))
                response.raise_for_status()
                result = response.json()
                
                if result.get('shippingId'):
                    tracking_number = result.get('shippingId')
                    confirmation_code = result.get('confirmationCode')
                    tracking_url = result.get('shareLocationUrl')
                    
                    # Save the PedidosYa shipping ID and confirmation code
                    picking.write({
                        'carrier_tracking_ref': tracking_number,
                        'pedidosya_confirmation_code': confirmation_code,
                        'pedidosya_tracking_url': tracking_url
                    })
                    
                    # Calculate the shipping cost
                    shipping_cost = 0.0
                    route = result.get('route', {})
                    if route and route.get('pricing'):
                        shipping_cost = route.get('pricing', {}).get('total', 0.0)
                    
                    msg = _(f"Shipment created in PedidosYa<br/>"
                           f"<b>Shipping ID:</b> {tracking_number}<br/>"
                           f"<b>Confirmation Code:</b> {confirmation_code}<br/>"
                           f"<b>Tracking URL:</b> {tracking_url}")
                    picking.message_post(body=msg)
                    
                    res.append({
                        'exact_price': shipping_cost,
                        'tracking_number': tracking_number,
                        'tracking_url': tracking_url
                    })
                else:
                    error_msg = result.get('message', 'Unknown error')
                    raise UserError(_('Error creating PedidosYa shipment: %s') % error_msg)
                    
            except requests.exceptions.RequestException as e:
                _logger.error(f"PedidosYa shipment creation error: {e}")
                raise UserError(_('Error creating PedidosYa shipment: %s') % str(e))
                
        return res
    
    # Cancel shipment method
    def pedidosya_cancel_shipment(self, pickings):
        """Cancel shipping orders in PedidosYa"""
        for picking in pickings:
            if not picking.carrier_tracking_ref:
                continue
                
            # Get auth token
            token = self._get_pedidosya_auth_token()
            
            # API request to cancel shipment
            url = f"{self._get_pedidosya_api_url()}/v3/shippings/{picking.carrier_tracking_ref}/cancel"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': token
            }
            
            data = {
                'reasonText': _('Canceled from Odoo')
            }
            
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data))
                response.raise_for_status()
                result = response.json()
                
                if result.get('status') == 'CANCELLED':
                    picking.message_post(body=_('Shipment canceled with PedidosYa'))
                else:
                    error_msg = result.get('message', 'Unknown error')
                    raise UserError(_('Error canceling PedidosYa shipment: %s') % error_msg)
                    
            except requests.exceptions.RequestException as e:
                _logger.error(f"PedidosYa shipment cancellation error: {e}")
                raise UserError(_('Error canceling PedidosYa shipment: %s') % str(e))
                
        return True
    
    # Get shipping labels
    def pedidosya_get_shipping_labels(self, pickings):
        """Get shipping labels from PedidosYa"""
        if not pickings:
            return False
            
        shipment_ids = []
        for picking in pickings:
            if picking.carrier_tracking_ref:
                shipment_ids.append(picking.carrier_tracking_ref)
                
        if not shipment_ids:
            raise UserError(_('No valid shipment IDs found for selected pickings'))
            
        # Get auth token
        token = self._get_pedidosya_auth_token()
        
        # API request to get shipping labels
        url = f"{self._get_pedidosya_api_url()}/v3/shippings/labels"
        headers = {
            'Authorization': token
        }
        
        params = {
            'values': ','.join(shipment_ids)
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            # Return PDF content
            return {
                'pdf': response.content,
                'file_name': f"PedidosYa_Labels_{fields.Date.today()}.pdf"
            }
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa label retrieval error: {e}")
            raise UserError(_('Error getting PedidosYa shipping labels: %s') % str(e))
    
    # Tracking method
    def pedidosya_tracking_state_update(self, pickings):
        """Update tracking status from PedidosYa"""
        for picking in pickings:
            if not picking.carrier_tracking_ref:
                continue
                
            # Get auth token
            token = self._get_pedidosya_auth_token()
            
            # API request to get shipping details
            url = f"{self._get_pedidosya_api_url()}/v3/shippings/{picking.carrier_tracking_ref}"
            headers = {
                'Authorization': token
            }
            
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                if result:
                    status = result.get('status')
                    
                    # Update delivery status based on PedidosYa status
                    if status == 'COMPLETED':
                        picking.write({'carrier_tracking_status': 'delivered'})
                    elif status in ['IN_PROGRESS', 'NEAR_PICKUP', 'PICKED_UP', 'NEAR_DROPOFF']:
                        picking.write({'carrier_tracking_status': 'in_transit'})
                    elif status == 'CANCELLED':
                        picking.write({'carrier_tracking_status': 'canceled'})
                    elif status == 'CONFIRMED':
                        picking.write({'carrier_tracking_status': 'waiting'})
                        
                    # Add message with tracking update
                    msg = _(f"Tracking Update from PedidosYa<br/>"
                          f"<b>Status:</b> {status}")
                    picking.message_post(body=msg)
                        
            except requests.exceptions.RequestException as e:
                _logger.error(f"PedidosYa tracking update error: {e}")
                # Don't raise an error, just log it
                
        return True
    
    # Configure webhook for tracking updates
    def pedidosya_configure_webhook(self):
        """Configure PedidosYa webhook for shipping status updates"""
        self.ensure_one()
        
        if not self.pedidosya_webhook_url:
            raise UserError(_('Webhook URL is required to configure webhooks'))
            
        # Get auth token
        token = self._get_pedidosya_auth_token()
        
        # API request to configure webhook
        url = f"{self._get_pedidosya_api_url()}/v3/webhooks-configuration"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': token
        }
        
        data = {
            'webhooksConfiguration': [
                {
                    'isTest': self.pedidosya_environment == 'test',
                    'notificationType': 'WEBHOOK',
                    'topic': 'SHIPPING_STATUS',
                    'urls': [
                        {
                            'url': self.pedidosya_webhook_url,
                            'authorizationKey': self.pedidosya_webhook_key or '',
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.put(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            return True
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"PedidosYa webhook configuration error: {e}")
            raise UserError(_('Error configuring PedidosYa webhook: %s') % str(e))


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    pedidosya_confirmation_code = fields.Char(string='PedidosYa Confirmation Code', readonly=True, copy=False)
    pedidosya_tracking_url = fields.Char(string='PedidosYa Tracking URL', readonly=True, copy=False)