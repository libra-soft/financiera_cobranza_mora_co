# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np

class CobranzaSesion(models.Model):
	_name = 'cobranza.sesion'

	name = fields.Char('Nombre')
	fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	current_user = fields.Many2one('res.users','Current User', default=lambda self: self.env.user)
	state = fields.Selection([('borrador', 'Borrador'), ('proceso', 'En proceso'), ('finalizado', 'Finalizado')], string='Estado', readonly=True, default='borrador')
	item_ids = fields.One2many('cobranza.sesion.item', 'cobranza_sesion_id', "Deudores")
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

class CobranzaSesionItem(models.Model):
	_name = 'cobranza.sesion.item'

	cobranza_sesion_id = fields.Many2one('cobranza.sesion', 'Sesion')
	partner_id = fields.Many2many('res.partner', 'Deudor')
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
