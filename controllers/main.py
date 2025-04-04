# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import logging
import json
from werkzeug.exceptions import BadRequest, Unauthorized

_logger = logging.getLogger(__name__)

class PedidosYaController(http.Controller):
    
    @http.route('/pedidosya/webhook', type='json', auth='public', csrf=False, methods=['POST'])
    def pedidosya_webhook(self, **kwargs):
        """
        Controller for PedidosYa webhook callbacks
        This receives shipping status updates from PedidosYa
        """
        # Get authorization header
        auth_header = request.httprequest.headers.get('Authorization')
        api_key_header = request.httprequest.headers.get('x-api-key')
        
        # Load JSON data
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON received from PedidosYa webhook: {e}")
            raise BadRequest("Invalid JSON format")
        
        # Validate request
        if not data:
            _logger.error("Empty data received from PedidosYa webhook")
            raise BadRequest("Empty data received")
        
        # Extract fields from data
        topic = data.get('topic')
        shipping_id = data.get('id')
        reference_id = data.get('referenceId')
        confirmation_code = data.get('confirmationCode')
        status_data = data.get('data', {})
        status = status_data.get('status')
        
        # Check required fields
        if not (topic and shipping_id and status):
            _logger.error(f"Missing required fields in PedidosYa webhook data: {data}")
            raise BadRequest("Missing required fields")
        
        # Process only SHIPPING_STATUS topic
        if topic != 'SHIPPING_STATUS':
            _logger.info(f"Ignoring non-shipping status webhook: {topic}")
            return {'status': 'OK'}
        
        # Find carrier by webhook key
        carrier = None
        
        if auth_header or api_key_header:
            auth_key = auth_header or api_key_header
            carrier = request.env['delivery.carrier'].sudo().search([
                ('delivery_type', '=', 'pedidosya'),
                ('pedidosya_webhook_key', '=', auth_key)
            ], limit=1)
        
        # If carrier not found by key, search by reference
        if not carrier and shipping_id:
            picking = request.env['stock.picking'].sudo().search([
                ('carrier_tracking_ref', '=', shipping_id)
            ], limit=1)
            if picking:
                carrier = picking.carrier_id
        
        # Handle shipping status update
        if shipping_id:
            picking = request.env['stock.picking'].sudo().search([
                ('carrier_tracking_ref', '=', shipping_id)
            ], limit=1)
            
            if picking:
                # Update picking status based on PedidosYa status
                if status == 'COMPLETED':
                    picking.sudo().write({'carrier_tracking_status': 'delivered'})
                    # If picking is not done, mark it as done
                    if picking.state != 'done':
                        picking.sudo().with_context(tracking_disable=False).button_validate()
                elif status in ['IN_PROGRESS', 'NEAR_PICKUP', 'PICKED_UP', 'NEAR_DROPOFF']:
                    picking.sudo().write({'carrier_tracking_status': 'in_transit'})
                elif status == 'CANCELLED':
                    picking.sudo().write({'carrier_tracking_status': 'canceled'})
                    # Add cancel reason if provided
                    cancel_reason = status_data.get('cancelReason', '')
                    cancel_code = status_data.get('cancelCode', '')
                    if cancel_reason or cancel_code:
                        picking.sudo().message_post(
                            body=_(f"PedidosYa shipment canceled<br/>"
                                  f"Reason: {cancel_reason}<br/>"
                                  f"Code: {cancel_code}")
                        )
                elif status == 'CONFIRMED':
                    picking.sudo().write({'carrier_tracking_status': 'waiting'})
                
                # Add message with status update
                picking.sudo().message_post(
                    body=_(f"PedidosYa Status Update: {status}")
                )
                
                _logger.info(f"Updated picking {picking.name} with PedidosYa status: {status}")
                
                return {'status': 'OK'}
            else:
                _logger.warning(f"Picking not found for PedidosYa shipping ID: {shipping_id}")
                return {'status': 'OK'}
        
        return {'status': 'OK'}