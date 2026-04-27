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
}
