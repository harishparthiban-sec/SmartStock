import * as React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { getInventoryStatus, getForecasts, getHolidays } from '../services/api';
import type { InventoryResult, Forecast, Holiday } from '../types/contracts';
import { AlertTriangle, TrendingUp, PackageMinus, PackagePlus, ArrowRight, Lightbulb, Calendar } from 'lucide-react';

export default function Overview() {
  const [inventory, setInventory] = React.useState<InventoryResult[]>([]);
  const [forecasts, setForecasts] = React.useState<Forecast[]>([]);
  const [holidays, setHolidays] = React.useState<Holiday[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function loadData() {
      try {
        setError(null);
        const [invData, fcData, holData] = await Promise.all([
          getInventoryStatus(),
          getForecasts("P001"), // Load some sample forecast highlights
          getHolidays()
        ]);
        setInventory(invData);
        setForecasts(fcData);
        setHolidays(holData);
      } catch (err) {
        setError("Failed to load dashboard data.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <LoadingState title="Loading Command Center" message="Please wait while we gather your AI recommendations." />;
  if (error) return <ErrorState title="Failed to Load Dashboard" message={error} onRetry={() => window.location.reload()} />;
  if (inventory.length === 0) return <EmptyState title="No Inventory Data" message="There are currently no products available to track." />;

  // Derived KPIs
  const criticalCount = inventory.filter(i => i.status === 'CRITICAL').length;
  const warningCount = inventory.filter(i => i.status === 'WARNING').length;
  const overstockedCount = inventory.filter(i => i.status === 'OVERSTOCKED').length;
  const totalOrderValue = inventory.reduce((sum, item) => sum + (item.order_value || 0), 0);
  
  const requiresAction = inventory.filter(i => i.status === 'CRITICAL' || i.status === 'WARNING');
  const overstocked = inventory.filter(i => i.status === 'OVERSTOCKED');

  return (
    <div className="space-y-8 pb-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Command Center</h1>
        <p className="text-sm text-gray-500">AI-driven reorder recommendations and stockout prevention.</p>
      </div>
      
      {/* 1. KPI SUMMARY */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between space-y-0 pb-2">
              <p className="text-sm font-medium text-gray-500">Action Required</p>
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{criticalCount + warningCount}</div>
            <p className="text-xs text-gray-500 mt-1">Products needing reorder</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between space-y-0 pb-2">
              <p className="text-sm font-medium text-gray-500">Stockout Risk</p>
              <PackageMinus className="h-4 w-4 text-red-500" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{criticalCount}</div>
            <p className="text-xs text-gray-500 mt-1">Critical stockout trajectory</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between space-y-0 pb-2">
              <p className="text-sm font-medium text-gray-500">Overstocked</p>
              <PackagePlus className="h-4 w-4 text-blue-500" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{overstockedCount}</div>
            <p className="text-xs text-gray-500 mt-1">Capital tied up in excess</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between space-y-0 pb-2">
              <p className="text-sm font-medium text-gray-500">Total Recommended Order</p>
              <TrendingUp className="h-4 w-4 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-gray-900">${totalOrderValue.toLocaleString()}</div>
            <p className="text-xs text-gray-500 mt-1">Based on optimal reorder points</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-12">
        {/* Left Column: Alerts and Reorder List */}
        <div className="md:col-span-8 space-y-6">
          
          {/* 3 & 4. URGENT ALERTS & STOCKOUT EARLY-WARNING */}
          {requiresAction.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">Urgent Attention Required</h2>
              <div className="grid gap-4">
                {requiresAction.map((item) => (
                  <Card key={item.product_id} className="border-l-4 border-l-red-500">
                    <CardContent className="p-5">
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-lg">
                              <Link to={`/products/${item.product_id}`} className="hover:underline text-gray-900">
                                {item.name} ({item.product_id})
                              </Link>
                            </h3>
                            <StatusIndicator status={item.status} />
                          </div>
                          <p className="text-sm text-gray-600">{item.reason}</p>
                          
                          {/* Visual Early Warning Timeline */}
                          <div className="flex items-center gap-2 text-xs font-medium pt-2 overflow-x-auto pb-2">
                            <span className="bg-gray-100 px-2 py-1 rounded">Today: {item.current_stock}u</span>
                            <ArrowRight className="h-3 w-3 text-gray-400" />
                            <span className="bg-gray-100 px-2 py-1 rounded">Lead Time: {item.lead_time_days}d</span>
                            <ArrowRight className="h-3 w-3 text-gray-400" />
                            <span className="bg-red-50 text-red-700 px-2 py-1 rounded border border-red-200">
                              Stockout: {item.stockout_date}
                            </span>
                          </div>
                        </div>
                        
                        <div className="flex flex-col items-end gap-1 bg-gray-50 p-3 rounded-lg border border-gray-100 shrink-0">
                          <span className="text-xs text-gray-500 uppercase font-semibold">Recommended Action</span>
                          <span className="text-lg font-bold text-gray-900">Order {item.order_qty} units</span>
                          <span className="text-xs text-red-600 font-medium">By {item.order_by_date}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* 5. REORDER PRODUCTS TABLE */}
          <Card>
            <CardHeader>
              <CardTitle>Reorder Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 font-medium rounded-tl-lg">Product</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Stock</th>
                      <th className="px-4 py-3 font-medium">Order Qty</th>
                      <th className="px-4 py-3 font-medium">Order By</th>
                      <th className="px-4 py-3 font-medium rounded-tr-lg">Cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {inventory.map(item => (
                      <tr key={item.product_id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium">
                          <Link to={`/products/${item.product_id}`} className="text-primary hover:underline">
                            {item.name}
                          </Link>
                        </td>
                        <td className="px-4 py-3"><StatusIndicator status={item.status} /></td>
                        <td className="px-4 py-3">{item.current_stock}</td>
                        <td className="px-4 py-3 font-medium">{item.order_qty > 0 ? item.order_qty : '-'}</td>
                        <td className="px-4 py-3">{item.order_qty > 0 ? item.order_by_date : '-'}</td>
                        <td className="px-4 py-3">{item.order_value > 0 ? `$${item.order_value.toLocaleString()}` : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: AI Copilot, Insights, Signals */}
        <div className="md:col-span-4 space-y-6">
          
          {/* 2. AI REORDER COPILOT */}
          <Card className="bg-gradient-to-br from-indigo-50 to-white border-indigo-100 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-indigo-900">
                <Lightbulb className="h-5 w-5 text-indigo-600" />
                AI Reorder Copilot
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-indigo-800/80">
                Based on current inventory and forecasted demand, here is your AI summary.
              </p>
              <div className="bg-white p-4 rounded-lg border border-indigo-100 shadow-sm text-sm text-gray-700 space-y-3">
                <p>
                  <strong>What should I order today?</strong><br/>
                  You have {criticalCount} critical item(s). Prioritize ordering {inventory.find(i => i.status === 'CRITICAL')?.name || 'urgent items'} today to prevent stockouts before {inventory.find(i => i.status === 'CRITICAL')?.stockout_date || 'next week'}.
                </p>
                <p>
                  <strong>Why should I order more?</strong><br/>
                  The forecast predicts an average daily demand of {inventory.find(i => i.status === 'CRITICAL')?.avg_daily_demand || 0} units for your top risk items, leaving only {inventory.find(i => i.status === 'CRITICAL')?.days_of_stock_left || 0} days of cover.
                </p>
              </div>
              <Link to="/copilot" className="w-full flex justify-center py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm font-medium transition-colors focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                Open AI Reorder Copilot
              </Link>
            </CardContent>
          </Card>

          {/* 7. FORECAST / DEMAND HIGHLIGHTS */}
          {forecasts.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-gray-500" />
                  Forecast Highlight (P001)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {forecasts.slice(0, 3).map((fc, i) => (
                    <div key={i} className="flex justify-between items-center text-sm border-b border-gray-50 pb-2 last:border-0 last:pb-0">
                      <span className="text-gray-600">{fc.date}</span>
                      <div className="text-right">
                        <span className="font-medium text-gray-900">{fc.yhat} units</span>
                        <div className="text-xs text-gray-400">Range: {fc.yhat_lower} - {fc.yhat_upper}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 8. HOLIDAY / PROMOTION SIGNALS */}
          {holidays.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-gray-500" />
                  Upcoming Events
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {holidays.map((h, i) => (
                    <li key={i} className="flex items-center justify-between text-sm bg-gray-50 p-2 rounded border border-gray-100">
                      <span className="font-medium">{h.holiday_name}</span>
                      <span className="text-gray-500">{h.date}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* 6. OVERSTOCK INTELLIGENCE */}
          {overstocked.length > 0 && (
            <Card className="border-blue-100">
              <CardHeader className="pb-3 bg-blue-50/50 rounded-t-xl">
                <CardTitle className="flex items-center gap-2 text-blue-900">
                  <PackagePlus className="h-4 w-4 text-blue-500" />
                  Overstock Intelligence
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 space-y-3">
                {overstocked.map(item => (
                  <div key={item.product_id} className="text-sm border-b border-blue-50 pb-3 last:border-0 last:pb-0">
                    <div className="flex justify-between font-medium">
                      <Link to={`/products/${item.product_id}`} className="hover:underline text-blue-700">
                        {item.name}
                      </Link>
                      <span>{item.current_stock} units</span>
                    </div>
                    <p className="text-gray-500 text-xs mt-1">{item.reason}</p>
                    <p className="text-xs text-gray-400 mt-1">Days of stock: {item.days_of_stock_left}</p>
                  </div>
                ))}
                <div className="pt-2">
                  <Link to="/overstock" className="text-xs font-semibold text-blue-700 hover:text-blue-800 flex items-center gap-1">
                    View Overstock Intelligence <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          )}

        </div>
      </div>
    </div>
  );
}
