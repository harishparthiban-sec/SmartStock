import * as React from 'react';
import { Link } from 'react-router-dom';
import { getAccuracyResults, getInventoryBacktestResults } from '../services/api';
import type { Accuracy, InventoryBacktest } from '../types/contracts';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { Activity, CheckCircle2, TrendingDown, ArrowRight, BookOpen, Info } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

export default function ModelImpact() {
  const [accuracy, setAccuracy] = React.useState<Accuracy[]>([]);
  const [backtest, setBacktest] = React.useState<InventoryBacktest[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [accData, btData] = await Promise.all([
          getAccuracyResults(),
          getInventoryBacktestResults()
        ]);
        setAccuracy(accData);
        setBacktest(btData);
      } catch (e) {
        setError("Failed to load impact metrics.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <LoadingState title="Loading Validation Metrics" message="Please wait while we fetch the model and impact data." />;
  if (error) return <ErrorState title="Failed to Load Data" message={error} onRetry={() => window.location.reload()} />;
  if (accuracy.length === 0 || backtest.length === 0) return <EmptyState title="Model evaluation data is not available" message="Please connect the forecasting engine or wait for backtest results." />;

  const accAll = accuracy.find(a => a.product_id === 'ALL');
  const accProducts = accuracy.filter(a => a.product_id !== 'ALL').sort((a, b) => b.improvement_pct - a.improvement_pct);

  const btAllNaive = backtest.find(b => b.product_id === 'ALL' && b.policy === 'NAIVE');
  const btAllSmart = backtest.find(b => b.product_id === 'ALL' && b.policy === 'SMART');
  
  const btProductsRaw = backtest.filter(b => b.product_id !== 'ALL');
  const btProductsUnique = Array.from(new Set(btProductsRaw.map(b => b.product_id)));

  const chartDataWAPE = accProducts.slice(0, 10).map(p => ({
    name: p.product_id,
    Model: p.wape_model,
    Baseline: p.wape_baseline,
  }));

  const chartDataStockouts = btProductsUnique.slice(0, 10).map(pid => {
    const n = btProductsRaw.find(b => b.product_id === pid && b.policy === 'NAIVE');
    const s = btProductsRaw.find(b => b.product_id === pid && b.policy === 'SMART');
    return {
      name: pid,
      NAIVE: n?.stockout_days || 0,
      SMART: s?.stockout_days || 0
    };
  });

  return (
    <div className="max-w-7xl mx-auto pb-12 space-y-12">
      
      {/* 1. Page Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-indigo-600" />
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Model & Impact</h1>
        </div>
        <p className="text-gray-500">
          Validation of forecasting quality and operational inventory impact. <span className="inline-block bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded font-medium ml-2">Demo data — real outputs will connect in integration</span>
        </p>
      </div>

      {/* 20. Methodology Notes */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-5">
        <h3 className="text-sm font-bold text-indigo-900 uppercase tracking-wide mb-2 flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Evaluation Context
        </h3>
        <p className="text-sm text-indigo-800">
          <strong>Forecast evaluation</strong> uses a holdout period to calculate error compared to a baseline. 
          <br/>
          <strong>Inventory evaluation</strong> backtests the actual proposed <em>SMART</em> policy against the current <em>NAIVE</em> rules to measure service levels and working capital tradeoffs.
        </p>
      </div>

      <hr className="border-gray-200" />

      {/* FORECAST MODEL PERFORMANCE SECTION */}
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-gray-900">Forecast Model Performance</h2>
        </div>
        
        {/* 8. Accuracy Interpretation */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
            <strong className="block text-gray-900 mb-1">MAE</strong>
            Average absolute prediction error (units).
          </div>
          <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
            <strong className="block text-gray-900 mb-1">WAPE</strong>
            Weighted absolute percentage error. Lower is better.
          </div>
          <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
            <strong className="block text-gray-900 mb-1">Improvement</strong>
            Reduction in error compared with the baseline model.
          </div>
        </div>

        {/* 7. Forecast Accuracy Summary */}
        {accAll && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Model MAE</p>
                <p className="text-2xl font-semibold text-gray-900 mt-1">{accAll.mae_model.toFixed(2)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Model WAPE</p>
                <p className="text-2xl font-semibold text-indigo-600 mt-1">{accAll.wape_model.toFixed(1)}%</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Baseline MAE</p>
                <p className="text-2xl font-semibold text-gray-400 mt-1">{accAll.mae_baseline.toFixed(2)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Baseline WAPE</p>
                <p className="text-2xl font-semibold text-gray-400 mt-1">{accAll.wape_baseline.toFixed(1)}%</p>
              </CardContent>
            </Card>
            <Card className="bg-emerald-50 border-emerald-100">
              <CardContent className="p-4">
                <p className="text-xs font-bold text-emerald-700 uppercase tracking-wide">Improvement</p>
                <p className="text-2xl font-bold text-emerald-700 mt-1 flex items-center gap-1">
                  <TrendingDown className="h-5 w-5" />
                  {accAll.improvement_pct.toFixed(1)}%
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 9. SmartStock vs Baseline Chart */}
        <Card>
          <CardHeader>
            <CardTitle>SmartStock vs Baseline (WAPE %)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartDataWAPE} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} />
                  <YAxis axisLine={false} tickLine={false} tickFormatter={(val) => `${val}%`} />
                  <Tooltip cursor={{fill: '#f3f4f6'}} formatter={(value: any) => [`${Number(value).toFixed(1)}%`]} />
                  <Legend />
                  <Bar dataKey="Baseline" fill="#d1d5db" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Model" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* 10. Product-Level Accuracy */}
        <Card>
          <CardHeader>
            <CardTitle>Product-Level Accuracy</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 font-medium rounded-tl-lg">Product ID</th>
                    <th className="px-4 py-3 font-medium text-right">Model MAE</th>
                    <th className="px-4 py-3 font-medium text-right">Baseline MAE</th>
                    <th className="px-4 py-3 font-medium text-right">Model WAPE</th>
                    <th className="px-4 py-3 font-medium text-right">Baseline WAPE</th>
                    <th className="px-4 py-3 font-medium text-right rounded-tr-lg">Improvement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {accProducts.map(item => (
                    <tr key={item.product_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium">
                        <Link to={`/products/${item.product_id}`} className="text-indigo-600 hover:underline flex items-center gap-1">
                          {item.product_id} <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right">{item.mae_model.toFixed(1)}</td>
                      <td className="px-4 py-3 text-right text-gray-400">{item.mae_baseline.toFixed(1)}</td>
                      <td className="px-4 py-3 text-right font-medium">{item.wape_model.toFixed(1)}%</td>
                      <td className="px-4 py-3 text-right text-gray-400">{item.wape_baseline.toFixed(1)}%</td>
                      <td className="px-4 py-3 text-right">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${item.improvement_pct > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                          {item.improvement_pct > 0 ? '+' : ''}{item.improvement_pct.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      <hr className="border-gray-200" />

      {/* INVENTORY POLICY PERFORMANCE SECTION */}
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-gray-900">Inventory Policy Performance</h2>
        </div>

        {/* 15 & 16. Performance Interpretation */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
            <strong className="block text-gray-900 mb-1 flex items-center gap-1"><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Availability Target</strong>
            Fewer <strong>stockout days</strong> and <strong>units short</strong> indicate better fulfillment. A higher <strong>fill rate</strong> is preferred.
          </div>
          <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700">
            <strong className="block text-gray-900 mb-1 flex items-center gap-1"><Info className="h-4 w-4 text-blue-600" /> Working Capital</strong>
            <strong>Average On-Hand</strong> shows inventory investment. Lower inventory is not automatically "better" if it hurts service levels; the goal is optimal balance.
          </div>
        </div>

        {/* 13. Inventory KPI Cards */}
        {btAllNaive && btAllSmart && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            <Card className="border-gray-200 shadow-sm">
              <CardHeader className="bg-gray-50 border-b border-gray-100 py-3">
                <CardTitle className="text-sm font-bold text-gray-500 uppercase flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-gray-400"></span> NAIVE Policy
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500">Stockout Days</p>
                  <p className="text-xl font-medium">{btAllNaive.stockout_days}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Units Short</p>
                  <p className="text-xl font-medium">{btAllNaive.units_short.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Fill Rate</p>
                  <p className="text-xl font-medium">{btAllNaive.fill_rate_pct.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Avg On-Hand</p>
                  <p className="text-xl font-medium">{btAllNaive.avg_on_hand_units.toLocaleString()}</p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-indigo-200 shadow-sm">
              <CardHeader className="bg-indigo-50 border-b border-indigo-100 py-3">
                <CardTitle className="text-sm font-bold text-indigo-700 uppercase flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500"></span> SMART Policy
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-indigo-500">Stockout Days</p>
                  <p className="text-xl font-bold text-indigo-900">{btAllSmart.stockout_days}</p>
                </div>
                <div>
                  <p className="text-xs text-indigo-500">Units Short</p>
                  <p className="text-xl font-bold text-indigo-900">{btAllSmart.units_short.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-indigo-500">Fill Rate</p>
                  <p className="text-xl font-bold text-indigo-900">{btAllSmart.fill_rate_pct.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-indigo-500">Avg On-Hand</p>
                  <p className="text-xl font-bold text-indigo-900">{btAllSmart.avg_on_hand_units.toLocaleString()}</p>
                </div>
              </CardContent>
            </Card>

          </div>
        )}

        {/* 14. Policy Comparison Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Stockout Days (NAIVE vs SMART)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartDataStockouts} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} />
                  <YAxis axisLine={false} tickLine={false} />
                  <Tooltip cursor={{fill: '#f3f4f6'}} />
                  <Legend />
                  <Bar dataKey="NAIVE" fill="#9ca3af" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="SMART" fill="#4338ca" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* 17. Product-Level Inventory Performance */}
        <Card>
          <CardHeader>
            <CardTitle>Product-Level Inventory Backtest</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 font-medium rounded-tl-lg">Product ID</th>
                    <th className="px-4 py-3 font-medium">Policy</th>
                    <th className="px-4 py-3 font-medium text-right">Stockout Days</th>
                    <th className="px-4 py-3 font-medium text-right">Units Short</th>
                    <th className="px-4 py-3 font-medium text-right">Fill Rate</th>
                    <th className="px-4 py-3 font-medium text-right rounded-tr-lg">Avg On-Hand</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {btProductsUnique.map(pid => {
                    const naive = btProductsRaw.find(b => b.product_id === pid && b.policy === 'NAIVE');
                    const smart = btProductsRaw.find(b => b.product_id === pid && b.policy === 'SMART');
                    return (
                      <React.Fragment key={pid}>
                        <tr className="hover:bg-gray-50 transition-colors bg-white">
                          <td className="px-4 py-3 font-medium" rowSpan={2}>
                            <Link to={`/products/${pid}`} className="text-indigo-600 hover:underline flex items-center gap-1">
                              {pid} <ArrowRight className="h-3 w-3" />
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-gray-500 text-xs font-bold">NAIVE</td>
                          <td className="px-4 py-3 text-right">{naive?.stockout_days || 0}</td>
                          <td className="px-4 py-3 text-right">{naive?.units_short?.toLocaleString() || 0}</td>
                          <td className="px-4 py-3 text-right">{naive?.fill_rate_pct?.toFixed(1) || 0}%</td>
                          <td className="px-4 py-3 text-right">{naive?.avg_on_hand_units?.toLocaleString() || 0}</td>
                        </tr>
                        <tr className="hover:bg-indigo-50/50 transition-colors bg-indigo-50/30 border-b-2 border-gray-200">
                          <td className="px-4 py-3 text-indigo-700 text-xs font-bold">SMART</td>
                          <td className="px-4 py-3 text-right font-medium">{smart?.stockout_days || 0}</td>
                          <td className="px-4 py-3 text-right font-medium">{smart?.units_short?.toLocaleString() || 0}</td>
                          <td className="px-4 py-3 text-right font-medium">{smart?.fill_rate_pct?.toFixed(1) || 0}%</td>
                          <td className="px-4 py-3 text-right font-medium">{smart?.avg_on_hand_units?.toLocaleString() || 0}</td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
