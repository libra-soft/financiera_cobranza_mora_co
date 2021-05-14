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
			# ('cuota_ids.state','=','activa'),
		])
		# inicializacion
		for mora_id in self.mora_ids:
			mora_id.monto = 0
			mora_id.partner_cantidad = 0
		fecha_actual = datetime.now()
		deuda_total = 0.0
		for _id in partner_ids:
			partner_id = partner_obj.browse(self.env.cr, self.env.uid, _id)
			partner_id.saldo_mora = 0
			partner_id.saldo_total = partner_id.saldo
			partner_id.cuota_mora_ids = []
			partner_id.mora_id = False
			primer_cuota_analizada = False
			for cuota_id in partner_id.cuota_ids:
				if cuota_id.state == 'activa':
					fecha_vencimiento = datetime.strptime(cuota_id.fecha_vencimiento, "%Y-%m-%d")
					diferencia = fecha_actual - fecha_vencimiento
					dias = diferencia.days
					if not primer_cuota_analizada:
						primer_cuota_analizada = True
						for mora_id in self.mora_ids:
							if mora_id.activo and dias >= mora_id.dia_inicial_impago and dias <= mora_id.dia_final_impago:
								deuda_total += partner_id.saldo_total
								mora_id.monto += partner_id.saldo_total
								mora_id.partner_cantidad += 1
								partner_id.mora_id = mora_id.id
								break
					if dias > 0:
						partner_id.saldo_mora += cuota_id.saldo
						partner_id.cuota_mora_ids = [cuota_id.id]
					else:
						break
		for mora_id in self.mora_ids:
			if deuda_total > 0:
				mora_id.porcentaje = (mora_id.monto / deuda_total) * 100

class ExtendsResCompany(models.Model):
	_name = 'res.company'
	_inherit = 'res.company'

	cobranza_config_id = fields.Many2one('financiera.cobranza.config', 'Configuracion Cobranza y seguimiento')

