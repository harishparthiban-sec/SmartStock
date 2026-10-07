import fs from 'fs';
import path from 'path';
import xlsx from 'xlsx';

const DATA_DIR = path.resolve('../Data Forcast/data');
const OUT_DIR = path.resolve('./public/api');

if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

function parseExcelDate(excelDate) {
  // If it's a number, it's an Excel serial date
  if (typeof excelDate === 'number') {
    // Excel epoch is 1899-12-30 (but 1900 leap year bug means 25569 is offset for 1970-01-01)
    const date = new Date(Math.round((excelDate - 25569) * 86400 * 1000));
    return date.toISOString().split('T')[0];
  }
  // If it's already a Date object
  if (excelDate instanceof Date) {
    const year = excelDate.getFullYear();
    const month = String(excelDate.getMonth() + 1).padStart(2, '0');
    const day = String(excelDate.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  // Fallback to string
  if (typeof excelDate === 'string') {
    return excelDate.split('T')[0];
  }
  return excelDate;
}

function processFile(filename, outfile) {
  const filePath = path.join(DATA_DIR, filename);
  if (!fs.existsSync(filePath)) {
    console.warn(`File not found: ${filePath}`);
    return;
  }
  // cellDates: false ensures we get the raw serial numbers so we can precisely convert to UTC without local timezone shifts
  const wb = xlsx.readFile(filePath, { cellDates: false });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const data = xlsx.utils.sheet_to_json(sheet);
  
  // Format dates if the 'date' field exists
  const formattedData = data.map(row => {
    if (row.date) {
      row.date = parseExcelDate(row.date);
    }
    return row;
  });

  fs.writeFileSync(path.join(OUT_DIR, outfile), JSON.stringify(formattedData, null, 2));
  console.log(`Processed ${filename} -> ${outfile} (${formattedData.length} records)`);
}

processFile('forecast.xlsx', 'forecast.json');
processFile('products.xlsx', 'products.json');
processFile('holidays.xlsx', 'holidays.json');
processFile('future_promos.xlsx', 'future_promos.json');

console.log('Adapter complete.');
