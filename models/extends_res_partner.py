# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np


class ExtendsResPartner(models.Model):
	_name = 'res.partner'
	_inherit = 'res.partner'

	cuota_mora_ids = fields.One2many('financiera.prestamo.cuota', 'partner_cuota_mora_id', 'Cuotas en mora')
	saldo_mora = fields.Float('Deuda en mora', digits=(16, 2))
	saldo_total = fields.Float('Deuda total', digits=(16, 2))
	cobranza_historial_conversacion_ids = fields.One2many('cobranza.historial.conversacion', 'partner_id', 'Historial de conversacion')
	cobranza_disponible = fields.Boolean('Disponible', default=True)
	# Estado actual
	cobranza_estado_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Estado')
	cobranza_proxima_accion_id = fields.Many2one('cobranza.historial.conversacion.accion', 'Proxima accion')
	cobranza_proxima_accion_fecha = fields.Datetime('Fecha proxima accion')
	# Estado de mora
	mora_id = fields.Many2one('res.partner.mora', 'Segmento')

	@api.one
	def compute_cuotas_mora(self):
		self.cuota_mora_ids = None
		cuota_obj = self.pool.get('financiera.prestamo.cuota')
		cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
			('partner_id', '=', self.id),
			('state_mora', 'not in', ('preventiva', 'normal')),
			('state', 'in', ('activa', 'judicial', 'incobrable')),
		])
		self.cuota_mora_ids = cuota_ids
		self._saldo_mora()

	@api.one
	def _saldo_mora(self):
		saldo = 0
		for cuota_id in self.cuota_mora_ids:
			saldo += cuota_id.saldo
		self.saldo_mora = saldo

	@api.model
	def cobranza_siguiente_deudor(self):
		cr = self.env.cr
		uid = self.env.uid
		current_user = self.env['res.users'].browse(uid)
		ret_deudor_id = None
		deudor_obj = self.pool.get('res.partner')
		deudor_primera_accion_ids = deudor_obj.search(cr, uid, [
			('saldo_mora', '>', 0),
			('cobranza_disponible', '=', True),
			('cobranza_proxima_accion_fecha', '=', False),
			('company_id', '=', current_user.company_id.id),
		])
		if len(deudor_primera_accion_ids) > 0:
			ret_deudor_id = deudor_obj.browse(cr, uid, deudor_primera_accion_ids[0])
			ret_deudor_id.cobranza_disponible = False
		else:
			date_now = datetime.now()
			deudor_ids = deudor_obj.search(cr, uid, [
				('saldo_mora', '>', 0),
				('cobranza_disponible', '=', True),
				('company_id', '=', current_user.company_id.id),
				('cobranza_proxima_accion_fecha', '<=', str(date_now))
			], order='cobranza_proxima_accion_fecha asc', limit=1)
			if len(deudor_ids) > 0:
				partner_id = deudor_obj.browse(cr, uid, deudor_ids[0])
				ret_deudor_id = partner_id
				ret_deudor_id.cobranza_disponible = False
		return ret_deudor_id

class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	partner_cuota_mora_id = fields.Many2one('res.partner', "Cuota en mora")
