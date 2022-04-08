# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.exceptions import UserError, ValidationError
from datetime import datetime
import xlwt
import base64
import StringIO

BNA_COBRO_NOMBRE = 'bna_a_cobrar.txt'
BNA_DETALLE_NOMBRE = 'bna_detalle.xls'
BAPRO_DETALLE_NOMBRE = 'bapro_detalle.xls'
MACRO_COBRO_NOMBRE = 'macro_a_cobrar.xls'
MACRO_DETALLE_NOMBRE = 'macro_detalle.xls'
CIUDAD_COBRO_NOMBRE = 'ciudad_a_cobrar.xls'
CIUDAD_DETALLE_NOMBRE = 'ciudad_detalle.xls'
ITAU_COBRO_NOMBRE = 'itau_a_cobrar.xls'
ITAU_DETALLE_NOMBRE = 'itau_detalle.xls'
BBVA_COBRO_NOMBRE = 'bbva_a_cobrar.xls'
BBVA_DETALLE_NOMBRE = 'bbva_detalle.xls'
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
	archivo_cobro = fields.Binary('Archivo de cobro')
	archivo_cobro_nombre = fields.Char('Nombre del archivo de cobro')
	archivo_detalle = fields.Binary('Archivo de detalle')
	archivo_detalle_nombre = fields.Char('Nombre del archivo de detalle')
	suma_a_cobrar = fields.Float('Suma a cobrar')
	cantidad_impactos = fields.Integer('Cantidad de impactos')
	# BNA
	bna_fecha_inicio_debitos = fields.Date('BNA Fecha de Inicio Débitos')
	bna_fecha_fin_debitos = fields.Date('BNA Fecha de Fin Débitos')
	bna_mes_tope_rendicion = fields.Char('BNA mes tope rendicion', help='Por ej: 08 para agosto, 12 para diciembre.')
	bna_nro_archivo_enviado_mes = fields.Char('BNA nro de archivo enviado en el mes', help='Comenzando por 01', default='01')
	# BAPRO
	bapro_fecha_impacto = fields.Date('BAPRO fecha de impacto')
	# MACRO
	macro_fecha_inicio = fields.Date('MACRO fecha de inicio Debitos')
	# CIUDAD
	ciudad_fecha_inicio = fields.Date('CIUDAD primer fecha de Debitos')
	ciudad_fecha_fin = fields.Date('CIUDAD ultima fecha de Debitos')
	ciudad_fecha_impacto_ids = fields.One2many('financiera.cobranza.cbu.fecha', 'cobranza_cbu_id', 'Fechas de impacto')
	# ITAU
	itau_fecha_inicio = fields.Date('ITAU primer fecha de Debitos')
	itau_fecha_fin = fields.Date('ITAU ultima fecha de Debitos')
	# BBVA
	bbva_fecha_inicio = fields.Date('BBVA primer fecha de Debitos')
	bbva_fecha_fin = fields.Date('BBVA ultima fecha de Debitos')

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
		self.archivo_cobro = None
		self.archivo_cobro_nombre = None
		self.archivo_detalle = None
		self.archivo_detalle_nombre = None
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

	@api.one
	def asignar_registros(self):
		self.enviar_a_borrador()
		partner_obj = self.pool.get('res.partner')
		domain = [
			('company_id', '=', self.company_id.id),
			('prestamo_ids.state', 'in', ['acreditado','incobrable']),
			('prestamo_ids.app_cbu', 'like', self.banco+'%'),
		]
		partner_ids = partner_obj.search(self.env.cr, self.env.uid, domain)
		partner_ids = partner_obj.browse(self.env.cr, self.env.uid, partner_ids)
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

	@api.one
	def all_stop_debito_automatico(self):
		for registro_id in self.registro_ids:
			registro_id.stop_debito_automatico()
	
	@api.one
	def all_allow_debito_automatico(self):
		for registro_id in self.registro_ids:
			registro_id.allow_debito_automatico()

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
		self.archivo_cobro = file_read
		self.archivo_cobro_nombre = BNA_COBRO_NOMBRE
		stream_detalle = StringIO.StringIO()
		book.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = BNA_DETALLE_NOMBRE
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	# BAPRO ******************************

	@api.one
	def get_bapro_name(self):
		name = ''
		cobranza_config_id = self.company_id.cobranza_config_id
		if cobranza_config_id.bapro_file_name_pre:
			name = cobranza_config_id.bapro_file_name_pre
		if self.bapro_fecha_impacto:
			name += str(self.bapro_fecha_impacto)
		if cobranza_config_id.bapro_file_name_pos:
			name += cobranza_config_id.bapro_file_name_pos + '.xls'
		self.archivo_cobro_nombre = name
	
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
		self.archivo_cobro = base64.encodestring(stream.getvalue())
		self.get_bapro_name()
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = BAPRO_DETALLE_NOMBRE
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
			cantidad_impactos += 1
		book.save(stream)
		self.archivo_cobro = base64.encodestring(stream.getvalue())
		self.archivo_cobro_nombre = MACRO_COBRO_NOMBRE
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = MACRO_DETALLE_NOMBRE
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	def sheet_epico_prepare(self, sheet):
		sheet.write(0, 3, 'Alta de Ordenes de debito')

		firstColStyle = xlwt.easyxf(
			'pattern:pattern solid, fore_colour light_orange;'
			'font: name Calibri, height 160;'
			'border: top thin, bottom thin, left thin, right thin;')
		requiredStyle = xlwt.easyxf(
			'pattern: pattern solid, fore_colour coral;'
			'align: vert top;'
			'font: name Calibri, height 160;'
			'border: top thin, bottom thin, left thin, right thin;')
		greenStyle = xlwt.easyxf(
			'pattern: pattern solid, fore_colour light_green;'
			'align: vert top;'
			'font: name Calibri, height 160;'
			'border: top thin, bottom thin, left thin, right thin;')
		
		sheet.write(1, 0, 'Observaciones', style=firstColStyle)
		sheet.col(0).width = int(3600)
		sheet.write(1, 1, 'Mandatorio.\nIndicador de tipo de registro. \nValor Fijo "D".', style=requiredStyle)
		sheet.col(1).width = int(5000)
		sheet.write(1, 2, 'Mandatorio.\nTipo de identificador fiscal del adherente.\n(C,T,D)', style=requiredStyle)
		sheet.col(2).width = int(5000)
		sheet.write(1, 3, 'Mandatorio. \nIdentificador fiscal del adherente.\n(Ingresar sin guiones)', style=requiredStyle)
		sheet.col(3).width = int(5000)
		sheet.write(1, 4, 'Mandatorio. \nIdentificador unívoco de la operación.\nÚnico por cada orden de debito.', style=requiredStyle)
		sheet.col(4).width = int(5000)
		sheet.write(1, 5, 'Opcional.\nAdmite 2 valores posibles: \nM (Masculino) o F (Femenino)', style=greenStyle)
		sheet.col(5).width = int(5000)
		sheet.write(1, 6, 'Mandatorio.\nTipo de documento del adherente. (D, L, C, P)', style=requiredStyle)
		sheet.col(6).width = int(5000)
		sheet.write(1, 7, 'Mandatorio.\nNúmero de documento del adherente.', style=requiredStyle)
		sheet.col(7).width = int(5000)
		sheet.write(1, 8, 'Mandatorio.\nNombre y apellido del cliente.', style=requiredStyle)
		sheet.col(8).width = int(5000)
		sheet.write(1, 9, 'Opcional.\nFecha de nacimiento del cliente.', style=greenStyle)
		sheet.col(9).width = int(5000)
		sheet.write(1, 10, 'Opcional.\nTeléfono del cliente.', style=greenStyle)
		sheet.col(10).width = int(5000)
		sheet.write(1, 11, 'Opcional.', style=greenStyle)
		sheet.col(11).width = int(5000)
		sheet.write(1, 12, 'Opcional.\nCalle + Nro', style=greenStyle)
		sheet.col(12).width = int(5000)
		sheet.write(1, 13, 'Opcional.\nLocalidad del domicilio del cliente.', style=greenStyle)
		sheet.col(13).width = int(5000)
		sheet.write(1, 14, 'Mandatorio.\nProvincia del domicilio del cliente.', style=requiredStyle)
		sheet.col(14).width = int(5000)
		sheet.write(1, 15, 'Opcional.\nDirección de correo electrónico.', style=greenStyle)
		sheet.col(15).width = int(5000)
		sheet.write(1, 16, 'Opcional.\nFecha conocida de cobro de haberes', style=greenStyle)
		sheet.col(16).width = int(5000)
		sheet.write(1, 17, 'Opcional.\nCUIT del empleador.', style=greenStyle)
		sheet.col(17).width = int(5000)
		sheet.write(1, 18, 'Mandatorio.\nRazón social del empleador.', style=requiredStyle)
		sheet.col(18).width = int(5000)
		sheet.write(1, 19, 'Mandatorio.\nIdentificador del servicio subscripto a utilizar. \nUTILIZAR EL PROVISTO POR EPICO', style=requiredStyle)
		sheet.col(19).width = int(5000)
		sheet.write(1, 20, 'Mandatorio.\nIdentificador del medio de pago:\nD = debito en cuenta,\nT = Tarjeta de crédito, \nP = Presencial.', style=requiredStyle)
		sheet.col(20).width = int(5000)
		sheet.write(1, 21, 'Mandatorio.\nEl número de la cuenta. Según el medio de pago se interpreta como CBU, Número de tarjeta o Código de Pago presencial', style=requiredStyle)
		sheet.col(21).width = int(5000)
		sheet.write(1, 22, 'Mandatorio.\nCódigo ISO de la moneda de cobro.\nSe debe completar con un 0 a izquierda. Ej: "032"', style=requiredStyle)
		sheet.col(22).width = int(5000)
		sheet.write(1, 23, 'Mandatorio. \nEspecifica si el cálculo de fecha de cobro es variable o fijo:\nF = Fijo\nB = Barrido.', style=requiredStyle)
		sheet.col(23).width = int(5000)
		sheet.write(1, 24, 'Mandatorio.\nMonto de cada cuota.\nLos 2 últimos dígitos corresponden a los decimales.\nCampo ignorado para cálculo de fecha fijo', style=requiredStyle)
		sheet.col(24).width = int(5000)
		sheet.write(1, 25, 'Mandatorio.\nFecha de inicio de periodo de reintentos para un tipo de operación de fecha variable o fijas\nSi el tipo de operación es variable o Barrido, será la fecha de inicio del periodo de débitos.\nFormato AAAAMMDD', style=requiredStyle)
		sheet.col(25).width = int(5000)
		sheet.write(1, 26, 'Mandatorio para Barrido.\nSi el tipo de operación es Variable o Barrido, será la fecha de fin del periodo de débitos.\nFecha de fin del Período a Debitar.\nFormato AAAAMMDD', style=requiredStyle)
		sheet.col(26).width = int(5000)
		sheet.write(1, 27, 'Mandatorio para Fecha Fija. \nCantidad de intentos.\nEn caso de no querer reintentos informar 0 o dejar vacío.', style=requiredStyle)
		sheet.col(27).width = int(5000)
		sheet.write(1, 28, 'Mandatorio para Fecha Fija / Opcional Fecha Variable o barrido. \nFecha de Débito Informada por Cliente.\nEn barrido es una fecha por la cual el proceso deberá calendarizar un intento.', style=requiredStyle)
		sheet.col(28).width = int(5000)
		sheet.write(1, 29, 'Mandatorio. \nImporte a Debitar en la Fecha de Cobro.\nÚltimos 2 números se consideran decimales.\nNo ingresar ni puntos ni comas.', style=requiredStyle)
		sheet.col(29).width = int(5000)
		sheet.write(1, 30, 'Opcional.\nIndica una segunda fecha de reintento.', style=greenStyle)
		sheet.col(30).width = int(5000)
		sheet.write(1, 31, 'Opcional. \nSolo si existe Fecha de Cobro 2.', style=greenStyle)
		sheet.col(31).width = int(5000)
		sheet.write(1, 32, 'Opcional.\nIndica una tercera fecha de reintento.', style=greenStyle)
		sheet.col(32).width = int(5000)
		sheet.write(1, 33, 'Opcional. \nSolo si existe Fecha de Cobro 3.', style=greenStyle)
		sheet.col(33).width = int(5000)
		sheet.write(1, 34, 'Opcional.\nIndica una cuarta fecha de reintento.', style=greenStyle)
		sheet.col(34).width = int(5000)
		sheet.write(1, 35, 'Opcional. \nSolo si existe Fecha de Cobro 4.', style=greenStyle)
		sheet.col(35).width = int(5000)
		sheet.write(1, 36, 'Opcional.\nIndica una quinta fecha de reintento.', style=greenStyle)
		sheet.col(36).width = int(5000)
		sheet.write(1, 37, 'Opcional. \nSolo si existe Fecha de Cobro 5.', style=greenStyle)
		sheet.col(37).width = int(5000)
		sheet.write(1, 38, 'Opcional.\nIndica una sexta fecha de reintento.', style=greenStyle)
		sheet.col(38).width = int(5000)
		sheet.write(1, 39, 'Opcional. \nSolo si existe Fecha de Cobro 6.', style=greenStyle)
		sheet.col(39).width = int(5000)
		sheet.write(1, 40, 'Mandatorio. \nDetalle si el producto es un Préstamo o Servicio.  S: SERVICIO // P: PRESTAMO - No se admiten otros valores o campo vacío', style=requiredStyle)
		sheet.col(40).width = int(5000)
		sheet.write(1, 41, 'Opcional. \nInformación adicional dependiente del medio de pago.\nPresente sólo si el medio de pago requiere información adicional.', style=greenStyle)
		sheet.col(41).width = int(5000)

		sheet.write(2, 0, 'Campo', style=firstColStyle)
		sheet.write(2, 1, 'Tipo Registro', style=greenStyle)
		sheet.write(2, 2, 'Tipo Id adherente', style=greenStyle)
		sheet.write(2, 3, 'Id adherente', style=greenStyle)
		sheet.write(2, 4, 'Número Referencia', style=greenStyle)
		sheet.write(2, 5, 'Sexo', style=greenStyle)
		sheet.write(2, 6, 'Tipo de documento de Identidad', style=greenStyle)
		sheet.write(2, 7, 'Documento de Identidad', style=greenStyle)
		sheet.write(2, 8, 'Apellido y Nombre', style=greenStyle)
		sheet.write(2, 9, 'Fecha nacimiento', style=greenStyle)
		sheet.write(2, 10, 'Telefono 1', style=greenStyle)
		sheet.write(2, 11, 'Telefono 2', style=greenStyle)
		sheet.write(2, 12, 'Domicilio', style=greenStyle)
		sheet.write(2, 13, 'Localidad', style=greenStyle)
		sheet.write(2, 14, 'Provincia', style=greenStyle)
		sheet.write(2, 15, 'Email', style=greenStyle)
		sheet.write(2, 16, 'Fecha de acreditacion de haberes 1', style=greenStyle)
		sheet.write(2, 17, 'CUIT Empleador', style=greenStyle)
		sheet.write(2, 18, 'Empleador', style=greenStyle)
		sheet.write(2, 19, 'Código Servicio del cliente', style=greenStyle)
		sheet.write(2, 20, 'Código Medio de Pago', style=greenStyle)
		sheet.write(2, 21, 'Nro. Cuenta del medio de pago', style=greenStyle)
		sheet.write(2, 22, 'Código Moneda', style=greenStyle)
		sheet.write(2, 23, 'Tipo de operación de fecha', style=greenStyle)
		sheet.write(2, 24, 'Monto Cuota', style=greenStyle)
		sheet.write(2, 25, 'Fecha de Inicio Débitos', style=greenStyle)
		sheet.write(2, 26, 'Fecha de Fin Débitos', style=greenStyle)
		sheet.write(2, 27, 'Reintentos', style=greenStyle)
		sheet.write(2, 28, 'Fecha Cobro', style=greenStyle)
		sheet.write(2, 29, 'Monto a Debitar', style=greenStyle)
		sheet.write(2, 30, 'Fecha Cobro 2', style=greenStyle)
		sheet.write(2, 31, 'Monto a Debitar 2', style=greenStyle)
		sheet.write(2, 32, 'Fecha Cobro 3', style=greenStyle)
		sheet.write(2, 33, 'Monto a Debitar 3', style=greenStyle)
		sheet.write(2, 34, 'Fecha Cobro 4', style=greenStyle)
		sheet.write(2, 35, 'Monto a Debitar 4', style=greenStyle)
		sheet.write(2, 36, 'Fecha Cobro 5', style=greenStyle)
		sheet.write(2, 37, 'Monto a Debitar 5', style=greenStyle)
		sheet.write(2, 38, 'Fecha Cobro 6', style=greenStyle)
		sheet.write(2, 39, 'Monto a Debitar 6', style=greenStyle)
		sheet.write(2, 40, 'Detalle débito', style=greenStyle)
		sheet.write(2, 41, 'Información Medio de Pago', style=greenStyle)

		sheet.write(3, 0, 'Tamaño', style=firstColStyle)
		sheet.write(3, 1, '1')
		sheet.write(3, 2, '1')
		sheet.write(3, 3, '11')
		sheet.write(3, 4, '20')
		sheet.write(3, 5, '1')
		sheet.write(3, 6, '1')
		sheet.write(3, 7, '12')
		sheet.write(3, 8, '255')
		sheet.write(3, 9, '8')
		sheet.write(3, 10, '13')
		sheet.write(3, 11, '13')
		sheet.write(3, 12, '255')
		sheet.write(3, 13, '255')
		sheet.write(3, 14, '255')
		sheet.write(3, 15, '255')
		sheet.write(3, 16, '8')
		sheet.write(3, 17, '13')
		sheet.write(3, 18, '255')
		sheet.write(3, 19, '38')
		sheet.write(3, 20, '1')
		sheet.write(3, 21, '22')
		sheet.write(3, 22, '3')
		sheet.write(3, 23, '1')
		sheet.write(3, 24, '12')
		sheet.write(3, 25, '8')
		sheet.write(3, 26, '8')
		sheet.write(3, 27, '2')
		sheet.write(3, 28, '8')
		sheet.write(3, 29, '12')
		sheet.write(3, 30, '8')
		sheet.write(3, 31, '12')
		sheet.write(3, 32, '8')
		sheet.write(3, 33, '12')
		sheet.write(3, 34, '8')
		sheet.write(3, 35, '12')
		sheet.write(3, 36, '8')
		sheet.write(3, 37, '12')
		sheet.write(3, 38, '8')
		sheet.write(3, 39, '12')
		sheet.write(3, 40, '255')
		sheet.write(3, 41, '255')
		return sheet
	
	# CIUDAD file ADSUS
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
		sheet = book.add_sheet(u'Alta de Ordenes de débito')
		self.sheet_epico_prepare(sheet)
		row = 4
		# Escribimos el encabezado de detalle
		book_detalle = xlwt.Workbook(encoding='utf-8')
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
			provincia = 'Buenos Aires'
			if registro_id.partner_id.state_id:
				provincia = registro_id.partner_id.state_id.name
			sheet.write(row, 14, provincia)
			# sheet.write(row, 15, 'Email')
			# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
			# sheet.write(row, 17, 'CUIT Empleador')
			sheet.write(row, 18, 'Sin Informacion')
			sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
			sheet.write(row, 20, "D")
			sheet.write(row, 21, registro_id.cbu)
			sheet.write(row, 22, "032")
			sheet.write(row, 23, "F")
			sheet.write(row, 24, registro_id.debito_partes) # Ignorado para fecha fijo!
			date = datetime.strptime(self.ciudad_fecha_inicio, "%Y-%m-%d")
			sheet.write(row, 25, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2)) # Ignorado para fecha fijo!
			date = datetime.strptime(self.ciudad_fecha_fin, "%Y-%m-%d")
			sheet.write(row, 26, str(date.year)+str(date.month).zfill(2)+str(date.day).zfill(2)) # Ignorado para fecha fijo!
			sheet.write(row, 27, 0) # Reintentos dejamos en cero para fecha fijo!

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
			ciudad_debito_maximo_disponible = registro_id.monto_a_cobrar
			for date_id in self.ciudad_fecha_impacto_ids:
				monto_impacto = min(ciudad_debito_maximo_disponible, date_id.monto_impacto)
				if monto_impacto > 0:
					sheet_detalle.write(row_detalle, 0, registro_id.partner_id.name)
					sheet_detalle.write(row_detalle, 1, str(registro_id.partner_id.main_id_number))
					sheet_detalle.write(row_detalle, 2, registro_id.cuenta)
					sheet_detalle.write(row_detalle, 3, int(monto_impacto))
					sheet_detalle.write(row_detalle, 4, provincia)
					sheet_detalle.write(row_detalle, 5, self.ciudad_fecha_fin)
					sheet_detalle.write(row_detalle, 6, self.company_id.name)
					row_detalle +=1
					suma_a_cobrar += int(monto_impacto)
					cantidad_impactos += 1
					ciudad_debito_maximo_disponible -= monto_impacto

		book.save(stream)
		self.archivo_cobro = base64.encodestring(stream.getvalue())
		self.archivo_cobro_nombre = CIUDAD_COBRO_NOMBRE
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = CIUDAD_DETALLE_NOMBRE
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	# ITAU file
	@api.one
	def itau_file(self):
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
		row = 4
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
				provincia = 'Buenos Aires'
				if registro_id.partner_id.state_id:
					provincia = registro_id.partner_id.state_id.name
				sheet.write(row, 14, provincia)
				# sheet.write(row, 15, 'Email')
				# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
				# sheet.write(row, 17, 'CUIT Empleador')
				sheet.write(row, 18, 'Sin Informacion')
				sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
				sheet.write(row, 20, "D")
				sheet.write(row, 21, registro_id.cbu)
				sheet.write(row, 22, "032")
				sheet.write(row, 23, "B")
				sheet.write(row, 24, monto_impacto*100)
				date_init = datetime.strptime(self.itau_fecha_inicio, "%Y-%m-%d")
				sheet.write(row, 25, str(date_init.year)+str(date_init.month).zfill(2)+str(date_init.day).zfill(2))
				date_fin = datetime.strptime(self.itau_fecha_fin, "%Y-%m-%d")
				sheet.write(row, 26, str(date_fin.year)+str(date_fin.month).zfill(2)+str(date_fin.day).zfill(2))
				sheet.write(row, 27, 0) #Reintentos dejamos en cero para fecha fijo!

				sheet.write(row, 28, str(date_init.year)+str(date_init.month).zfill(2)+str(date_init.day).zfill(2))
				sheet.write(row, 29, monto_impacto*100)
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
				sheet_detalle.write(row_detalle, 4, provincia)
				sheet_detalle.write(row_detalle, 5, self.itau_fecha_fin)
				sheet_detalle.write(row_detalle, 6, self.company_id.name)
				row_detalle +=1
				suma_a_cobrar += int(monto_impacto)
				cantidad_impactos += 1
				cantidad_a_debitar_disponible -= monto_impacto
				monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)

		book.save(stream)
		self.archivo_cobro = base64.encodestring(stream.getvalue())
		self.archivo_cobro_nombre = ITAU_COBRO_NOMBRE
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = ITAU_DETALLE_NOMBRE
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos


	# BBVA file
	@api.one
	def bbva_file(self):
		suma_a_cobrar = 0
		cantidad_impactos = 0
		if len(self.registro_ids) == 0:
			raise UserError('Sin registro de deudores.')
		self.state = 'generado'
		cobranza_config_id = self.company_id.cobranza_config_id
		if not cobranza_config_id.codigo_referencia_bbva:
			raise ValidationError("Falta configurar Codigo referencia BBVA brindado por ADSUS.")
		if not cobranza_config_id.codigo_servicio_epico:
			raise ValidationError("Falta configurar Codigo de servicio EPICO brindado por ADSUS.")
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		self.sheet_epico_prepare(sheet)
		row = 4
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
				provincia = 'Buenos Aires'
				if registro_id.partner_id.state_id:
					provincia = registro_id.partner_id.state_id.name
				sheet.write(row, 14, provincia)
				# sheet.write(row, 15, 'Email')
				# sheet.write(row, 16, 'Fecha de acreditacion de haberes 1')
				# sheet.write(row, 17, 'CUIT Empleador')
				sheet.write(row, 18, 'Sin Informacion')
				sheet.write(row, 19, cobranza_config_id.codigo_servicio_epico)
				sheet.write(row, 20, "D")
				sheet.write(row, 21, registro_id.cbu)
				sheet.write(row, 22, "032")
				sheet.write(row, 23, "B")
				sheet.write(row, 24, monto_impacto*100)
				date_init = datetime.strptime(self.bbva_fecha_inicio, "%Y-%m-%d")
				sheet.write(row, 25, str(date_init.year)+str(date_init.month).zfill(2)+str(date_init.day).zfill(2))
				date_fin = datetime.strptime(self.bbva_fecha_fin, "%Y-%m-%d")
				sheet.write(row, 26, str(date_fin.year)+str(date_fin.month).zfill(2)+str(date_fin.day).zfill(2))
				sheet.write(row, 27, 0) #Reintentos dejamos en cero para fecha fijo!

				sheet.write(row, 28, str(date_init.year)+str(date_init.month).zfill(2)+str(date_init.day).zfill(2))
				sheet.write(row, 29, monto_impacto*100)
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
				sheet_detalle.write(row_detalle, 4, provincia)
				sheet_detalle.write(row_detalle, 5, self.bbva_fecha_fin)
				sheet_detalle.write(row_detalle, 6, self.company_id.name)
				row_detalle +=1
				suma_a_cobrar += int(monto_impacto)
				cantidad_impactos += 1
				cantidad_a_debitar_disponible -= monto_impacto
				monto_impacto = min(cantidad_a_debitar_disponible, registro_id.debito_partes)

		book.save(stream)
		self.archivo_cobro = base64.encodestring(stream.getvalue())
		self.archivo_cobro_nombre = BBVA_COBRO_NOMBRE
		stream_detalle = StringIO.StringIO()
		book_detalle.save(stream_detalle)
		self.archivo_detalle = base64.encodestring(stream_detalle.getvalue())
		self.archivo_detalle_nombre = BBVA_DETALLE_NOMBRE
		self.suma_a_cobrar = suma_a_cobrar
		self.cantidad_impactos = cantidad_impactos

	@api.multi
	def enviar_email_adsus(self):
		""" Open a window to compose an email, with the edi cupon template
			message loaded by default
		"""
		self.ensure_one()
		cobranza_config_id = self.company_id.cobranza_config_id
		if not cobranza_config_id or not cobranza_config_id.adsus_template_id:
			raise ValidationError("Falta configurar el templeta del email ADSUS.")
		template = cobranza_config_id.adsus_template_id
		if self.archivo_cobro == None or self.archivo_detalle == None:
			raise ValidationError("Falta generar archivo!")
		compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)		
		archivo_cobro_attachment_id = False
		if self.archivo_cobro != None:
			archivo_cobro_attachment_id = self.env['ir.attachment'].create({
				'name': self.archivo_cobro_nombre,
				'datas_fname': self.archivo_cobro_nombre,
				'type': 'binary',
				'datas': base64.encodestring(self.archivo_cobro),
				'res_model': 'financiera.cobranza.cbu',
				'res_id': self.id,
				'mimetype': 'application/x-pdf',
			})
			archivo_detalle_attachment_id = False
			if self.archivo_detalle != None:
				archivo_detalle_attachment_id = self.env['ir.attachment'].create({
				'name': self.archivo_detalle_nombre,
				'datas_fname': self.archivo_detalle_nombre,
				'type': 'binary',
				'datas': base64.encodestring(self.archivo_detalle),
				'res_model': 'financiera.cobranza.cbu',
				'res_id': self.id,
				'mimetype': 'application/x-pdf',
			})
		ctx = dict(
			default_model='financiera.cobranza.cbu',
			default_res_id=self.id,
			default_use_template=bool(template),
			default_template_id=template and template.id or False,
			default_composition_mode='comment',
			default_attachment_ids=[(6, 0, [archivo_cobro_attachment_id.id, archivo_detalle_attachment_id.id])],
			sub_action='tc_sent',
			# mark_invoice_as_sent=True,
		)
		# ctx['default_attachment_ids'] = [(6, 0, [archivo_cobro_attachment_id.id, archivo_detalle_attachment_id.id])]
		return {
			'name': 'Envio archivos de cobro a ADSUS',
			'type': 'ir.actions.act_window',
			'view_type': 'form',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(compose_form.id, 'form')],
			'view_id': compose_form.id,
			'target': 'new',
			'context': ctx,
		}

class FinancieraCobranzaCbuRegistro(models.Model):
	_name = 'financiera.cobranza.cbu.registro'

	cobranza_cbu_id = fields.Many2one('financiera.cobranza.cbu', 'Cobranza CBU')
	partner_id = fields.Many2one('res.partner', 'Cliente')
	prestamo_id = fields.Many2one('financiera.prestamo', 'Prestamo')
	prestamo_mobbex_debito_automatico = fields.Boolean(related='prestamo_id.mobbex_debito_automatico')
	prestamo_mobbex_suscripcion_suscriptor_confirm = fields.Boolean('prestamo_id.mobbex_suscripcion_suscriptor_confirm', readonly="1")
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

	@api.one
	def stop_debito_automatico(self):
		self.prestamo_mobbex_debito_automatico = False
	
	@api.one
	def allow_debito_automatico(self):
		self.prestamo_mobbex_debito_automatico = True
	
	@api.one
	def stop_debito_cbu(self):
		self.prestamo_no_debitar_cbu = False
	
	@api.one
	def allow_debito_cbu(self):
		self.prestamo_no_debitar_cbu = True
class FinancieraCobranzaCbuFecha(models.Model):
	_name = 'financiera.cobranza.cbu.fecha'

	cobranza_cbu_id = fields.Many2one('financiera.cobranza.cbu', 'Cobranza ID')
	fecha_impacto = fields.Date('Fecha de impacto')
	monto_impacto = fields.Float('Monto a debitar')

class ExtendsAccountPayment(models.Model):
	_inherit = 'account.payment' 
	_name = 'account.payment'

	company_related_id = fields.Many2one('res.company', related='cuota_id.company_id')