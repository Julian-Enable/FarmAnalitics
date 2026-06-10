/**
 * Utilidades de exportación — Farma Analytics
 * Genera archivos Excel (.xls) con formato profesional listo para presentar.
 */

// ── Helpers ──────────────────────────────────────────────────────────────

function escapeHtml(value) {
  if (value === null || value === undefined) return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Detecta si un valor formateado es moneda ($123K, $1.2M, $500) */
function isCurrencyValue(raw, formatted) {
  if (typeof formatted === 'string' && /^\$/.test(formatted)) return true
  return false
}

/** Detecta si un valor es porcentaje */
function isPercentValue(raw, formatted) {
  if (typeof formatted === 'string' && /%$/.test(formatted)) return true
  return false
}

/** Formatea un número crudo para Excel (sin el formato display) */
function excelNumber(raw) {
  const n = Number(raw)
  if (isNaN(n)) return escapeHtml(raw)
  // Formato con separador de miles colombiano
  return n.toLocaleString('es-CO', { maximumFractionDigits: 2 })
}

// ── Estilos CSS para Excel ───────────────────────────────────────────────

const EXCEL_STYLES = `
  body {
    font-family: Calibri, Arial, sans-serif;
    font-size: 11pt;
    color: #1a1a1a;
  }
  h2 {
    font-family: Calibri, Arial, sans-serif;
    font-size: 14pt;
    font-weight: 700;
    color: #1e3a5f;
    margin: 20px 0 8px 0;
    padding-bottom: 4px;
    border-bottom: 2px solid #3b82f6;
  }
  table {
    border-collapse: collapse;
    margin-bottom: 20px;
    width: 100%;
  }
  th {
    background: #1e3a5f;
    color: #ffffff;
    font-weight: 700;
    font-size: 10pt;
    padding: 8px 12px;
    border: 1px solid #15304f;
    text-align: left;
    white-space: nowrap;
  }
  td {
    padding: 6px 12px;
    border: 1px solid #d1d5db;
    font-size: 10pt;
    vertical-align: middle;
  }
  tr:nth-child(even) td {
    background: #f0f4ff;
  }
  tr:nth-child(odd) td {
    background: #ffffff;
  }
  .num-cell {
    text-align: right;
    font-variant-numeric: tabular-nums;
    mso-number-format: "#,##0";
  }
  .money-cell {
    text-align: right;
    font-weight: 600;
    color: #15803d;
    font-variant-numeric: tabular-nums;
    mso-number-format: "$ #,##0";
  }
  .money-cell-negative {
    text-align: right;
    font-weight: 600;
    color: #dc2626;
    font-variant-numeric: tabular-nums;
  }
  .pct-cell {
    text-align: right;
    color: #1e40af;
    font-weight: 600;
  }
  .footer-row td {
    background: #e8ecf4 !important;
    font-weight: 700;
    font-size: 10pt;
    border-top: 2px solid #1e3a5f;
  }
  .report-header {
    font-family: Calibri, Arial, sans-serif;
    font-size: 18pt;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: 4px;
  }
  .report-meta {
    font-family: Calibri, Arial, sans-serif;
    font-size: 9pt;
    color: #6b7280;
    margin-bottom: 16px;
  }
`

// ── Construcción de tabla HTML formateada ─────────────────────────────────

function buildFormattedTable(data, columns, title = null) {
  if (!data || !data.length || !columns || !columns.length) return ''

  // Cabeceras
  const headers = columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join('')

  // Analizar tipos de columna basado en los datos
  const colTypes = columns.map(col => {
    let moneyCount = 0, pctCount = 0, numCount = 0
    const sample = data.slice(0, Math.min(data.length, 20))
    for (const row of sample) {
      const raw = row[col.key]
      let formatted = raw
      if (col.formatter && typeof col.formatter === 'function') {
        try { formatted = col.formatter(raw, row) } catch (e) { formatted = raw }
      }
      if (isCurrencyValue(raw, String(formatted))) moneyCount++
      else if (isPercentValue(raw, String(formatted))) pctCount++
      else if (typeof raw === 'number' && !isNaN(raw)) numCount++
    }
    if (moneyCount > sample.length * 0.5) return 'money'
    if (pctCount > sample.length * 0.5) return 'pct'
    if (numCount > sample.length * 0.5) return 'num'
    return 'text'
  })

  // Filas de datos
  const body = data.map(row => {
    const cells = columns.map((col, ci) => {
      const raw = row[col.key]
      let formatted = raw
      if (col.formatter && typeof col.formatter === 'function') {
        try { formatted = col.formatter(raw, row) } catch (e) { formatted = raw }
      }

      const type = colTypes[ci]
      let cssClass = ''
      let displayValue = ''

      if (type === 'money') {
        cssClass = (Number(raw) < 0) ? 'money-cell-negative' : 'money-cell'
        // Mostrar el valor formateado (ya incluye $)
        displayValue = escapeHtml(formatted)
      } else if (type === 'pct') {
        cssClass = 'pct-cell'
        displayValue = escapeHtml(formatted)
      } else if (type === 'num') {
        cssClass = 'num-cell'
        displayValue = (raw != null && !isNaN(Number(raw)))
          ? Number(raw).toLocaleString('es-CO', { maximumFractionDigits: 2 })
          : escapeHtml(formatted)
      } else {
        displayValue = escapeHtml(formatted)
      }

      return `<td class="${cssClass}">${displayValue}</td>`
    }).join('')
    return `<tr>${cells}</tr>`
  }).join('')

  // Fila de totales automáticos para columnas monetarias
  let footerRow = ''
  const hasMoney = colTypes.some(t => t === 'money')
  if (hasMoney && data.length > 1) {
    const footerCells = columns.map((col, ci) => {
      if (ci === 0) return `<td>TOTAL (${data.length} registros)</td>`
      if (colTypes[ci] === 'money') {
        const sum = data.reduce((acc, row) => acc + (Number(row[col.key]) || 0), 0)
        let formatted = sum
        if (col.formatter && typeof col.formatter === 'function') {
          try { formatted = col.formatter(sum, {}) } catch (e) { formatted = sum }
        }
        return `<td class="money-cell">${escapeHtml(formatted)}</td>`
      }
      if (colTypes[ci] === 'num') {
        const sum = data.reduce((acc, row) => acc + (Number(row[col.key]) || 0), 0)
        return `<td class="num-cell">${sum.toLocaleString('es-CO', { maximumFractionDigits: 0 })}</td>`
      }
      return '<td></td>'
    }).join('')
    footerRow = `<tr class="footer-row">${footerCells}</tr>`
  }

  const titleHtml = title ? `<h2>${escapeHtml(title)}</h2>` : ''

  return `
    ${titleHtml}
    <table>
      <thead><tr>${headers}</tr></thead>
      <tbody>${body}${footerRow}</tbody>
    </table>
  `
}

// ── Generar documento Excel completo ─────────────────────────────────────

function buildExcelDocument(content, reportTitle = 'Reporte') {
  const now = new Date()
  const dateStr = now.toLocaleDateString('es-CO', { year: 'numeric', month: 'long', day: 'numeric' })
  const timeStr = now.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })

  return `
    <html xmlns:o="urn:schemas-microsoft-com:office:office"
          xmlns:x="urn:schemas-microsoft-com:office:excel"
          xmlns="http://www.w3.org/TR/REC-html40">
      <head>
        <meta charset="UTF-8" />
        <!--[if gte mso 9]>
        <xml>
          <x:ExcelWorkbook>
            <x:ExcelWorksheets>
              <x:ExcelWorksheet>
                <x:Name>${escapeHtml(reportTitle)}</x:Name>
                <x:WorksheetOptions>
                  <x:DisplayGridlines/>
                  <x:FitToPage/>
                  <x:Print>
                    <x:FitWidth>1</x:FitWidth>
                    <x:FitHeight>0</x:FitHeight>
                  </x:Print>
                </x:WorksheetOptions>
              </x:ExcelWorksheet>
            </x:ExcelWorksheets>
          </x:ExcelWorkbook>
        </xml>
        <![endif]-->
        <style>${EXCEL_STYLES}</style>
      </head>
      <body>
        <div class="report-header">📊 Farma Analytics — ${escapeHtml(reportTitle)}</div>
        <div class="report-meta">Generado: ${dateStr} a las ${timeStr}</div>
        ${content}
      </body>
    </html>
  `
}

function downloadExcel(html, filename) {
  const blob = new Blob(['\uFEFF' + html], { type: 'application/vnd.ms-excel;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.xls`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// ── API Pública ──────────────────────────────────────────────────────────

/**
 * Exporta un arreglo de objetos a un archivo Excel formateado.
 * Reemplaza la antigua exportToCSV manteniendo la misma firma.
 * @param {Array} data - El arreglo de datos (filas).
 * @param {Array} columns - Arreglo de { key, label, formatter? }
 * @param {String} filename - Nombre del archivo (sin extensión).
 */
export function exportToCSV(data, columns, filename = 'exportacion') {
  if (!data || !data.length) {
    alert('No hay datos para exportar.')
    return
  }

  const tableHtml = buildFormattedTable(data, columns)
  const html = buildExcelDocument(tableHtml, filename.replace(/_/g, ' '))
  downloadExcel(html, filename)
}

/**
 * Exporta múltiples hojas/secciones en un solo archivo Excel.
 * @param {Array} sheets - Arreglo de { name, data, columns }
 * @param {String} filename - Nombre del archivo (sin extensión).
 */
export function exportWorkbookAsExcel(sheets, filename = 'reporte') {
  const validSheets = sheets.filter(sheet => sheet?.data?.length && sheet?.columns?.length)
  if (!validSheets.length) {
    alert('No hay datos para exportar.')
    return
  }

  const content = validSheets.map(sheet =>
    buildFormattedTable(sheet.data, sheet.columns, sheet.name)
  ).join('<br style="page-break-after: always;" />')

  const html = buildExcelDocument(content, filename.replace(/_/g, ' '))
  downloadExcel(html, filename)
}
