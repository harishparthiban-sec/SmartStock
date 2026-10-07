import * as React from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { getProduct, getProductInventory, getForecasts, getHolidays } from '../services/api';
import type { Product, InventoryResult, Forecast, Holiday } from '../types/contracts';
import { ArrowLeft, Package, Clock, ShieldAlert, CheckCircle2, TrendingUp, Calendar, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

export default function ProductDetail() {
  const { productId } = useParams<{ productId: string }>();
  
  const [loading, setLoading] = React.useState(true);
  const [product, setProduct] = React.useState<Product | null>(null);
  const [inventory, setInventory] = React.useState<InventoryResult | null>(null);
  const [forecasts, setForecasts] = React.useState<Forecast[]>([]);
  const [holidays, setHolidays] = React.useState<Holiday[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function loadData() {
      if (!productId) return;
      setLoading(true);
      try {
        const [pData, invData, fcData, holData] = await Promise.all([
          getProduct(productId),
          getProductInventory(productId),
          getForecasts(productId),
          getHolidays()
        ]);
        setProduct(pData);
        setInventory(invData);
        setForecasts(fcData);
        setHolidays(holData);
      } catch (err) {
        setError("Failed to load product details.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [productId]);

  if (loading) return <LoadingState title="Loading Product Data" message={`Please wait while we fetch information for ${productId}.`} />;
  if (error) return <ErrorState title="Failed to Load Product" message={error} onRetry={() => window.location.reload()} />;

  if (!product || !inventory) {
    return (
      <EmptyState 
        title="Product Not Found" 
        message={`We couldn't find the data for ${productId}. It might not exist in the current mock data set.`}
        icon={<ShieldAlert className="mx-auto h-12 w-12 text-gray-300" />}
      />
    );
  }

  // Derived values for chart
  const chartData = forecasts.map(f => ({
    name: f.date,
    Expected: f.yhat,
    Bounds: [f.yhat_lower, f.yhat_upper]
  }));

  const isOverstocked = inventory.status === 'OVERSTOCKED';
  const needsAttention = inventory.status === 'CRITICAL' || inventory.status === 'WARNING';

  return (
    <div className="space-y-6 pb-8 max-w-6xl mx-auto">
      {/* Navigation */}
      <nav>
        <Link to="/" className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="mr-1 h-4 w-4" /> Back to Overview
        </Link>
      </nav>

      {/* 1. PRODUCT HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-gray-200 pb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-sm font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded uppercase tracking-wider">{product.category}</span>
            <span className="text-sm text-gray-400">ID: {product.product_id}</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">{product.name}</h1>
        </div>
        <div className="flex items-center gap-4 bg-white p-3 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-right">
            <p className="text-xs text-gray-500 uppercase font-semibold">System Status</p>
            <StatusIndicator status={inventory.status} className="mt-1" />
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-12">
        {/* Left Column: Details & Charts */}
        <div className="md:col-span-8 space-y-6">
          
          {/* 2. INVENTORY SUMMARY */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5 text-gray-500" />
                Inventory Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Current Stock</p>
                  <p className="text-lg font-semibold">{inventory.current_stock} <span className="text-sm text-gray-400 font-normal">units</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">On Order</p>
                  <p className="text-lg font-semibold">{inventory.on_order} <span className="text-sm text-gray-400 font-normal">units</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Safety Stock</p>
                  <p className="text-lg font-semibold">{inventory.safety_stock} <span className="text-sm text-gray-400 font-normal">units</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Reorder Point</p>
                  <p className="text-lg font-semibold">{inventory.reorder_point} <span className="text-sm text-gray-400 font-normal">units</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Avg Daily Demand</p>
                  <p className="text-lg font-semibold">{inventory.avg_daily_demand} <span className="text-sm text-gray-400 font-normal">units/d</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Stock Cover</p>
                  <p className="text-lg font-semibold">{inventory.days_of_stock_left} <span className="text-sm text-gray-400 font-normal">days</span></p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 font-medium">Lead Time</p>
                  <p className="text-lg font-semibold">{inventory.lead_time_days} <span className="text-sm text-gray-400 font-normal">days</span></p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 3. FORECAST VISUALIZATION */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-indigo-500" />
                  Demand Forecast
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {forecasts.length === 0 ? (
                <div className="h-64 flex items-center justify-center bg-gray-50 rounded border border-dashed border-gray-200">
                  <p className="text-gray-500">Forecast data not available for this product.</p>
                </div>
              ) : (
                <div className="h-72 w-full mt-4" role="img" aria-label="Line chart showing demand forecast with uncertainty bounds">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fontSize: 12, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                      <Tooltip 
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: any, name: any) => {
                          if (name === "Bounds") return [`${value[0]} - ${value[1]} units`, "Uncertainty Range"];
                          return [`${value} units`, name];
                        }}
                      />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                      <Area 
                        type="monotone" 
                        dataKey="Bounds" 
                        fill="#e0e7ff" 
                        stroke="none" 
                        name="Uncertainty Range"
                      />
                      <Line 
                        type="monotone" 
                        dataKey="Expected" 
                        stroke="#4f46e5" 
                        strokeWidth={2} 
                        dot={{ r: 4, fill: '#4f46e5', strokeWidth: 0 }} 
                        activeDot={{ r: 6 }} 
                        name="Expected Demand"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 4. HISTORICAL DEMAND (Stubbed as unavailable) */}
          <Card>
            <CardHeader>
              <CardTitle className="text-gray-500 text-sm font-medium uppercase tracking-wider">Historical Demand</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-gray-500 bg-gray-50 p-4 rounded-lg border border-gray-100">
                Historical sales data is not currently available in the active mock contract.
              </div>
            </CardContent>
          </Card>

        </div>

        {/* Right Column: Decisions & Intelligence */}
        <div className="md:col-span-4 space-y-6">

          {/* 8. REORDER RECOMMENDATION & 9. OVERSTOCK INTELLIGENCE */}
          {isOverstocked ? (
            <Card className="border-blue-200 bg-blue-50/30 shadow-md">
              <CardHeader className="pb-3 border-b border-blue-100 bg-blue-50/50">
                <CardTitle className="text-blue-900 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-blue-600" />
                  Overstock Intelligence
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5 space-y-4">
                <div className="space-y-1">
                  <p className="text-sm text-gray-500">Recommended Action</p>
                  <p className="text-xl font-bold text-gray-900">Hold Orders</p>
                </div>
                <div className="space-y-2 text-sm text-gray-700 bg-white p-3 rounded border border-blue-100">
                  <p><strong>Current Stock:</strong> {inventory.current_stock} units</p>
                  <p><strong>Stock Cover:</strong> {inventory.days_of_stock_left} days</p>
                  <p className="mt-2 text-blue-800 font-medium">{inventory.reason}</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className={needsAttention ? "border-red-200 bg-red-50/30 shadow-md" : "border-emerald-200 bg-emerald-50/30 shadow-md"}>
              <CardHeader className={`pb-3 border-b ${needsAttention ? "border-red-100 bg-red-50/50" : "border-emerald-100 bg-emerald-50/50"}`}>
                <CardTitle className={`flex items-center gap-2 ${needsAttention ? "text-red-900" : "text-emerald-900"}`}>
                  <AlertTriangle className={`h-5 w-5 ${needsAttention ? "text-red-600" : "text-emerald-600"}`} />
                  Reorder Recommendation
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5 space-y-5">
                <div className="space-y-1">
                  <p className="text-sm text-gray-500">Recommended Order Qty</p>
                  <p className="text-3xl font-bold text-gray-900">{inventory.order_qty > 0 ? `${inventory.order_qty} units` : 'None'}</p>
                  {inventory.order_value > 0 && <p className="text-sm font-medium text-gray-500">Est. Value: ${inventory.order_value.toLocaleString()}</p>}
                </div>

                {inventory.order_qty > 0 && (
                  <div className="space-y-3 bg-white p-4 rounded-lg border shadow-sm">
                    <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                      <span className="text-sm text-gray-500">Order By</span>
                      <span className="font-semibold text-red-600">{inventory.order_by_date}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Expected Arrival</span>
                      <span className="font-medium text-gray-900">{inventory.expected_arrival_date}</span>
                    </div>
                  </div>
                )}
                
                {/* 7. WHY ORDER NOW? */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wide">Why this recommendation?</h4>
                  <ul className="text-sm text-gray-700 space-y-2 list-disc pl-4 marker:text-gray-400">
                    <li>{inventory.reason}</li>
                    {inventory.current_stock <= inventory.reorder_point && (
                      <li>Current inventory ({inventory.current_stock}) has breached the reorder threshold ({inventory.reorder_point}).</li>
                    )}
                    {inventory.order_qty > 0 && (
                      <li>Ordering {inventory.order_qty} units ensures cover through the {inventory.lead_time_days}-day lead time.</li>
                    )}
                  </ul>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 6. STOCKOUT EARLY-WARNING */}
          {needsAttention && inventory.stockout_date && (
            <Card className="border-amber-200">
              <CardHeader className="pb-3 bg-amber-50/50">
                <CardTitle className="text-amber-900 flex items-center gap-2 text-sm">
                  <Clock className="h-4 w-4" />
                  Stockout Timeline Risk
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="relative pl-4 space-y-4 border-l-2 border-gray-200">
                  <div className="relative">
                    <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full bg-gray-300 border-2 border-white"></div>
                    <p className="text-xs font-semibold text-gray-500 uppercase">Today</p>
                    <p className="text-sm font-medium">{inventory.current_stock} units in stock</p>
                  </div>
                  <div className="relative">
                    <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full bg-amber-400 border-2 border-white"></div>
                    <p className="text-xs font-semibold text-gray-500 uppercase">Order Deadline</p>
                    <p className="text-sm font-medium text-amber-700">{inventory.order_by_date}</p>
                  </div>
                  <div className="relative">
                    <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full bg-red-500 border-2 border-white"></div>
                    <p className="text-xs font-semibold text-gray-500 uppercase">Projected Stockout</p>
                    <p className="text-sm font-bold text-red-600">{inventory.stockout_date}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 5. HOLIDAY / PROMOTION SIGNALS */}
          {holidays.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2 text-gray-700">
                  <Calendar className="h-4 w-4 text-gray-400" />
                  External Demand Signals
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {holidays.map((h, i) => (
                    <div key={i} className="flex justify-between items-center text-sm p-2 bg-gray-50 rounded">
                      <span className="font-medium text-gray-900">{h.holiday_name}</span>
                      <span className="text-gray-500">{h.date}</span>
                    </div>
                  ))}
                  <p className="text-xs text-gray-500 mt-2">These events are factored into the forecasted demand.</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
