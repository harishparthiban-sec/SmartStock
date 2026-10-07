import type { Product, InventoryResult, Forecast, Holiday, ScenarioComparison, DemandAnalogSummary, Accuracy, InventoryBacktest } from '../types/contracts';
import { MOCK_PRODUCTS, MOCK_INVENTORY, MOCK_FORECAST, MOCK_HOLIDAYS, MOCK_ANALOG_SUMMARY, MOCK_ACCURACY, MOCK_BACKTEST } from '../data/mockData';

const USE_REAL_DATA = true;

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export async function getProducts(): Promise<Product[]> {
  await delay(300);
  if (USE_REAL_DATA) {
    try {
      const res = await fetch('/api/products.json');
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Real products not available, falling back to mock.');
    }
  }
  return MOCK_PRODUCTS;
}

export async function getProduct(productId: string): Promise<Product | null> {
  const products = await getProducts();
  const result = products.find(p => p.product_id === productId);
  return result || null;
}

export async function getInventoryStatus(): Promise<InventoryResult[]> {
  await delay(400);
  return MOCK_INVENTORY;
}

export async function getProductInventory(productId: string): Promise<InventoryResult | null> {
  await delay(200);
  const result = MOCK_INVENTORY.find(inv => inv.product_id === productId);
  return result || null;
}

export async function getForecasts(productId: string): Promise<Forecast[]> {
  await delay(300);
  if (USE_REAL_DATA) {
    try {
      const res = await fetch('/api/forecast.json');
      if (res.ok) {
        const data: Forecast[] = await res.json();
        return data.filter(f => f.product_id === productId);
      }
    } catch (e) {
      console.warn('Real forecast not available, falling back to mock.');
    }
  }
  return MOCK_FORECAST.filter(f => f.product_id === productId);
}

export async function getHolidays(): Promise<Holiday[]> {
  await delay(100);
  if (USE_REAL_DATA) {
    try {
      const res = await fetch('/api/holidays.json');
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Real holidays not available, falling back to mock.');
    }
  }
  return MOCK_HOLIDAYS;
}

export interface ScenarioInputs {
  uplift_pct: number;
  start_date: string;
  end_date: string;
  product_ids: string[];
  lead_time_extra_days: number;
  service_level: number;
  review_period_days: number;
}

export async function runScenario(inputs: ScenarioInputs): Promise<ScenarioComparison[]> {
  await delay(600); // Simulate heavy computation
  
  // MOCK LOGIC for frontend service abstraction only.
  // The real app will POST these inputs to the Python Inventory Engine.
  
  if (!inputs.start_date || !inputs.end_date) {
    throw new Error("Start date and End date are required.");
  }
  
  // Baseline means no changes
  const isBaseline = inputs.uplift_pct === 0 && inputs.lead_time_extra_days === 0;

  return MOCK_INVENTORY
    .filter(inv => inputs.product_ids.length === 0 || inputs.product_ids.includes(inv.product_id))
    .map(inv => {
      let afterQty = inv.order_qty;
      let afterStatus = inv.status;
      
      if (!isBaseline) {
        // Mock impact: Higher uplift or longer delay increases required order
        const impactRatio = 1 + (inputs.uplift_pct / 100) + (inputs.lead_time_extra_days * 0.1);
        if (impactRatio > 1 && inv.order_qty > 0) {
           afterQty = Math.round(inv.order_qty * impactRatio);
        } else if (impactRatio > 1 && inv.order_qty === 0) {
           afterQty = Math.round(inv.avg_daily_demand * inputs.lead_time_extra_days);
        }
        
        if (inputs.lead_time_extra_days > 0 && afterStatus === 'HEALTHY') {
           afterStatus = 'WARNING';
        }
        if (inputs.uplift_pct > 20 && afterStatus === 'WARNING') {
           afterStatus = 'CRITICAL';
        }
      }

      return {
        product_id: inv.product_id,
        name: inv.name,
        order_qty_before: inv.order_qty,
        order_qty_after: afterQty,
        delta: afterQty - inv.order_qty,
        status_before: inv.status,
        status_after: afterStatus,
      };
    });
}

export async function getDemandAnalogSummary(productId: string): Promise<DemandAnalogSummary | null> {
  await delay(200);
  const result = MOCK_ANALOG_SUMMARY.find(a => a.product_id === productId);
  return result || null;
}

export async function getAccuracyResults(): Promise<Accuracy[]> {
  await delay(300);
  return MOCK_ACCURACY;
}

export async function getInventoryBacktestResults(): Promise<InventoryBacktest[]> {
  await delay(300);
  return MOCK_BACKTEST;
}

export interface CopilotResponse {
  message: string;
  items?: InventoryResult[];
  intent: string;
}

export async function askCopilot(query: string): Promise<CopilotResponse> {
  await delay(800); // Simulate AI delay
  
  const q = query.toLowerCase();
  
  if (q.includes("order today") || q.includes("what should i order") || q.includes("what to order")) {
    const items = MOCK_INVENTORY.filter(i => i.order_qty > 0 || i.status === 'CRITICAL');
    return {
      message: items.length > 0 ? `I found ${items.length} products requiring attention today.` : "No immediate reorder actions found. Inventory levels are sufficient.",
      items: items.length > 0 ? items : undefined,
      intent: "ORDER_TODAY"
    };
  }
  
  if (q.includes("at risk") || q.includes("stock out") || q.includes("stockout")) {
    const items = MOCK_INVENTORY.filter(i => i.status === 'CRITICAL' || i.status === 'WARNING');
    return {
      message: `Here is the current risk profile of your inventory. Pay immediate attention to ORDER NOW items.`,
      items: items,
      intent: "AT_RISK"
    };
  }

  if (q.includes("overstock") || q.includes("over stock")) {
    const items = MOCK_INVENTORY.filter(i => i.status === 'OVERSTOCKED');
    return {
      message: items.length > 0 ? `I found ${items.length} overstocked products. Review these for potential markdowns.` : "No overstock detected.",
      items: items.length > 0 ? items : undefined,
      intent: "OVERSTOCK"
    };
  }
  
  if (q.includes("why should i order") || q.includes("why order")) {
    // Try to extract a product name
    const matchItem = MOCK_INVENTORY.find(i => q.includes(i.name.toLowerCase()));
    if (matchItem) {
      return {
        message: `Here is the evidence supporting the recommendation for ${matchItem.name}:`,
        items: [matchItem],
        intent: "WHY_ORDER"
      };
    } else {
      return {
        message: "Please specify which product you would like to review (e.g. 'Why should I order Milk 1L?').",
        intent: "WHY_ORDER"
      };
    }
  }
  
  return {
    message: "I'm your mock SmartStock Reorder Copilot. Try asking me 'What should I order today?' or 'Which products are at risk?'",
    intent: "UNKNOWN"
  };
}

