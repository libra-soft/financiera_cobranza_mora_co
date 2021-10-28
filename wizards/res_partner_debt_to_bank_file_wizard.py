# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.exceptions import UserError, ValidationError
import xlwt
import base64
import StringIO

class ResPartnerDebtToBankFileWizard(models.TransientModel):
	_name = 'res.partner.debt.to.bank.file.wizard'
	
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('res.partner.debt.to.bank.file.wizard'))
	bna_fecha_inicio_debitos = fields.Date('Fecha de Inicio Débitos')
	bna_fecha_fin_debitos = fields.Date('Fecha de Fin Débitos')
	bna_mes_tope_rendicion = fields.Char('BNA mes tope rendicion', help='Por ej: 08 para agosto, 12 para diciembre.')
	bna_nro_archivo_enviado_mes = fields.Char('BNA nro de archivo enviado en el mes', help='Comenzando por 01', default='01')
	bna_debito_partes = fields.Float('BNA debito en parte maxima de')
	bna_file_debt = fields.Binary('BNA archivo')
	bna_file_debt_name = fields.Char('BNA archivo nombre', default='bna_a_cobrar.txt')
	bna_file_detalle = fields.Binary('BNA archivo de detalle')
	bna_file_detalle_name = fields.Char('BNA archivo de detalle nombre', default='bna_detalle.xls')

	@api.multi
	def generar_archivos(self):
		context = dict(self._context or {})
		active_ids = context.get('active_ids')
		self.bna_file(active_ids)
		return {'type': 'ir.actions.do_nothing'}
	
	@api.onchange('bna_fecha_fin_debitos')
	def _onchange_bna_mes_tope_rendicion(self):
		if self.bna_fecha_fin_debitos:
			fecha_tope_rendicion = datetime.strptime(self.bna_fecha_fin_debitos, "%Y-%m-%d")
			self.bna_mes_tope_rendicion = str(fecha_tope_rendicion.month).zfill(2)

	def bna_file(self, partner_ids):
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
		# Escribimos los registro tipo 2
		registros_tipo_2 = ""
		cantidad_registros_tipo_2 = 0
		total_a_debitar = 0
		for _id in partner_ids:
			partner_obj = self.pool.get('res.partner')
			partner_id = partner_obj.browse(self.env.cr, self.env.uid, _id)
			print("Parner name: ", partner_id.name)
			partner_cbu = False
			partner_cbu_entidad = False
			partner_cbu_sucursal = False
			partner_cbu_cuenta = False
			if len(partner_id.cuota_mora_ids) > 0:
				partner_cbu = partner_id.cuota_mora_ids[0].prestamo_id.app_cbu
				if partner_cbu and len(partner_cbu) == 22:
					partner_cbu_entidad = partner_cbu[0:3]
					partner_cbu_sucursal_bcra = partner_cbu[3:7]
					partner_cbu_sucursal = self.env['res.bank.bna.code'].code_bcra_to_bna(partner_cbu_sucursal_bcra)
					partner_cbu_cuenta = partner_cbu[11:21]
			print("partner_cbu: ", partner_cbu)
			print("partner_cbu_entidad: ", partner_cbu_entidad)
			print("partner_cbu_sucursal: ", partner_cbu_sucursal)
			print("partner_cbu_cuenta: ", partner_cbu_cuenta)
			print("partner_id.saldo_mora: ", partner_id.saldo_mora)
			if partner_id and partner_id.saldo_mora > 0 and partner_cbu_entidad and partner_cbu_entidad == '011' and partner_cbu_sucursal and partner_cbu_cuenta:
				saldo_a_debitar = partner_id.saldo_mora
				while saldo_a_debitar > 0:
					nuevo_registro = "2"
					if len(partner_cbu_sucursal) == 4:
						nuevo_registro += partner_cbu_sucursal
					else:
						pass
					# Hardcore CA - Supuestamente siempre sera CA: Caja de Ahorro
					nuevo_registro += "CA"
					# Cuenta a debitar primera posicion 0 y N(10) para Nro de cuenta del cliente
					nuevo_registro += "0"
					if len(partner_cbu_cuenta) == 10:
							nuevo_registro += partner_cbu_cuenta
					else:
						pass
					# Importe a debitar N(15) 13,2
					monto_a_debitar = saldo_a_debitar
					if self.bna_debito_partes > 0:
						monto_a_debitar = min(self.bna_debito_partes, monto_a_debitar)
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
					nuevo_registro += str(partner_id.id).zfill(10)
					nuevo_registro += "".ljust(46, ' ')
					nuevo_registro += "\r\n"
					registros_tipo_2 += nuevo_registro
					cantidad_registros_tipo_2 += 1
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
		
		file_read = base64.b64encode(encabezado+registros_tipo_2+finalizar)
		# +registros+finalizar
		self.bna_file_debt = file_read


	def bna_file(self, partner_ids):
		stream = StringIO.StringIO()
		book = xlwt.Workbook(encoding='utf-8')
		sheet = book.add_sheet(u'Sheet1')
		sheet.write(0, 0, 'Tipo Registro')
		sheet.write(0, 1, 'Tipo Id adherente')
		sheet.write(0, 2, 'Id adherente')
		sheet.write(0, 3, 'Número Referencia')
		sheet.write(0, 4, 'Tipo de documento de Identidad')
		sheet.write(0, 5, 'Documento de Identidad')
		sheet.write(0, 6, 'Apellido y Nombre')
		sheet.write(0, 7, 'DÍAS DE ATRASO')
		sheet.write(0, 8, 'Provincia')
		sheet.write(0, 9, 'Empleador')
		sheet.write(0, 10, 'Código Servicio del cliente')
		sheet.write(0, 11, 'Código Medio de Pago')
		sheet.write(0, 12, 'Nro. Cuenta del medio de pago')
		sheet.write(0, 13, 'Nro. Cuenta del medio de pago')
		sheet.write(0, 14, 'Nro. Cuenta del medio de pago')
		sheet.write(0, 15, 'Código Moneda')
		sheet.write(0, 16, 'Tipo de operación de fecha')
		sheet.write(0, 17, 'Monto Cuota')
		sheet.write(0, 18, 'Fecha de Inicio Débitos')
		sheet.write(0, 19, 'Fecha de Fin Débitos')
		sheet.write(0, 20, 'Reintentos')
		sheet.write(0, 21, 'Monto a Debitar')
		sheet.write(0, 22, 'Detalle débito')
		sheet.write(0, 23, 'Información Medio de Pago')
		sheet.write(0, 24, 'Banco ID')
		sheet.write(0, 25, 'Banco')
		row = 1
		for _id in partner_ids:
			cuota_id = self.env['financiera.prestamo.cuota'].browse(_id)
			col = 0
			while col <= 25:
				if col == 0:
					sheet.write(row, col, 'D')
				elif col == 1:
					sheet.write(row, col, 'C')
				elif col == 2:
					sheet.write(row, col, int(cuota_id.partner_id.main_id_number))
				elif col == 3:
					sheet.write(row, col, cuota_id.id)
				elif col == 4:
					sheet.write(row, col, 'D')
				elif col == 5:
					sheet.write(row, col, cuota_id.partner_id.dni)
				elif col == 6:
					sheet.write(row, col, cuota_id.partner_id.name)
				elif col == 7:
					sheet.write(row, col, cuota_id.partner_id.alerta_dias_ultimo_pago)
				elif col == 8:
					sheet.write(row, col, cuota_id.partner_id.state_id.name)
				elif col == 9:
					sheet.write(row, col, cuota_id.partner_id.function)
				elif col == 10:
					sheet.write(row, col, '')
				elif col == 11:
					sheet.write(row, col, 'D')
				elif col == 12:
					sheet.write(row, col, cuota_id.prestamo_id.app_cbu)
				elif col == 13:
					sheet.write(row, col, cuota_id.partner_id.app_cbu)
				elif col == 14:
					if len(cuota_id.partner_id.bank_ids) > 0:
						sheet.write(row, col, cuota_id.partner_id.bank_ids[0].cbu)
				elif col == 15:
					sheet.write(row, col, '032')
				elif col == 16:
					sheet.write(row, col, 'B')
				elif col == 17:
					sheet.write(row, col, int(str(cuota_id.saldo).replace(',','').replace('.', '')))
				elif col == 18:
					if self.fecha_inicio_debitos:
						sheet.write(row, col, str(self.fecha_inicio_debitos).replace('-', '').replace('/', ''))
				elif col == 19:
					if self.fecha_fin_debitos:
						sheet.write(row, col, str(self.fecha_fin_debitos).replace('-', '').replace('/', ''))
				elif col == 20:
					sheet.write(row, col, self.reintentos)
				elif col == 21:
					sheet.write(row, col, int(str(cuota_id.saldo).replace(',','').replace('.', '')))
				elif col == 22:
					sheet.write(row, col, 'PRESTAMO')
				elif col == 23:
					sheet.write(row, col, cuota_id.prestamo_id.name)
				elif col == 24:
					sheet.write(row, col, cuota_id.prestamo_id.app_banco_haberes_numero_entidad)
				elif col == 25:
					sheet.write(row, col, cuota_id.prestamo_id.app_banco_haberes)
				col += 1
			row +=1
		book.save(stream)
		self.file = base64.encodestring(stream.getvalue())