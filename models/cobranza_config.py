# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta, date
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import requests

class FinancieraCobranzaConfig(models.Model):
	_name = 'financiera.cobranza.config'

	name = fields.Char("Nombre")
	fecha = fields.Datetime("Fecha ultima actualizacion")
	# promesa_pago_id = fields.Many2one('cobranza.historial.conversacion.estado', 'Estado de promesa de pago')
	mora_ids = fields.One2many('res.partner.mora', "config_id", "Segmentos")
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.config'))
	 
	@api.model
	def _cron_actualizar_deudores(self):
		company_obj = self.pool.get('res.company')
		comapny_ids = company_obj.search(self.env.cr, self.env.uid, [])
		for _id in comapny_ids:
			company_id = company_obj.browse(self.env.cr, self.env.uid, _id)
			if len(company_id.cobranza_config_id) > 0:
				company_id.cobranza_config_id.actualizar_deudores()

	@api.one
	def actualizar_deudores(self):
		self.fecha = datetime.now()
		partner_obj = self.pool.get('res.partner')
		partner_ids = partner_obj.search(self.env.cr, self.env.uid, [
			('company_id', '=', self.company_id.id),
			# ('prestamo_ids.state','in', ['acreditado']),
			# ('cuota_ids.state','in',['activa']),
			# ('cuota_ids.state_mora','in',['preventiva','moraTemprana','moraMedia','moraTardia','incobrable']),
		])
		# inicializacion
		for mora_id in self.mora_ids:
			mora_id.monto = 0
			mora_id.partner_cantidad = 0
			mora_id.partner_ids = [(6, 0, [])]
		fecha_actual = datetime.now()
		deuda_total = 0.0
		for _id in partner_ids:
			partner_id = partner_obj.browse(self.env.cr, self.env.uid, _id)
			partner_id.saldo_total = partner_id.saldo
			partner_id.mora_id = False
			# Buscamos la cuota activa mas antigua del cliente
			cuota_obj = self.pool.get('financiera.prestamo.cuota')
			cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
				('partner_id', '=', partner_id.id),
				('state','=','activa')
			], order='fecha_vencimiento asc')
			cuota_id = None
			if len(cuota_ids) > 0:
				cuota_id = cuota_obj.browse(self.env.cr, self.env.uid, cuota_ids[0])
				fecha_vencimiento = datetime.strptime(cuota_id.fecha_vencimiento, "%Y-%m-%d")
				diferencia = fecha_actual - fecha_vencimiento
				dias = diferencia.days
				for mora_id in self.mora_ids:
					if mora_id.activo and dias >= mora_id.dia_inicial_impago and dias <= mora_id.dia_final_impago:
						deuda_total += partner_id.saldo_total
						mora_id.monto += partner_id.saldo_total
						mora_id.partner_cantidad += 1
						partner_id.mora_id = mora_id.id
						break
			partner_id.compute_cuotas_mora()
		for mora_id in self.mora_ids:
			if deuda_total > 0:
				mora_id.porcentaje = (mora_id.monto / deuda_total) * 100

class ExtendsResCompany(models.Model):
	_name = 'res.company'
	_inherit = 'res.company'

	cobranza_config_id = fields.Many2one('financiera.cobranza.config', 'Configuracion Cobranza y seguimiento')

