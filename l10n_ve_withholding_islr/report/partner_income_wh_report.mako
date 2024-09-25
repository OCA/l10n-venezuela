<!DOCTYPE html SYSTEM
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"> 
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<html>
    <head>
        <style type="text/css">
            ${css}
        </style>
    </head>

    <body style="border:0; margin: 0;" onload="subst()" >
      %for obj in objects :
        <table width="100%">
          <tr>
            <td width="25%">
                <div>${helper.embed_image('jpeg',str(obj.company_id.logo),100, 46)}</div>
                <div class="logoAndCompanyName">${obj.company_id.name or ''|entity}</div>
                <div class="logoAndCompanyName">RIF: ${obj.company_id.partner_id.vat[2:]|entity}</div>
            </td>
            <td width="75%">
              <table style="width: 100%; text-align:center;">
                <tr><td><div class="headerTitle"> COMPROBANTE DE RETENCIONES VARIAS DEL IMPUESTO SOBRE LA RENTA</div></td></tr>
                <tr><td><div class="headerSubTitle"> (DIFERENTES A SUELDOS Y SALARIOS Y DEMÁS REMUNERACIONES SIMILARES A PERSONAS NATURALES RESIDENTES) </div></td></tr>
                <tr>
                  <td>
                      <div class="headerSubTitle"> <b/>
                      ${u"PERÍODO DESDE %s HASTA %s"%(formatLang(obj.period_id.date_start, digits=0, date=True, date_time=False, grouping=3, monetary=False),
                      formatLang(obj.period_id.date_stop, digits=0, date=True, date_time=False, grouping=3, monetary=False))}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        <table width="100%">
          <tr>
            <td class="headerBodyCenter" width="50%">
                <div> AGENTE DE RETENCIÓN </div>
            </td>
            <td class="headerBodyCenter" width="50%">
                <div> BENEFICIARIO </div>
            </td>
          </tr>
          <tr>
            <td class="cellBodyCenter" width="50%">
                <div> ${obj.company_id.name.upper() or ''|entity} </div>
                <div> RIF: ${obj.company_id.partner_id.vat[2:]|entity} </div>
                <div> ${obj.get_partner_address(obj.company_id.partner_id.id)|entity} </div>
            </td>
            <td class="cellBodyCenter" width="50%">
                <div> ${obj.partner_id.name.upper() or ''|entity} </div>
                <div> RIF: ${obj.partner_id.vat and obj.partner_id.vat[2:] or 'FALTA RIF'|entity} </div>
                <div> ${obj.get_partner_address(obj.partner_id.id)|entity} </div>
            </td>
          </tr>
        </table>
        %if obj.iwdl_ids:
          <%
          total_base_amount = 0.0
          total_amount = 0.0
          total_currency_base_amount = 0.0
          total_currency_amount = 0.0
          multicurrency = False
          for iwdl_brw in obj.iwdl_ids:
            if iwdl_brw.invoice_id.currency_id.id != obj.company_id.currency_id.id:
              multicurrency = iwdl_brw.invoice_id.currency_id.name
              break
          %>
          <table width="100%">
            <tr>
              %if multicurrency:
                <td class="headerBodyCenter" width="12.5%"> <div> FACTURA </div> </td>
                <td class="headerBodyCenter" width="12.5%"> <div> NÚM. CONTROL </div> </td>
              %else:
                <td class="headerBodyCenter" width="25.0%"> <div> FACTURA </div> </td>
                <td class="headerBodyCenter" width="25.0%"> <div> NÚM. CONTROL </div> </td>
              %endif
              <td class="headerBodyCenter" width="12.5%"> <div> FEC. FACT. </div> </td>
              <td class="headerBodyCenter" width="12.5%"> <div> PORC. RET. </div> </td>
              <td class="headerBodyCenter" width="12.5%"> <div> BASE DE RET. </div> </td>
              <td class="headerBodyCenter" width="12.5%"> <div> RETENCIÓN </div> </td>
              %if multicurrency:
                  <td class="headerBodyCenter" width="12.5%"> <div>B/RET. FÓRANEA</div> </td>
                  <td class="headerBodyCenter" width="12.5%"> <div> RET. FÓRANEA </div> </td>
              %endif
            </tr>
          </table>
          <table class="basic_table" width="100%">
            %for iwdl_brw in obj.iwdl_ids:
              <%
                total_base_amount += iwdl_brw.base_amount
                total_amount += iwdl_brw.amount
                total_currency_base_amount += iwdl_brw.currency_base_amount
                total_currency_amount += iwdl_brw.currency_amount
              %>
              <tr>
              %if multicurrency:
                <td class="cellCenter" width="12.5%"> ${iwdl_brw.invoice_id.supplier_invoice_number} </td>
                <td class="cellCenter" width="12.5%"> ${iwdl_brw.invoice_id.nro_ctrl} </td>
              %else:
                <td class="cellCenter" width="25.0%"> ${iwdl_brw.invoice_id.supplier_invoice_number} </td>
                <td class="cellCenter" width="25.0%"> ${iwdl_brw.invoice_id.nro_ctrl} </td>
              %endif
                <td class="cellCenter" width="12.5%"> ${iwdl_brw.invoice_id.date_document and formatLang(iwdl_brw.invoice_id.date_document, digits=0, date=True, date_time=False, grouping=3, monetary=False)} </td>
                <td class="cellRightMonospace" width="12.5%"> ${formatLang(iwdl_brw.retencion_islr, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
                <td class="cellRightMonospace" width="12.5%"> ${formatLang(iwdl_brw.base_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
                <td class="cellRightMonospace" width="12.5%"> ${formatLang(iwdl_brw.amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
                %if multicurrency:
                  <td class="cellRightMonospace" width="12.5%"> ${iwdl_brw.invoice_id.currency_id.name} ${formatLang(iwdl_brw.currency_base_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
                  <td class="cellRightMonospace" width="12.5%">  ${iwdl_brw.invoice_id.currency_id.name} ${formatLang(iwdl_brw.currency_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
                %endif
              </tr>
            %endfor
          </table>
          <table width="100%">
            <tr>
              %if multicurrency:
              <td class="footerBodyCenter" width="12.5%"> </td>
              <td class="footerBodyCenter" width="12.5%"> </td>
              %else:
              <td class="footerBodyCenter" width="25.0%"> </td>
              <td class="footerBodyCenter" width="25.0%"> </td>
              %endif
              <td class="footerBodyRightMonospace" width="12.5%"> </td>
              <td class="footerBodyCenter" width="12.5%"> TOTALES </td>
              <td class="footerBodyRightMonospace" width="12.5%"> ${formatLang(total_base_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
              <td class="footerBodyRightMonospace" width="12.5%"> ${formatLang(total_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
              %if multicurrency:
              <td class="footerBodyRightMonospace" width="12.5%"> ${multicurrency} ${formatLang(total_currency_base_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
              <td class="footerBodyRightMonospace" width="12.5%"> ${multicurrency} ${formatLang(total_currency_amount, digits=2, date=False, date_time=False, grouping=3, monetary=True)} </td>
              %endif
            </tr>
          </table>
        %endif
      %endfor
    </body>
</html>
