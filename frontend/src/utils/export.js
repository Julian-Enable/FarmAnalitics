/**
 * Exporta un arreglo de objetos a un archivo CSV.
 * @param {Array} data - El arreglo de datos (filas).
 * @param {Array} columns - Arreglo de objetos definiendo las columnas: { key: 'Referencia', label: 'Cód. Ref' }
 * @param {String} filename - Nombre del archivo a descargar (sin el .csv).
 */
export function exportToCSV(data, columns, filename = 'exportacion') {
  if (!data || !data.length) {
    alert('No hay datos para exportar.');
    return;
  }

  // Crear cabeceras
  const headers = columns.map(col => `"${col.label.replace(/"/g, '""')}"`).join(',');

  // Crear filas
  const rows = data.map(row => {
    return columns.map(col => {
      let cellData = row[col.key];
      if (col.formatter && typeof col.formatter === 'function') {
        cellData = col.formatter(cellData, row);
      }
      if (cellData === null || cellData === undefined) {
        cellData = '';
      }
      // Escapar comillas dobles y comas envolviendo en comillas
      const stringData = String(cellData).replace(/"/g, '""');
      return `"${stringData}"`;
    }).join(',');
  });

  // Agregar BOM (Byte Order Mark) para UTF-8 (para que Excel reconozca tildes y ñ)
  const csvContent = '\uFEFF' + [headers, ...rows].join('\n');

  // Descargar archivo
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `${filename}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function escapeHtml(value) {
  if (value === null || value === undefined) return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildSheetHtml(sheet) {
  const rows = sheet.data || []
  const columns = sheet.columns || []
  const headers = columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join('')
  const body = rows.map(row => {
    const cells = columns.map(col => {
      let value = row[col.key]
      if (col.formatter && typeof col.formatter === 'function') value = col.formatter(value, row)
      return `<td>${escapeHtml(value)}</td>`
    }).join('')
    return `<tr>${cells}</tr>`
  }).join('')

  return `
    <h2>${escapeHtml(sheet.name)}</h2>
    <table>
      <thead><tr>${headers}</tr></thead>
      <tbody>${body}</tbody>
    </table>
  `
}

export function exportWorkbookAsExcel(sheets, filename = 'reporte') {
  const validSheets = sheets.filter(sheet => sheet?.data?.length && sheet?.columns?.length)
  if (!validSheets.length) {
    alert('No hay datos para exportar.')
    return
  }

  const html = `
    <html>
      <head>
        <meta charset="UTF-8" />
        <style>
          body { font-family: Arial, sans-serif; }
          h2 { margin-top: 24px; }
          table { border-collapse: collapse; margin-bottom: 24px; }
          th, td { border: 1px solid #999; padding: 6px 8px; font-size: 12px; }
          th { background: #eef0fb; font-weight: 700; }
        </style>
      </head>
      <body>${validSheets.map(buildSheetHtml).join('<br style="page-break-after: always;" />')}</body>
    </html>
  `

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
