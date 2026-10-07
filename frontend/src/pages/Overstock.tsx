import * as React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { getInventoryStatus, getForecasts } from '../services/api';
import type { InventoryResult, Forecast } from '../types/contracts';
import { PackagePlus, ShieldAlert, TrendingDown, Tag, AlertCircle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function Overstock() {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [overstocked, setOverstocked] = React.useState<InventoryResult[]>([]);
  const [forecasts, setForecasts] = React.useState<Record<string, Forecast[]>>({});

  React.useEffect(() => {
    async function loadData() {
      try {
        const invData = await getInventoryStatus();
        const over = invData.filter(i => i.status === 'OVERSTOCKED').sort((a, b) => b.days_of_stock_left - a.days_of_stock_left);
        setOverstocked(over);

        // Fetch forecasts for all overstocked items
        const fcMap: Record<string, Forecast[]> = {};
        await Promise.all(
          over.map(async (item) => {
            const fcs = await getForecasts(item.product_id);
            fcMap[item.product_id] = fcs;
          })
        );
        setForecasts(fcMap);
      } catch (err) {
        setError("Failed to load overstock intelligence data.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <LoadingState title="Loading Overstock Intelligence" message="Please wait while we analyze your inventory for excess capital." />;
  if (error) return <ErrorState title="Failed to Load Data" message={error} onRetry={() => window.location.reload()} />;

  if (overstocked.length === 0) {
    return (
      <EmptyState 
        title="No Overstock Detected" 
        message="Your inventory is currently running lean. No capital is tied up in excess stock."
        icon={<PackagePlus className="mx-auto h-12 w-12 text-emerald-300" />}
      />
    );
  }

  return (
    <div className="space-y-6 pb-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Overstock Intelligence</h1>
        <p className="text-sm text-gray-500 mt-1">Identify excess inventory, understand demand context, and review Markdown recommendations.</p>
      </div>

      <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-lg flex items-start gap-3 text-sm shadow-sm">
        <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5 text-blue-600" />
        <div>
          <strong className="font-semibold block mb-1">Pricing Recommendation Policy</strong>
          SmartStock provides markdown and pricing suggestions purely as decision-support intelligence. Final pricing decisions remain with the human operator. No product prices are automatically modified.
        </div>
      </div>

      <div className="grid gap-6">
        {overstocked.map((item, index) => {
          const fcs = forecasts[item.product_id] || [];
          const avgDemand = fcs.length > 0 ? (fcs.reduce((acc, f) => acc + f.yhat, 0) / fcs.length).toFixed(1) : item.avg_daily_demand;
          const maxDemand = fcs.length > 0 ? Math.max(...fcs.map(f => f.yhat_upper)) : 0;
          
          // Determine Action Recommendation logic (mock)
          let recommendation = "Hold orders and monitor demand.";
          let actionType = "Monitor";
          if (item.days_of_stock_left > 120) {
            recommendation = "Consider Markdown to liquidate excess stock.";
            actionType = "Markdown";
          } else if (item.current_stock > item.reorder_point * 2) {
            recommendation = "Reduce replenishment frequency.";
            actionType = "Reduce";
          }

          const chartData = fcs.map(f => ({
            name: f.date,
            Expected: f.yhat,
            Bounds: [f.yhat_lower, f.yhat_upper]
          }));

          return (
            <Card key={item.product_id} className={`overflow-hidden border-2 ${index === 0 ? 'border-blue-300 shadow-md' : 'border-gray-200'}`}>
              <div className="grid grid-cols-1 md:grid-cols-12">
                
                {/* Left: Product & Inventory Stats */}
                <div className="md:col-span-4 bg-gray-50 p-5 border-b md:border-b-0 md:border-r border-gray-200">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider bg-white px-2 py-1 rounded border shadow-sm">
                      {item.category}
                    </span>
                    <span className="text-xs text-gray-400">{item.product_id}</span>
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-1">
                    <Link to={`/products/${item.product_id}`} className="hover:underline hover:text-primary transition-colors">
                      {item.name}
                    </Link>
                  </h3>
                  <div className="mb-4"><StatusIndicator status={item.status} /></div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm mt-6">
                    <div className="space-y-1">
                      <p className="text-gray-500 font-medium text-xs uppercase">Current Stock</p>
                      <p className="font-bold text-gray-900 text-lg">{item.current_stock} <span className="font-normal text-sm text-gray-500">units</span></p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-gray-500 font-medium text-xs uppercase">Days of Cover</p>
                      <p className={`font-bold text-lg ${index === 0 ? 'text-blue-700' : 'text-gray-900'}`}>{item.days_of_stock_left} <span className="font-normal text-sm text-gray-500">days</span></p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-gray-500 font-medium text-xs uppercase">On Order</p>
                      <p className="font-medium text-gray-900">{item.on_order}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-gray-500 font-medium text-xs uppercase">Reorder Point</p>
                      <p className="font-medium text-gray-900">{item.reorder_point}</p>
                    </div>
                  </div>
                </div>

                {/* Middle: Demand Context */}
                <div className="md:col-span-5 p-5 border-b md:border-b-0 md:border-r border-gray-200 bg-white">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-1.5">
                    <TrendingDown className="h-4 w-4 text-gray-400" />
                    Demand Context
                  </h4>
                  {fcs.length > 0 ? (
                    <>
                      <div className="h-32 w-full mb-3">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={chartData} margin={{ top: 5, right: 0, left: -25, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                            <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                            <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                            <Tooltip 
                              contentStyle={{ fontSize: '12px', borderRadius: '6px' }}
                              formatter={(value: any, name: any) => [name === "Bounds" ? `${value[0]}-${value[1]}` : value, name]}
                            />
                            <Area type="monotone" dataKey="Bounds" fill="#e0e7ff" stroke="none" />
                            <Area type="monotone" dataKey="Expected" stroke="#4f46e5" fill="none" strokeWidth={2} />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        Expected demand averages <strong>{avgDemand} units/day</strong> over the forecast window, peaking at {maxDemand}. 
                        Current inventory far exceeds this trajectory.
                      </p>
                    </>
                  ) : (
                    <div className="h-full flex items-center justify-center text-sm text-gray-400 bg-gray-50 rounded border border-dashed border-gray-200">
                      Forecast data unavailable.
                    </div>
                  )}
                </div>

                {/* Right: Recommendation */}
                <div className="md:col-span-3 p-5 bg-gradient-to-b from-white to-gray-50">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-1.5">
                    <AlertCircle className="h-4 w-4 text-gray-400" />
                    Action Required
                  </h4>
                  
                  <div className={`p-4 rounded-lg border shadow-sm mb-4 ${actionType === 'Markdown' ? 'bg-blue-600 text-white border-blue-700' : 'bg-white border-gray-200 text-gray-900'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      {actionType === 'Markdown' && <Tag className="h-4 w-4" />}
                      <span className="font-bold">{actionType === 'Markdown' ? 'Review Pricing' : 'Hold Orders'}</span>
                    </div>
                    <p className={`text-sm ${actionType === 'Markdown' ? 'text-blue-100' : 'text-gray-600'}`}>{recommendation}</p>
                  </div>

                  <div className="space-y-2 text-xs">
                    <p className="font-semibold text-gray-700 uppercase tracking-wide">Why?</p>
                    <p className="text-gray-600 leading-relaxed">
                      {item.reason} You have {item.days_of_stock_left} days of stock coverage, which creates capital lock-up risk.
                    </p>
                  </div>
                </div>

              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
