const fs = require('fs');
const path = require('path');

const file = path.join('c:/Users/karki/smartweb/frontend/src/data/mockData.ts');
let content = fs.readFileSync(file, 'utf8');

const products = [
  "P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008", 
  "P009", "P010", "P011", "P012", "P013", "P014", "P015"
];

const accuracy = [];
const backtest = [];

products.forEach(p => {
  const mae_b = 20 + Math.random() * 50;
  const wape_b = 0.3 + Math.random() * 0.4;
  const impr = Math.random() * 0.4; // up to 40% improvement
  const mae_m = mae_b * (1 - impr);
  const wape_m = wape_b * (1 - impr);

  accuracy.push(`  {
    product_id: "${p}",
    mae_model: ${mae_m.toFixed(2)},
    wape_model: ${(wape_m * 100).toFixed(2)},
    mae_baseline: ${mae_b.toFixed(2)},
    wape_baseline: ${(wape_b * 100).toFixed(2)},
    improvement_pct: ${(impr * 100).toFixed(2)},
  }`);

  const naive_so = Math.floor(Math.random() * 20) + 10;
  const naive_short = naive_so * (10 + Math.random() * 20);
  const naive_fr = 70 + Math.random() * 15;
  const naive_avg = 100 + Math.random() * 500;
  
  const smart_so = Math.max(0, naive_so - Math.floor(Math.random() * 10) - 5);
  const smart_short = smart_so * (5 + Math.random() * 10);
  const smart_fr = naive_fr + Math.random() * 10;
  const smart_avg = naive_avg * (0.6 + Math.random() * 0.3); // Less inventory

  backtest.push(`  { product_id: "${p}", policy: "NAIVE", stockout_days: ${naive_so}, units_short: ${naive_short.toFixed(0)}, fill_rate_pct: ${naive_fr.toFixed(2)}, avg_on_hand_units: ${naive_avg.toFixed(0)} }`);
  backtest.push(`  { product_id: "${p}", policy: "SMART", stockout_days: ${smart_so}, units_short: ${smart_short.toFixed(0)}, fill_rate_pct: ${Math.min(99.9, smart_fr).toFixed(2)}, avg_on_hand_units: ${smart_avg.toFixed(0)} }`);
});

content += `\nexport const MOCK_ACCURACY: import('../types/contracts').Accuracy[] = [\n${accuracy.join(',\n')}\n];\n`;
content += `\nexport const MOCK_BACKTEST: import('../types/contracts').InventoryBacktest[] = [\n${backtest.join(',\n')}\n];\n`;

fs.writeFileSync(file, content);
