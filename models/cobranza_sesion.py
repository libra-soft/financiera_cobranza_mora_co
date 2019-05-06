# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np

class CobranzaSesion(models.Model):
	_name = 'cobranza.sesion'

	_order = 'id desc'
	name = fields.Char('Nombre')
	fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	current_user = fields.Many2one('res.users','Current User', default=lambda self: self.env.user)
	state = fields.Selection([('borrador', 'Borrador'), ('proceso', 'En proceso'), ('finalizado', 'Finalizado')], string='Estado', readonly=True, default='borrador')
	item_ids = fields.One2many('cobranza.sesion.item', 'cobranza_sesion_id', "Deudores")
	current_item_id = fields.Many2one('cobranza.sesion.item', 'Item actual')
	count_item_historial = fields.Integer('Cantidad de registros de historial')
	# Control time
	process_time = fields.Datetime('Hora de proceso')
	process_minutes = fields.Float('Minutos en proceso', compute='_compute_process_minutes')
	process_time_finish = fields.Datetime('Hora finalizacion de proceso')

	@api.model
	def create(self, values):
		rec = super(CobranzaSesion, self).create(values)
		rec.update({
			'name': 'COBRANZA ' + str(rec.create_uid.id).zfill(6) + '-'  + str(rec.id).zfill(8),
		})
		return rec

	@api.one
	def _compute_process_minutes(self):
		datetimeFormat = '%Y-%m-%d %H:%M:%S'
		date_start = None
		date_finish = datetime.now()
		if self.process_time_finish:
			date_finish = datetime.strptime(self.process_time_finish,datetimeFormat)
		if self.process_time:
			date_start = self.process_time
			start = datetime.strptime(date_start, datetimeFormat)
			finish = date_finish
			result = finish - start
			minutos = result.seconds / 60
			self.process_minutes = minutos
		else:
			self.process_minutes = 0

	def check_finish_current_item(self):
		ret = False
		if len(self.current_item_id.partner_id.cobranza_historial_conversacion_ids) > self.count_item_historial:
			ret = True
		return ret


	def set_finish_current_item(self):
		self.current_item_id.process_time_finish = datetime.now()
		self.current_item_id.estado_id = self.current_item_id.partner_id.cobranza_historial_conversacion_ids[0].estado_id.id
		self.current_item_id.proxima_accion_id = self.current_item_id.partner_id.cobranza_historial_conversacion_ids[0].proxima_accion_id.id
		self.current_item_id.proxima_accion_fecha = self.current_item_id.partner_id.cobranza_historial_conversacion_ids[0].proxima_accion_fecha
		 
	@api.multi
	def siguiente_item(self):
		cr = self.env.cr
		uid = self.env.uid
		deudor_id = None
		if self.state == 'borrador':
			# La sesion va a comenzar
			self.state = 'proceso'
			self.process_time = datetime.now()
			deudor_id = self.pool.get('res.partner').cobranza_siguiente_deudor(cr, uid)
		elif self.state == 'proceso':
			if self.check_finish_current_item():
				self.set_finish_current_item()
				deudor_id = self.pool.get('res.partner').cobranza_siguiente_deudor(cr, uid)
			else:
				deudor_id = self.current_item_id.partner_id
		
		if deudor_id != None:
			# Creamos item de cobranza
			if len(self.current_item_id) == 0 or self.check_finish_current_item():
				csi_values = {
					'cobranza_sesion_id': self.id,
					'partner_id': deudor_id.id,
					'saldo_mora': deudor_id.saldo_mora,
					'process_time': datetime.now(),
				}
				new_item_id = self.env['cobranza.sesion.item'].create(csi_values)
				self.item_ids = [new_item_id.id]
				self.current_item_id = new_item_id.id
				self.count_item_historial = len(deudor_id.cobranza_historial_conversacion_ids)

			action = self.env.ref('financiera_cobranza_mora.cobranza_mora_sesion_action')
			result = action.read()[0]
			form_view = self.env.ref('financiera_cobranza_mora.cobranza_mora_cliente_sesion_form')
			result['views'] = [(form_view.id, 'form')]
			result['res_id'] = deudor_id.id
			result['target'] = 'new'
		else:
			raise ValidationError("No quedan deudores disponibles. Revise la lista de deudores para ver la fecha de la proxima accion.")
			
		return result

	@api.multi
	def editar_item(self):
		action = self.env.ref('financiera_cobranza_mora.cobranza_mora_sesion_action')
		result = action.read()[0]
		form_view = self.env.ref('financiera_cobranza_mora.cobranza_mora_cliente_sesion_form')
		result['views'] = [(form_view.id, 'form')]
		result['res_id'] = self.current_item_id.partner_id.id
		result['target'] = 'new'
		return result


	@api.one
	def finalizar_sesion(self):
		if self.check_finish_current_item():
			self.set_finish_current_item()
			self.process_time_finish = datetime.now()
			self.state = 'finalizado'
		else:
			raise ValidationError("Al Deudor actual no le creo Historial de Conversacion.")

class CobranzaSesionItem(models.Model):
	_name = 'cobranza.sesion.item'

	_order = 'id desc'
	cobranza_sesion_id = fields.Many2one('cobranza.sesion', 'Sesion')
	partner_id = fields.Many2one('res.partner', 'Deudor')
	estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Estado')
	proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	proxima_accion_fecha = fields.Datetime('Fecha')
	saldo_mora = fields.Float('Saldo en mora', digits=(16, 2), readonly=True)
	# Control time
	process_time = fields.Datetime('Hora de proceso')
	process_minutes = fields.Float('Minutos en proceso', compute='_compute_process_minutes')
	process_time_finish = fields.Datetime('Hora finalizacion de proceso')
	
	@api.one
	def _compute_process_minutes(self):
		datetimeFormat = '%Y-%m-%d %H:%M:%S'
		date_start = None
		date_finish = datetime.now()
		if self.process_time_finish:
			date_finish = datetime.strptime(self.process_time_finish,datetimeFormat)
		if self.process_time:
			date_start = self.process_time
			start = datetime.strptime(date_start, datetimeFormat)
			finish = date_finish
			result = finish - start
			minutos = result.seconds / 60
			self.process_minutes = minutos
		else:
			self.process_minutes = 0
