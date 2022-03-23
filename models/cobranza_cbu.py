# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.exceptions import UserError, ValidationError
from datetime import datetime
import xlwt
import base64
import StringIO

MACRO_DEBITO_MAXIMO = 15000.00
CIUDAD_DEBITO_MAXIMO = 15000.00
ITAU_DEBITO_MAXIMO = 15000.00
BBVA_DEBITO_MAXIMO = 15000.00
class FinancieraCobranzaCbu(models.Model):
	_name = 'financiera.cobranza.cbu'

	_order = 'id desc'
	name = fields.Char("Nombre")
	banco = fields.Selection([
		('011', 'ADSUS BANCO DE LA NACION ARGENTINA'),
		('014', 'ADSUS BANCO DE LA PROVINCIA DE BUENOS AIRES'),
		('285', 'ADSUS BANCO MACRO S.A.'),
		('259', 'ADSUS BANCO ITAU'),
		('017', 'ADSUS BANCO BBVA'),
		('029', 'ADSUS BANCO DE LA CIUDAD DE BUENOS AIRES'),
		# ('083', 'BANCO CHUBUT'),
		# ('097', 'BANCO NEUQUEN'),
	], 'Banco')
	cuota_hasta = fields.Date('Incluir cuotas con fecha hasta')
	partner_suscripto_debito_cbu = fields.Boolean('Cliente suscripto al debito por CBU', default=False)
	partner_incluir_no_debitar = fields.Boolean('Incluir clientes que rechazan debito por CBU', default=False)
	maximo_a_cobrar = fields.Float('Maximo a cobrar de', digits=(16,2))
	debito_partes = fields.Float('Debitar en partes maxima de', digits=(16,2))
	registro_ids = fields.One2many('financiera.cobranza.cbu.registro', 'cobranza_cbu_id', 'Registros')
	state = fields.Selection([
		('borrador', 'Borrador'), ('generado', 'Generado'), ('enviado', 'Enviado'), ('finalizado', 'Finalizado')
	], 'Estado', default='borrador')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.cobranza.cbu'))
	# Generales
	suma_a_cobrar = fields.Float('Suma a cobrar')
	cantidad_impactos = fields.Integer('Cantidad de impactos')
	# BNA
	bna_fecha_inicio_debitos = fields.Date('BNA Fecha de Inicio Débitos')
	bna_fecha_fin_debitos = fields.Date('BNA Fecha de Fin Débitos')
	bna_mes_tope_rendicion = fields.Char('BNA mes tope rendicion', help='Por ej: 08 para agosto, 12 para diciembre.')
	bna_nro_archivo_enviado_mes = fields.Char('BNA nro de archivo enviado en el mes', help='Comenzando por 01', default='01')
	bna_file_debt = fields.Binary('BNA archivo')
	bna_file_debt_name = fields.Char('BNA archivo nombre', default='bna_a_cobrar.txt')
	bna_file_detalle = fields.Binary('BNA archivo de detalle')
	bna_file_detalle_name = fields.Char('BNA archivo de detalle nombre', default='bna_detalle.xls')
	# BAPRO
	bapro_fecha_impacto = fields.Date('BAPRO fecha de impacto')
	bapro_file_debt = fields.Binary('BAPRO archivo')
	bapro_file_debt_name = fields.Char('BAPRO archivo nombre', compute='_compute_bapro_file_debt_name')
	bapro_file_detalle = fields.Binary('BAPRO archivo de detalle')
	bapro_file_detalle_name = fields.Char('BAPRO archivo de detalle nombre', default='bapro_detalle.xls')
	# MACRO
	macro_fecha_inicio = fields.Date('MACRO fecha de inicio Debitos')
	macro_file_debt = fields.Binary('MACRO archivo')
	macro_file_debt_name = fields.Char('MACRO archivo nombre', default='macro_a_cobrar.xls')
	macro_file_detalle = fields.Binary('MACRO archivo de detalle')
	macro_file_detalle_name = fields.Char('MACRO archivo de detalle nombre', default='macro_detalle.xls')
	# CIUDAD
	ciudad_fecha_inicio = fields.Date('CIUDAD primer fecha de Debitos')
	ciudad_fecha_fin = fields.Date('CIUDAD ultima fecha de Debitos')
	ciudad_fecha_impacto_ids = fields.One2many('financiera.cobranza.cbu.fecha', 'cobranza_cbu_id', 'Fechas de impacto')
	ciudad_file_debt = fields.Binary('CIUDAD archivo')
	ciudad_file_debt_name = fields.Char('CIUDAD archivo nombre', default='ciudad_a_cobrar.xls')
	ciudad_file_detalle = fields.Binary('CIUDAD archivo de detalle')
	ciudad_file_detalle_name = fields.Char('CIUDAD archivo de detalle nombre', default='ciudad_detalle.xls')
	# ITAU
	itau_fecha_inicio = fields.Date('ITAU primer fecha de Debitos')
	itau_fecha_fin = fields.Date('ITAU ultima fecha de Debitos')
	itau_file_debt = fields.Binary('ITAU archivo')
	itau_file_debt_name = fields.Char('ITAU archivo nombre', default='itau_a_cobrar.xls')
	itau_file_detalle = fields.Binary('ITAU archivo de detalle')
	itau_file_detalle_name = fields.Char('ITAU archivo de detalle nombre', default='itau_detalle.xls')
	# BBVA
	bbva_fecha_inicio = fields.Date('BBVA primer fecha de Debitos')
	bbva_fecha_fin = fields.Date('BBVA ultima fecha de Debitos')
	bbva_file_debt = fields.Binary('BBVA archivo')
	bbva_file_debt_name = fields.Char('BBVA archivo nombre', default='bbva_a_cobrar.xls')
	bbva_file_detalle = fields.Binary('BBVA archivo de detalle')
	bbva_file_detalle_name = fields.Char('BBVA archivo de detalle nombre', default='bbva_detalle.xls')

	@api.model
	def create(self, values):
		rec = super(FinancieraCobranzaCbu, self).create(values)
		id_cobranza_cbu = self.env.user.company_id.cobranza_config_id.get_id_cobranza_cbu()
		rec.update({
			'name': 'COBRANZA/CBU/' + str(id_cobranza_cbu).zfill(8),
		})
		return rec

	@api.one
	def enviar_a_borrador(self):
		self.state = 'borrador'
		self.bna_file_debt = None
		self.bna_file_detalle = None
		self.bapro_file_debt = None
		self.bapro_file_detalle = None
		self.macro_file_debt = None
		self.macro_file_detalle = None
		# Borramos registros creados
		for registro_id in self.registro_ids:
			registro_id.unlink()


	@api.one
	def enviar_a_enviado(self):
		self.state = 'enviado'

	@api.onchange('bna_fecha_fin_debitos')
	def _onchange_bna_mes_tope_rendicion(self):
		if self.bna_fecha_fin_debitos:
			fecha_tope_rendicion = datetime.strptime(self.bna_fecha_fin_debitos, "%Y-%m-%d")
			self.bna_mes_tope_rendicion = str(fecha_tope_rendicion.month).zfill(2)

	# @api.one
	# def asignar_registros(self):
	# 	self.bna_file_debt = False
	# 	self.bna_file_detalle = False
	# 	self.bapro_file_debt = False
	# 	self.bapro_file_detalle = False
	# 	self.macro_file_debt = False
	# 	self.macro_file_detalle = False
	# 	self.ciudad_file_debt = False
	# 	self.ciudad_file_detalle = False
	# 	self.itau_file_debt = False
	# 	self.itau_file_detalle = False
	# 	self.bbva_file_debt = False
	# 	self.bbva_file_detalle = False
	# 	partner_obj = self.pool.get('res.partner')
	# 	domain = [
	# 		('prestamo_ids.state', 'in', ['acreditado','incobrable']),
	# 		('prestamo_ids.app_cbu', 'like', self.banco+'%')
	# 	]
	# 	partner_ids = partner_obj.search(self.env.cr, self.env.uid, domain)
	# 	partner_ids = partner_obj.browse(self.env.cr, self.env.uid, partner_ids)
	# 	for registro_id in self.registro_ids:
	# 		registro_id.unlink()
	# 	for partner_id in partner_ids:
	# 		partner_cbu = False
	# 		partner_cbu_entidad = False
	# 		partner_cbu_sucursal = False
	# 		partner_cbu_cuenta = False
	# 		monto_a_cobrar = 0
	# 		if self.cuota_hasta:
	# 			cuota_obj = self.pool.get('financiera.prestamo.cuota')
	# 			cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
	# 				('partner_id', '=', partner_id.id),
	# 				('state', '=', 'activa'),
	# 				('fecha_vencimiento', '<=', self.cuota_hasta),
	# 				'|', ('prestamo_id.no_debitar_cbu', '=', False), ('prestamo_id.no_debitar_cbu', '=', self.partner_incluir_no_debitar)
	# 			])
	# 			cuota_ids = cuota_obj.browse(self.env.cr, self.env.uid, cuota_ids)
	# 			for cuota_id in cuota_ids:
	# 				monto_a_cobrar += cuota_id.saldo
	# 				partner_cbu = cuota_id.prestamo_id.app_cbu
	# 			if cuota_ids:
	# 				if not partner_cbu and len(cuota_ids) > 0:
	# 					partner_cbu = cuota_ids[0].prestamo_id.app_cbu
	# 				if partner_cbu and len(partner_cbu) == 22 and partner_cbu[0:3] == self.banco:
	# 					partner_cbu_sucursal = partner_cbu[3:7]
	# 					if self.banco == '011':
	# 						partner_cbu_sucursal = self.env['res.bank.bna.code'].code_bcra_to_bna(partner_cbu_sucursal)
	# 					partner_cbu_cuenta = partner_cbu[11:21]
	# 					fccr_values = {
	# 						'cobranza_cbu_id': self.id,
	# 						'partner_id': partner_id.id,
	# 						'cbu': partner_cbu,
	# 						'sucursal': partner_cbu_sucursal,
	# 						'cuenta': partner_cbu_cuenta,
	# 						'deuda_en_mora': partner_id.saldo_mora,
	# 						# 'proximo_a_vencer': proximo_a_vencer,
	# 						'total': partner_id.saldo,
	# 						'monto_a_cobrar': monto_a_cobrar,
	# 						'debito_partes': self.debito_partes,
	# 					}
	# 					self.env['financiera.cobranza.cbu.registro'].create(fccr_values)

	@api.one
	def asignar_registros(self):
		self.bna_file_debt = False
		self.bna_file_detalle = False
		self.bapro_file_debt = False
		self.bapro_file_detalle = False
		self.macro_file_debt = False
		self.macro_file_detalle = False
		self.ciudad_file_debt = False
		self.ciudad_file_detalle = False
		self.itau_file_debt = False
		self.itau_file_detalle = False
		self.bbva_file_debt = False
		self.bbva_file_detalle = False
		partner_obj = self.pool.get('res.partner')
		domain = [
			('prestamo_ids.state', 'in', ['acreditado','incobrable']),
			('prestamo_ids.app_cbu', 'like', self.banco+'%'),
		]
		partner_ids = partner_obj.search(self.env.cr, self.env.uid, domain)
		partner_ids = partner_obj.browse(self.env.cr, self.env.uid, partner_ids)
		for registro_id in self.registro_ids:
			registro_id.unlink()
		for partner_id in partner_ids:
			monto_a_cobrar_disponible = self.maximo_a_cobrar
			payment_last = False
			for prestamo_id in partner_id.prestamo_ids:
				state_condicion = prestamo_id.state in ('acreditado','incobrable')
				no_debitar_condicion = self.partner_incluir_no_debitar or not prestamo_id.no_debitar_cbu
				cbu_condicion = prestamo_id.app_cbu and len(prestamo_id.app_cbu) == 22 and prestamo_id.app_cbu[0:3] == self.banco
				if state_condicion and no_debitar_condicion and cbu_condicion:
					partner_cbu = prestamo_id.app_cbu
					partner_cbu_sucursal = False
					partner_cbu_cuenta = False
					monto_a_cobrar = 0
					# cuota_obj = self.pool.get('financiera.prestamo.cuota')
					# cuota_ids = cuota_obj.search(self.env.cr, self.env.uid, [
					# 	('prestamo_id', '=', prestamo_id.id),
					# 	('state', '=', 'activa'),
					# 	('fecha_vencimiento', '<=', self.cuota_hasta),
					# ])
					# cuota_ids = cuota_obj.browse(self.env.cr, self.env.uid, cuota_ids)
					cuota_actual = False
					for cuota_id in prestamo_id.cuota_ids:
						if cuota_id.payment_last_id:
							payment_last = cuota_id.payment_last_id.payment_date
						if cuota_id.state == 'activa' and cuota_id.fecha_vencimiento <= self.cuota_hasta:
							monto_a_cobrar += cuota_id.saldo
							if not cuota_actual:
								cuota_actual = True
								ultimos_debitos_mobbex = ""
								i = 0
								for ejecucion_id in cuota_id.mobbex_ejecucion_ids:
									ultimos_debitos_mobbex += ejecucion_id.mobbex_status_code + "|"
									i += 1
									if i > 10:
										break
					if monto_a_cobrar > 0:
						if partner_cbu and len(partner_cbu) == 22:
							partner_cbu_sucursal = partner_cbu[3:7]
							if self.banco == '011':
								partner_cbu_sucursal = self.env['res.bank.bna.code'].code_bcra_to_bna(partner_cbu_sucursal)
							partner_cbu_cuenta = partner_cbu[11:21]
						fccr_values = {
							'cobranza_cbu_id': self.id,
							'partner_id': partner_id.id,
							'prestamo_id': prestamo_id.id,
							'prestamo_no_debitar_cbu': prestamo_id.no_debitar_cbu,
							'cbu': partner_cbu,
							'sucursal': partner_cbu_sucursal,
							'cuenta': partner_cbu_cuenta,
							'total': prestamo_id.saldo,
							'ultimo_cobro': payment_last,
							'ultimos_debitos_mobbex': ultimos_debitos_mobbex,
							'total_vencido': monto_a_cobrar,
							'monto_a_cobrar': min(monto_a_cobrar, monto_a_cobrar_disponible),
							'debito_partes': self.debito_partes,
						}
						self.env['financiera.cobranza.cbu.registro'].create(fccr_values)
						monto_a_cobrar_disponible -= monto_a_cobrar

	# BNA ******************************

	@api.one
	def bna_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		fecha_tope_rendicion = datetime.strptime(self.bna_fecha_fin_debitos, "%Y-%m-%d")
		# Escribimos el encabezado
		encabezado = "1"
		encabezado += cobranza_config_id.bna_sucursal
		encabezado += str(cobranza_config_id.bna_tipo_moneda)
		encabezado += cobranza_config_id.bna_cuenta
		encabezado += str(cobranza_config_id.bna_moneda_movimientos)
		encabezado += "E"
		encabezado += self.bna_mes_tope_rendicion
		encabezado += self.bna_nro_archivo_enviado_mes
		encabezado += str(fecha_tope_rendicion.year)
		encabezado += str(fecha_tope_rendicion.month).zfill(2)
		encabezado += str(fecha_tope_rendicion.day).zfill(2)
		encabezado += str(cobranza_config_id.bna_indicador_empleados_bna)
		encabezado += "".ljust(94, ' ')
		encabezado += "\r\n"
		# encabezado += "\n"
		# Escribimos el encabezado de detalle
		book = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		sheet_detalle = book.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		# Escribimos los registro tipo 2
		registros_tipo_2 = ""
		cantidad_registros_tipo_2 = 0
		total_a_debitar = 0
		for registro_id in self.registro_ids:
			if registro_id.monto_a_cobrar > 0 and registro_id.cbu[0:3] == '011' and registro_id.sucursal and registro_id.cuenta:
				saldo_a_debitar = registro_id.monto_a_cobrar
				while saldo_a_debitar > 0:
					nuevo_registro = "2"
					if len(registro_id.sucursal) == 4:
						nuevo_registro += registro_id.sucursal
					else:
						pass
					# Hardcore CA - Supuestamente siempre sera CA: Caja de Ahorro
					nuevo_registro += "CA"
					# Cuenta a debitar primera posicion 0 y N(10) para Nro de cuenta del cliente
					nuevo_registro += "0"
					if len(registro_id.cuenta) == 10:
							nuevo_registro += registro_id.cuenta
					else:
						pass
					# Importe a debitar N(15) 13,2
					monto_a_debitar = saldo_a_debitar
					if registro_id.debito_partes > 0:
						monto_a_debitar = min(registro_id.debito_partes, monto_a_debitar)
					saldo_a_debitar -= monto_a_debitar
					if monto_a_debitar > 0:
						nuevo_registro += str(monto_a_debitar * 100).split(".")[0].zfill(15)
						total_a_debitar += monto_a_debitar
					else:
						pass
					# Empresa envia 0 N(8) - BNA devuelve fecha de cobro
					nuevo_registro += "00000000"
					# Empresa envia 0 N(1) - BNA devuelve 0 si aplicado
					# 9 si fue rechazado
					nuevo_registro += "0"
					# Empresa envia blancos N(30)
					nuevo_registro += "                              "
					# Empresa campo N(10) de uso interno
					nuevo_registro += str(registro_id.partner_id.id).zfill(10)
					nuevo_registro += "".ljust(46, ' ')
					nuevo_registro += "\r\n"
					registros_tipo_2 += nuevo_registro
					cantidad_registros_tipo_2 += 1
					sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
					sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
					sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
					sheet_detalle.write(row_detalle, 3, monto_a_debitar)
					sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
					sheet_detalle.write(row_detalle, 5, self.bna_fecha_fin_debitos)
					sheet_detalle.write(row_detalle, 6, self.company_id.name)
					row_detalle +=1
					suma_a_cobrar += int(monto_a_debitar)
					cantidad_impactos += 1
		# Un Registro tipo 3
		finalizar = "3"
		# Importe total a debitar N(15) 13,2
		finalizar += str(total_a_debitar * 100).split(".")[0].zfill(15)
		# Cantidad de registros tipo 2 que se envian N(6)
		finalizar += str(cantidad_registros_tipo_2).zfill(6)
		# Empresa envia 0 N(15) - BNA devuelve monto no aplicado
		finalizar += "0".zfill(15)
		# Empresa envia 0 N(6) - BNA cant de reg. no aplicados
		finalizar += "0".zfill(6)
		# Agregamos blancos para cumplicar con los 128 bit a enviar
		finalizar += "".ljust(85, ' ')
		finalizar += "\r\n"
		
		file_read = base64.b64encode((encabezado+registros_tipo_2+finalizar).encode('utf-8'))
		self.bna_file_debt = file_read
		stream_detalle = StringIO.StringIO()
		book.save(stream_detalle)
		self.bna_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	# BAPRO ******************************

	@api.one
	def _compute_bapro_file_debt_name(self):
		name = ''
		cobranza_config_id = self.company_id.cobranza_config_id
		if cobranza_config_id.bapro_file_name_pre:
			name = cobranza_config_id.bapro_file_name_pre
		if self.bapro_fecha_impacto:
			name += str(self.bapro_fecha_impacto)
		if cobranza_config_id.bapro_file_name_pos:
			name += cobranza_config_id.bapro_file_name_pos + '.xls'
		self.bapro_file_debt_name = name
	
	@api.one
	def bapro_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		sheet.write(0, 0, 'Nro. Préstamo')
		sheet.write(0, 1, 'Nro. Cuota')
		sheet.write(0, 2, 'Importe a Cobrar')
		sheet.write(0, 3, 'Sucursal')
		sheet.write(0, 4, 'Nro. Cuenta')
		sheet.write(0, 5, 'Referencia (15 dígitos)')
		sheet.write(0, 6, 'CBU')
		sheet.write(0, 7, 'Nro. Factura')
		sheet.write(0, 8, 'Denominacion')
		row = 1
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		# quantity_format = xlwt.easyxf(num_format_str='#,##0')
		sheet_detalle = book_detalle.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		for registro_id in self.registro_ids:
			id_prestamo = 0
			for prestamo_id in registro_id.partner_id.prestamo_ids:
				if prestamo_id.state == 'acreditado':
					id_prestamo = prestamo_id.name.split('-')[1]
			sheet.write(row, 0, int(id_prestamo))
			id_cuota = 0
			for cuota_id in registro_id.partner_id.cuota_ids:
				if cuota_id.state == 'activa':
					id_cuota = cuota_id.numero_cuota
					break
			sheet.write(row, 1, id_cuota)
			monto_a_cobrar = registro_id.monto_a_cobrar
			if registro_id.debito_partes > 0:
				monto_a_cobrar = min(registro_id.debito_partes, monto_a_cobrar)
			sheet.write(row, 2, int(monto_a_cobrar))
			sheet.write(row, 3, registro_id.sucursal)
			sheet.write(row, 4, registro_id.cuenta)
			sheet.write(row, 5, str(registro_id.id).zfill(15))
			sheet.write(row, 6, registro_id.cbu)
			sheet.write(row, 7, registro_id.partner_id.main_id_number)
			sheet.write(row, 8, cobranza_config_id.bapro_denominacion_pre+str(id_prestamo))
			row +=1
			# detalle
			sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
			sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
			sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
			sheet_detalle.write(row_detalle, 3, int(monto_a_cobrar))
			sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
			sheet_detalle.write(row_detalle, 5, self.bapro_fecha_impacto)
			sheet_detalle.write(row_detalle, 6, self.company_id.name)
			row_detalle +=1
			suma_a_cobrar += int(monto_a_cobrar)
			cantidad_impactos += 1
		book.save(stream)
		self.bapro_file_debt = base64.encodestring(stream.getvalue())
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.bapro_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos
	
	# MACRO ******************************

	@api.one
	def macro_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		sheet.write(0, 0, 'EMPRESA')
		sheet.write(0, 1, 'N°empresa sueldo')
		sheet.write(0, 2, 'Tipo_Banco')
		sheet.write(0, 3, 'Sucursal')
		sheet.write(0, 4, 'Tipo_cuenta')
		sheet.write(0, 5, 'Cuenta')
		sheet.write(0, 6, 'Id_adherente')
		sheet.write(0, 7, 'Id_debito')
		sheet.write(0, 8, 'Fecha_vto')
		sheet.write(0, 9, 'Moneda')
		sheet.write(0, 10, 'Importe')
		sheet.write(0, 11, 'DNI')
		sheet.write(0, 12, 'NOMBRE Y APELLIDO')
		row = 1
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		# quantity_format = xlwt.easyxf(num_format_str='#,##0')
		sheet_detalle = book_detalle.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		for registro_id in self.registro_ids:
			# EMPRESA --> EMPRESA QUE ENVIA EL DEBITO
			sheet.write(row, 0, self.company_id.name.upper())
			# N° EMPRESA SUELDO --> 00000 (FIJO)
			sheet.write(row, 1, "00000")
			# TIPO BANCO --> PRIMEROS 3 DIGITOS DEL CBU
			sheet.write(row, 2, registro_id.cbu[0:3])
			# SUCURSAL --> DIGITO POSICIONES 5, 6 Y 7 DEL CBU
			sheet.write(row, 3, registro_id.cbu[4:7])
			# TIPO CUENTA --> DIGITO POSICION 9 DEL CBU
			sheet.write(row, 4, registro_id.cbu[8])
			# CUENTA --> TIPO DE CUENTA+NUMERO DE SUCURSAL+ELIMINANDO ULTIMO DIGITO LOS 11 NUMEROS ANTERIORES
			sheet.write(row, 5, registro_id.cbu[8]+registro_id.cbu[4:7]+registro_id.cbu[10:21])
			# ID ADHERENTE --> NUMERO DE CBU
			sheet.write(row, 6, registro_id.cbu)
			# ID DEBITO --> 2 letras con las iniciales de la empresa + un numero univoco por línea enviada
			sheet.write(row, 7, self.company_id.name[0:2].upper()+str(registro_id.id))
			# FECHA VTO --> AAAAMMDD
			fecha_inicio = datetime.strptime(self.macro_fecha_inicio, "%Y-%m-%d")
			fecha_inicio_formato = str(fecha_inicio.year)
			fecha_inicio_formato += str(fecha_inicio.month).zfill(2)
			fecha_inicio_formato += str(fecha_inicio.day).zfill(2)
			sheet.write(row, 8, fecha_inicio_formato)
			# MONDA --> 080
			sheet.write(row, 9, "080")
			# IMPORTE --> 13 DIGITOS, ULTIMOS DOS SON DECIMALES (FORMATO EXCEL“PERSONALIZADO”)
			# Macro permite como maximo impacto de 15mil
			monto_a_cobrar = registro_id.monto_a_cobrar
			if registro_id.debito_partes > 0:
				monto_a_cobrar = min(registro_id.debito_partes, monto_a_cobrar)
			sheet.write(row, 10, str(monto_a_cobrar * 100).split('.')[0].zfill(13))
			# Actualizamos monto en el registro!
			registro_id.monto_a_cobrar = monto_a_cobrar
			# DNI --> SIN PUNTOS
			sheet.write(row, 11, registro_id.partner_id.dni)
			# NOMBRE Y APELLIDO --> DEL CLIENTE
			sheet.write(row, 12, registro_id.partner_id.name.upper())
			row +=1
			# detalle
			sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
			sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
			sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
			sheet_detalle.write(row_detalle, 3, int(monto_a_cobrar))
			sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
			sheet_detalle.write(row_detalle, 5, self.macro_fecha_inicio)
			sheet_detalle.write(row_detalle, 6, self.company_id.name)
			row_detalle +=1
			suma_a_cobrar += int(monto_a_cobrar)
			print("monto_a_cobrar: ", monto_a_cobrar)
			cantidad_impactos += 1
			print("cantidad_impactos: ", cantidad_impactos)
		book.save(stream)
		self.macro_file_debt = base64.encodestring(stream.getvalue())
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.macro_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	def sheet_epico_prepare(self, sheet):
		sheet.write(0, 0, 'Campo')
		sheet.write(0, 1, 'Tipo Registro')
		sheet.write(0, 2, 'Tipo Id adherente')
		sheet.write(0, 3, 'Id adherente')
		sheet.write(0, 4, 'Número Referencia')
		sheet.write(0, 5, 'Sexo')
		sheet.write(0, 6, 'Tipo de documento de Identidad')
		sheet.write(0, 7, 'Documento de Identidad')
		sheet.write(0, 8, 'Apellido y Nombre')
		sheet.write(0, 9, 'Fecha nacimiento')
		sheet.write(0, 10, 'Telefono 1')
		sheet.write(0, 11, 'Telefono 2')
		sheet.write(0, 12, 'Domicilio')
		sheet.write(0, 13, 'Localidad')
		sheet.write(0, 14, 'Provincia')
		sheet.write(0, 15, 'Email')
		sheet.write(0, 16, 'Fecha de acreditacion de haberes 1')
		sheet.write(0, 17, 'CUIT Empleador')
		sheet.write(0, 18, 'Empleador')
		sheet.write(0, 19, 'Código Servicio del cliente')
		sheet.write(0, 20, 'Código Medio de Pago')
		sheet.write(0, 21, 'Nro. Cuenta del medio de pago')
		sheet.write(0, 22, 'Código Moneda')
		sheet.write(0, 23, 'Tipo de operación de fecha')
		sheet.write(0, 24, 'Monto Cuota')
		sheet.write(0, 25, 'Fecha de Inicio Débitos')
		sheet.write(0, 26, 'Fecha de Fin Débitos')
		sheet.write(0, 27, 'Reintentos')
		sheet.write(0, 28, 'Fecha Cobro')
		sheet.write(0, 29, 'Monto a Debitar')
		sheet.write(0, 30, 'Fecha Cobro 2')
		sheet.write(0, 31, 'Monto a Debitar 2')
		sheet.write(0, 32, 'Fecha Cobro 3')
		sheet.write(0, 33, 'Monto a Debitar 3')
		sheet.write(0, 34, 'Fecha Cobro 4')
		sheet.write(0, 35, 'Monto a Debitar 4')
		sheet.write(0, 36, 'Fecha Cobro 5')
		sheet.write(0, 37, 'Monto a Debitar 5')
		sheet.write(0, 38, 'Fecha Cobro 6')
		sheet.write(0, 39, 'Monto a Debitar 6')
		sheet.write(0, 40, 'Detalle débito')
		sheet.write(0, 41, 'Información Medio de Pago')

		# sheet.write(1, 0, 'Tamaño')
		# sheet.write(1, 1, '1')
		# sheet.write(1, 2, '1')
		# sheet.write(1, 3, '11')
		# sheet.write(1, 4, '20')
		# sheet.write(1, 5, '1')
		# sheet.write(1, 6, '1')
		# sheet.write(1, 7, '12')
		# sheet.write(1, 8, '255')
		# sheet.write(1, 9, '8')
		# sheet.write(1, 10, '13')
		# sheet.write(1, 11, '13')
		# sheet.write(1, 12, '255')
		# sheet.write(1, 13, '255')
		# sheet.write(1, 14, '255')
		# sheet.write(1, 15, '255')
		# sheet.write(1, 16, '8')
		# sheet.write(1, 17, '13')
		# sheet.write(1, 18, '255')
		# sheet.write(1, 19, '38')
		# sheet.write(1, 20, '1')
		# sheet.write(1, 21, '22')
		# sheet.write(1, 22, '3')
		# sheet.write(1, 23, '1')
		# sheet.write(1, 24, '12')
		# sheet.write(1, 25, '8')
		# sheet.write(1, 26, '8')
		# sheet.write(1, 27, '2')
		# sheet.write(1, 28, '8')
		# sheet.write(1, 29, '12')
		# sheet.write(1, 30, '8')
		# sheet.write(1, 31, '12')
		# sheet.write(1, 32, '8')
		# sheet.write(1, 33, '12')
		# sheet.write(1, 34, '8')
		# sheet.write(1, 35, '12')
		# sheet.write(1, 36, '8')
		# sheet.write(1, 37, '12')
		# sheet.write(1, 38, '8')
		# sheet.write(1, 39, '12')
		# sheet.write(1, 40, '255')
		# sheet.write(1, 41, '255')
		return sheet
	
	# CIUDAD file
	@api.one
	def ciudad_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		self.sheet_epico_prepare(sheet)
		row = 1
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		# quantity_format = xlwt.easyxf(num_format_str='#,##0')
		sheet_detalle = book_detalle.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		cobranza_config_id = self.company_id.cobranza_config_id
		for registro_id in self.registro_ids:
			sheet.write(row, 1, "D")
			sheet.write(row, 2, "D")
			sheet.write(row, 3, registro_id.partner_id.dni)
			sheet.write(row, 4, row)
			# sheet.write(row, 5, registro_id.partner_id.sexo or "")
			sheet.write(row, 6, "D")
			sheet.write(row, 7, registro_id.partner_id.dni)
			sheet.write(row, 8, registro_id.partner_id.name)
			# sheet.write(row, 9, 'Fecha nacimiento')
			# sheet.write(row, 10, 'Telefono 1')
			# sheet.write(row, 11, 'Telefono 2')
			# sheet.write(row, 12, 'Domicilio')
			# sheet.write(row, 13, 'Localidad')
			sheet.write(row, 14, registro_id.partner_id.state_id.name)
			# sheet.write(row, 15, 'Email')
			# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
			# sheet.write(row, 17, 'CUIT Empleador')
			# sheet.write(row, 18, 'Empleador')
			sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
			sheet.write(row, 20, "D")
			sheet.write(row, 21, registro_id.cbu)
			sheet.write(row, 22, "032")
			sheet.write(row, 23, "F")
			# sheet.write(row, 24, 'Monto Cuota') Ignorado para fecha fijo!
			# sheet.write(row, 25, 'Fecha de Inicio Débitos') Ignorado para fecha fijo!
			# sheet.write(row, 26, 'Fecha de Fin Débitos') Ignorado para fecha fijo!
			sheet.write(row, 27, 0) #Reintentos dejamos en cero para fecha fijo!

			fecha_impacto_ids = self.ciudad_fecha_impacto_ids
			if not fecha_impacto_ids:
				raise ValidationError("Falta cargar fechas de impacto!")
			fecha_impacto_len = len(fecha_impacto_ids)
			ciudad_debito_maximo_disponible = registro_id.monto_a_cobrar
			if fecha_impacto_len > 0:
				date = fecha_impacto_ids[0]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 28, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 29, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto

			if fecha_impacto_len > 1:
				date = fecha_impacto_ids[1]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 30, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 31, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto
			
			if fecha_impacto_len > 2:
				date = fecha_impacto_ids[2]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 32, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 33, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto
			
			if fecha_impacto_len > 3:
				date = fecha_impacto_ids[3]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 34, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 35, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto
			
			if fecha_impacto_len > 4:
				date = fecha_impacto_ids[4]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 36, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 37, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto
			
			if fecha_impacto_len > 5:
				date = fecha_impacto_ids[5]
				monto_impacto = min(ciudad_debito_maximo_disponible, date.monto_impacto)
				if monto_impacto > 0:
					date = datetime.strptime(date.fecha_impacto, "%Y-%m-%d")
					sheet.write(row, 38, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2))
					sheet.write(row, 39, monto_impacto*100)
					ciudad_debito_maximo_disponible -= monto_impacto
			
			sheet.write(row, 40, "PRESTAMO")
			# sheet.write(row, 41, 'Información Medio de Pago')
			row +=1
			# detalle
			ciudad_debito_maximo_disponible = min(CIUDAD_DEBITO_MAXIMO, registro_id.monto_a_cobrar)
			for date_id in self.ciudad_fecha_impacto_ids:
				monto_impacto = min(ciudad_debito_maximo_disponible, date_id.monto_impacto)
				if monto_impacto > 0:
					sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
					sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
					sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
					sheet_detalle.write(row_detalle, 3, int(monto_impacto))
					sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
					sheet_detalle.write(row_detalle, 5, self.ciudad_fecha_fin)
					sheet_detalle.write(row_detalle, 6, self.company_id.name)
					row_detalle +=1
					suma_a_cobrar += int(monto_impacto)
					cantidad_impactos += 1
					ciudad_debito_maximo_disponible -= monto_impacto

		book.save(stream)
		self.ciudad_file_debt = base64.encodestring(stream.getvalue())
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.ciudad_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	# ITAU file
	@api.one
	def itau_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		# self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		self.sheet_epico_prepare(sheet)
		row = 1
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		# quantity_format = xlwt.easyxf(num_format_str='#,##0')
		sheet_detalle = book_detalle.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		cobranza_config_id = self.company_id.cobranza_config_id
		for registro_id in self.registro_ids:
			cantidad_a_debitar_disponible = registro_id.monto_a_cobrar
			monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)
			while (monto_impacto > 0):
				sheet.write(row, 1, "D")
				sheet.write(row, 2, "D")
				sheet.write(row, 3, registro_id.partner_id.dni)
				sheet.write(row, 4, row)
				# sheet.write(row, 5, registro_id.partner_id.sexo or "")
				sheet.write(row, 6, "D")
				sheet.write(row, 7, registro_id.partner_id.dni)
				sheet.write(row, 8, registro_id.partner_id.name)
				# sheet.write(row, 9, 'Fecha nacimiento')
				# sheet.write(row, 10, 'Telefono 1')
				# sheet.write(row, 11, 'Telefono 2')
				# sheet.write(row, 12, 'Domicilio')
				# sheet.write(row, 13, 'Localidad')
				sheet.write(row, 14, registro_id.partner_id.state_id.name)
				# sheet.write(row, 15, 'Email')
				# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
				# sheet.write(row, 17, 'CUIT Empleador')
				# sheet.write(row, 18, 'Empleador')
				sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
				sheet.write(row, 20, "D")
				sheet.write(row, 21, registro_id.cbu)
				sheet.write(row, 22, "032")
				sheet.write(row, 23, "B")
				sheet.write(row, 24, monto_impacto*100)
				sheet.write(row, 25, self.itau_fecha_inicio)
				sheet.write(row, 26, self.itau_fecha_fin)
				sheet.write(row, 27, 0) #Reintentos dejamos en cero para fecha fijo!

				# sheet.write(row, 28, "Fecha corbo")
				# sheet.write(row, 29, "Monto a debitar")
				# sheet.write(row, 30, "Fecha cobro 2")
				# sheet.write(row, 31, "Monto a debitar 2")
				# sheet.write(row, 32, "Fecha cobro 3")
				# sheet.write(row, 33, "Monto a debitar 3")
				# sheet.write(row, 34, "Fecha cobro 4")
				# sheet.write(row, 35, "Monto a debitar 4")
				# sheet.write(row, 36, "Fecha cobro 5")
				# sheet.write(row, 37, "Monto a debitar 5")
				# sheet.write(row, 38, "Fecha cobro 6")
				# sheet.write(row, 39, "Monto a debitar 6")
				
				sheet.write(row, 40, "PRESTAMO")
				# sheet.write(row, 41, 'Información Medio de Pago')
				row +=1
				# detalle
				sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
				sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
				sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
				sheet_detalle.write(row_detalle, 3, int(monto_impacto))
				sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
				sheet_detalle.write(row_detalle, 5, self.itau_fecha_fin)
				sheet_detalle.write(row_detalle, 6, self.company_id.name)
				row_detalle +=1
				suma_a_cobrar += int(monto_impacto)
				cantidad_impactos += 1
				cantidad_a_debitar_disponible -= monto_impacto
				monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)

		book.save(stream)
		self.itau_file_debt = base64.encodestring(stream.getvalue())
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.itau_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos


	# BBVA file
	@api.one
	def bbva_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		# self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		if not cobranza_config_id.codigo_referencia_bbva:
			raise ValidationError("Falta configurar Codigo referencia BBVA brindado por ADSUS.")
		if not cobranza_config_id.codigo_servicio_epico:
			raise ValidationError("Falta configurar Codigo de servicio EPICO brindado por ADSUS.")
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		self.sheet_epico_prepare(sheet)
		row = 1
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
		# currency_style = xlwt.XFStyle()
		# currency_style.num_format_str = "[$$-409]#,##0.00;-[$$-409]#,##0.00"
		# quantity_format = xlwt.easyxf(num_format_str='#,##0')
		sheet_detalle = book_detalle.add_sheet(u'Sheet1')
		sheet_detalle.write(0, 0, 'Nombre y apellido')
		sheet_detalle.write(0, 1, 'CUIT/DNI/CUIL')
		sheet_detalle.write(0, 2, 'N° CUENTA')
		sheet_detalle.write(0, 3, 'Importe')
		sheet_detalle.write(0, 4, 'Provincia')
		sheet_detalle.write(0, 5, 'Fecha de corte')
		sheet_detalle.write(0, 6, 'Nombre de la empresa')
		row_detalle = 1
		cobranza_config_id = self.company_id.cobranza_config_id
		for registro_id in self.registro_ids:
			cantidad_a_debitar_disponible = registro_id.monto_a_cobrar
			monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)
			while (monto_impacto > 0):
				sheet.write(row, 1, "D")
				sheet.write(row, 2, "D")
				sheet.write(row, 3, registro_id.partner_id.dni)
				sheet.write(row, 4, cobranza_config_id.codigo_referencia_bbva+'/'+str(row))
				# sheet.write(row, 5, registro_id.partner_id.sexo or "")
				sheet.write(row, 6, "D")
				sheet.write(row, 7, registro_id.partner_id.dni)
				sheet.write(row, 8, registro_id.partner_id.name)
				# sheet.write(row, 9, 'Fecha nacimiento')
				# sheet.write(row, 10, 'Telefono 1')
				# sheet.write(row, 11, 'Telefono 2')
				# sheet.write(row, 12, 'Domicilio')
				# sheet.write(row, 13, 'Localidad')
				sheet.write(row, 14, registro_id.partner_id.state_id.name)
				# sheet.write(row, 15, 'Email')
				# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
				# sheet.write(row, 17, 'CUIT Empleador')
				# sheet.write(row, 18, 'Empleador')
				sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
				sheet.write(row, 20, "D")
				sheet.write(row, 21, registro_id.cbu)
				sheet.write(row, 22, "032")
				sheet.write(row, 23, "B")
				sheet.write(row, 24, monto_impacto*100)
				sheet.write(row, 25, self.bbva_fecha_inicio)
				sheet.write(row, 26, self.bbva_fecha_fin)
				sheet.write(row, 27, 0) #Reintentos dejamos en cero para fecha fijo!

				# sheet.write(row, 28, "Fecha corbo")
				# sheet.write(row, 29, "Monto a debitar")
				# sheet.write(row, 30, "Fecha cobro 2")
				# sheet.write(row, 31, "Monto a debitar 2")
				# sheet.write(row, 32, "Fecha cobro 3")
				# sheet.write(row, 33, "Monto a debitar 3")
				# sheet.write(row, 34, "Fecha cobro 4")
				# sheet.write(row, 35, "Monto a debitar 4")
				# sheet.write(row, 36, "Fecha cobro 5")
				# sheet.write(row, 37, "Monto a debitar 5")
				# sheet.write(row, 38, "Fecha cobro 6")
				# sheet.write(row, 39, "Monto a debitar 6")
				
				sheet.write(row, 40, "PRESTAMO")
				# sheet.write(row, 41, 'Información Medio de Pago')
				row +=1
				# detalle
				sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
				sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
				sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
				sheet_detalle.write(row_detalle, 3, int(monto_impacto))
				sheet_detalle.write(row_detalle, 4, registro_id.partner_id.state_id.name)
				sheet_detalle.write(row_detalle, 5, self.bbva_fecha_fin)
				sheet_detalle.write(row_detalle, 6, self.company_id.name)
				row_detalle +=1
				suma_a_cobrar += int(monto_impacto)
				cantidad_impactos += 1
				cantidad_a_debitar_disponible -= monto_impacto
				monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)

		book.save(stream)
		self.bbva_file_debt = base64.encodestring(stream.getvalue())
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.bbva_file_detalle = base64.encodestring(stream_detalle.getvalue())
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos
class FinancieraCobranzaCbuRegistro(models.Model):
	_name = 'financiera.cobranza.cbu.registro'

	cobranza_cbu_id = fields.Many2one('financiera.cobranza.cbu', 'Cobranza CBU')
	partner_id = fields.Many2one('res.partner', 'Cliente')
	prestamo_id = fields.Many2one('financiera.prestamo', 'Prestamo')
	prestamo_no_debitar_cbu = fields.Boolean('No debitar por CBU', related='prestamo_id.no_debitar_cbu')
	cbu = fields.Char('CBU')
	sucursal = fields.Char('Sucursal')
	cuenta = fields.Char('Cuenta')
	deuda_en_mora = fields.Float('Deuda en mora', digits=(16,2))
	proximo_a_vencer = fields.Float('Proximo a vencer', digits=(16,2))
	ultimo_cobro = fields.Date('Ultimo cobro')
	ultimos_debitos_mobbex = fields.Char("Ultimos debitos Mobbex")
	total = fields.Float('Todas las cuotas', digits=(16,2))
	total_vencido = fields.Float('Total vencido', digits=(16,2))
	monto_a_cobrar = fields.Float('Monto a cobrar', digits=(16,2))
	debito_partes = fields.Float('Debitar en partes maxima de', digits=(16,2))

class FinancieraCobranzaCbuFecha(models.Model):
	_name = 'financiera.cobranza.cbu.fecha'

	cobranza_cbu_id = fields.Many2one('financiera.cobranza.cbu', 'Cobranza ID')
	fecha_impacto = fields.Date('Fecha de impacto')
	monto_impacto = fields.Float('Monto a debitar')