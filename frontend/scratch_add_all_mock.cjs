const fs = require('fs');
const path = require('path');

const file = path.join('c:/Users/karki/smartweb/frontend/src/data/mockData.ts');
let content = fs.readFileSync(file, 'utf8');

// Insert an 'ALL' record at the beginning of MOCK_ACCURACY
const accAll = `  {
    product_id: "ALL",
    mae_model: 25.50,
    wape_model: 32.10,
    mae_baseline: 35.00,
    wape_baseline: 45.50,
    improvement_pct: 29.45,
  },`;

content = content.replace("export const MOCK_ACCURACY: import('../types/contracts').Accuracy[] = [", "export const MOCK_ACCURACY: import('../types/contracts').Accuracy[] = [\n" + accAll);

const btAllNaive = `  { product_id: "ALL", policy: "NAIVE", stockout_days: 120, units_short: 4500, fill_rate_pct: 75.50, avg_on_hand_units: 8500 },`;
const btAllSmart = `  { product_id: "ALL", policy: "SMART", stockout_days: 45, units_short: 1200, fill_rate_pct: 94.20, avg_on_hand_units: 6200 },`;

content = content.replace("export const MOCK_BACKTEST: import('../types/contracts').InventoryBacktest[] = [", "export const MOCK_BACKTEST: import('../types/contracts').InventoryBacktest[] = [\n" + btAllNaive + "\n" + btAllSmart);

fs.writeFileSync(file, content);
