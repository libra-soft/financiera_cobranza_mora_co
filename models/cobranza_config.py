# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime

class FinancieraCobranzaConfig(models.Model):
	_name = 'financiera.cobranza.config'

	name = fields.Char("Nombre")
	fecha = fields.Datetime("Fecha ultima actualizacion")
	id_cobranza_cbu = fields.Integer('Id cobranza CBU')
	mora_ids = fields.One2many('res.partner.mora', "config_id", "Segmentos")
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.config'))
	# Carta Documento
	cd_logo_1 = fields.Binary('CD Logo 1 - carta documento')
	cd_logo_2 = fields.Binary('CD Logo 2 - carta documento')
	cd_logo_3 = fields.Binary('CD Logo 3 - carta documento')
	cd_titulo = fields.Char('CD titulo')
	cd_texto = fields.Text('CD texto')
	cd_saludo = fields.Char('CD saludo')
	# Configuracion Adsus
	# Archivo BNA
	bna_sucursal = fields.Char('BNA cuenta recaudadora sucursal')
	bna_cuenta = fields.Char('BNA cuenta recaudadora numero')
	bna_tipo_moneda = fields.Char('BNA cuenta recaudadora tipo y moneda')
	bna_moneda_movimientos = fields.Char('BNA moneda de movimientos')
	bna_indicador_empleados_bna = fields.Char('BNA indicador empleados BNA')
	# Archivo BAPRO
	bapro_file_name_pre = fields.Char('BAPRO - Pre nombre de archivo')
	bapro_file_name_pos = fields.Char('BAPRO - Pos nombre de archivo')
	bapro_denominacion_pre = fields.Char('BAPRO - Pre deniminacion')
	# Generales
	codigo_servicio_epico = fields.Char('Codigo de servicio Epico')
	
	@api.model
	def _cron_actualizar_deudores(self):
		company_obj = self.pool.get('res.company')
		comapny_ids = company_obj.search(self.env.cr, self.env.uid, [])
		for _id in comapny_ids:
			company_id = company_obj.browse(self.env.cr, self.env.uid, _id)
			if len(company_id.cobranza_config_id) > 0:
				company_id.cobranza_config_id.actualizar_deudores()

	def get_id_cobranza_cbu(self):
		self.id_cobranza_cbu += 1
		return self.id_cobranza_cbu

	@api.one
	def actualizar_deudores(self):
		self.fecha = datetime.now()
		partner_obj = self.pool.get('res.partner')
		partner_ids = partner_obj.search(self.env.cr, self.env.uid, [
			('company_id', '=', self.company_id.id),
			('prestamo_ids.state','!=', 'cancelado'),
			# ('cuota_ids.state','in',['activa']),
			# ('cuota_ids.state_mora','in',['preventiva','moraTemprana','moraMedia','moraTardia','incobrable']),
		])
		# inicializacion
		mora_en_memoria_ids = []
		for mora_id in self.mora_ids:
			mora_en_memoria_ids.append({
				'activo': mora_id.activo,
				'dia_inicial_impago': mora_id.dia_inicial_impago,
				'dia_final_impago':mora_id.dia_final_impago,
				'monto': 0,
				'partner_cantidad': 0,
				'ids': [],
			})
			mora_id.write({
				'monto': 0,
				'partner_cantidad': 0,
				'partner_ids': [(6,0,[])]
			})
		fecha_actual = datetime.now()
		deuda_total = 0.0
		for _id in partner_ids:
			partner_id = partner_obj.browse(self.env.cr, self.env.uid, _id)
			partner_saldo = partner_id.saldo
			partner_id.write({
				'saldo_total': partner_saldo,
				'mora_id': False,
			})
			# Buscamos la cuota activa mas antigua del cliente
			cuota_obj = self.pool.get('financiera.prestamo.cuota')
			cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
				('partner_id', '=', partner_id.id),
				('state','=','activa')
			], order='fecha_vencimiento asc')
			cuota_id = None
			if len(cuota_ids) > 0:
				cuota_id = cuota_obj.browse(self.env.cr, self.env.uid, cuota_ids[0])
				partner_id.proxima_cuota_id = cuota_ids[0]
				fecha_vencimiento = datetime.strptime(cuota_id.fecha_vencimiento, "%Y-%m-%d")
				diferencia = fecha_actual - fecha_vencimiento
				dias = diferencia.days
				for mora_id in mora_en_memoria_ids:
					if mora_id['activo'] and dias >= mora_id['dia_inicial_impago'] and dias <= mora_id['dia_final_impago']:
						deuda_total += partner_saldo
						mora_id['monto'] = mora_id['monto'] + partner_saldo
						mora_id['partner_cantidad'] = mora_id['partner_cantidad'] + 1
						mora_id['ids'].append(partner_id.id)
						break
				partner_id.compute_cuotas_mora()
			else:
				partner_id.write({
					'cuota_mora_ids': [(6, 0, [])],
					'saldo_mora': 0,
				})
		i = 0
		for mora_id in self.mora_ids:
			mora_id.write({
				'monto': mora_en_memoria_ids[i]['monto'],
				'partner_cantidad': mora_en_memoria_ids[i]['partner_cantidad'],
				'partner_ids': [(6,0,mora_en_memoria_ids[i]['ids'])]
			})
			i = i + 1
			if deuda_total > 0:
				mora_id.porcentaje = (mora_id.monto / deuda_total) * 100

class ExtendsResCompany(models.Model):
	_name = 'res.company'
	_inherit = 'res.company'

	cobranza_config_id = fields.Many2one('financiera.cobranza.config', 'Configuracion Cobranza y seguimiento')
	