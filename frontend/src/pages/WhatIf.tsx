import * as React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { runScenario } from '../services/api';
import type { ScenarioInputs } from '../services/api';
import type { ScenarioComparison } from '../types/contracts';
import { Play, ArrowRight, Activity, Cpu } from 'lucide-react';

export default function WhatIf() {
  const [inputs, setInputs] = React.useState<ScenarioInputs>({
    uplift_pct: 0,
    start_date: '2024-03-01',
    end_date: '2024-03-31',
    product_ids: [], // empty means all
    lead_time_extra_days: 0,
    service_level: 0.95,
    review_period_days: 7
  });

  const [loading, setLoading] = React.useState(false);
  const [results, setResults] = React.useState<ScenarioComparison[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Optionally pre-fetch data or keep as empty if not needed right now
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setInputs(prev => ({
      ...prev,
      [name]: name === 'uplift_pct' || name === 'lead_time_extra_days' || name === 'service_level' || name === 'review_period_days' 
        ? Number(value) 
        : value
    }));
  };

  const executeScenario = async (overrideInputs?: ScenarioInputs) => {
    const payload = overrideInputs || inputs;
    setLoading(true);
    setError(null);
    try {
      const data = await runScenario(payload);
      setResults(data);
    } catch (err: any) {
      setError(err.message || "Failed to run scenario");
    } finally {
      setLoading(false);
    }
  };

  const applyPreset = (preset: 'baseline' | 'diwali' | 'delay' | 'combined') => {
    let presetInputs = { ...inputs, product_ids: [] };
    if (preset === 'baseline') {
      presetInputs.uplift_pct = 0;
      presetInputs.lead_time_extra_days = 0;
    } else if (preset === 'diwali') {
      presetInputs.uplift_pct = 30;
      presetInputs.lead_time_extra_days = 0;
    } else if (preset === 'delay') {
      presetInputs.uplift_pct = 0;
      presetInputs.lead_time_extra_days = 5;
    } else if (preset === 'combined') {
      presetInputs.uplift_pct = 25;
      presetInputs.lead_time_extra_days = 7;
    }
    setInputs(presetInputs);
    executeScenario(presetInputs);
  };

  // Derived Summary Metrics
  const changedProductsCount = results ? results.filter(r => r.delta !== 0 || r.status_before !== r.status_after).length : 0;
  const totalExtraUnits = results ? results.reduce((acc, r) => acc + r.delta, 0) : 0;
  const criticalCountAfter = results ? results.filter(r => r.status_after === 'CRITICAL').length : 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">What-If Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Simulate supply chain shocks to evaluate inventory resilience.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Controls */}
        <div className="lg:col-span-4 space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-lg flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                Scenario Presets
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <button onClick={() => applyPreset('baseline')} className="w-full text-left px-4 py-2 text-sm border border-gray-200 rounded-md hover:bg-gray-50 transition-colors">
                <strong>Baseline</strong> - No anomalies
              </button>
              <button onClick={() => applyPreset('diwali')} className="w-full text-left px-4 py-2 text-sm border border-blue-200 bg-blue-50/50 rounded-md hover:bg-blue-50 transition-colors text-blue-900">
                <strong>Demand Spike</strong> - 30% Uplift
              </button>
              <button onClick={() => applyPreset('delay')} className="w-full text-left px-4 py-2 text-sm border border-amber-200 bg-amber-50/50 rounded-md hover:bg-amber-50 transition-colors text-amber-900">
                <strong>Supplier Delay</strong> - +5 Days Lead Time
              </button>
              <button onClick={() => applyPreset('combined')} className="w-full text-left px-4 py-2 text-sm border border-red-200 bg-red-50/50 rounded-md hover:bg-red-50 transition-colors text-red-900">
                <strong>Combined Stress</strong> - 25% Uplift + 7d Delay
              </button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-lg">Custom Scenario Inputs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="uplift_pct" className="text-xs font-semibold text-gray-600 uppercase">Uplift (%)</label>
                  <input id="uplift_pct" type="number" name="uplift_pct" value={inputs.uplift_pct} onChange={handleInputChange} className="w-full border-gray-300 rounded-md shadow-sm text-sm p-2 border focus:border-primary focus:ring-1 focus:ring-primary outline-none" />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="lead_time_extra_days" className="text-xs font-semibold text-gray-600 uppercase">Supplier Delay (Days)</label>
                  <input id="lead_time_extra_days" type="number" name="lead_time_extra_days" value={inputs.lead_time_extra_days} onChange={handleInputChange} className="w-full border-gray-300 rounded-md shadow-sm text-sm p-2 border focus:border-primary focus:ring-1 focus:ring-primary outline-none" />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="start_date" className="text-xs font-semibold text-gray-600 uppercase">Start Date</label>
                  <input id="start_date" type="date" name="start_date" value={inputs.start_date} onChange={handleInputChange} className="w-full border-gray-300 rounded-md shadow-sm text-sm p-2 border focus:border-primary focus:ring-1 focus:ring-primary outline-none" />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="end_date" className="text-xs font-semibold text-gray-600 uppercase">End Date</label>
                  <input id="end_date" type="date" name="end_date" value={inputs.end_date} onChange={handleInputChange} className="w-full border-gray-300 rounded-md shadow-sm text-sm p-2 border focus:border-primary focus:ring-1 focus:ring-primary outline-none" />
                </div>
              </div>

              <div className="pt-2">
                <button 
                  onClick={() => executeScenario()} 
                  disabled={loading}
                  className="w-full flex justify-center items-center gap-2 bg-primary text-white py-2.5 rounded-md hover:bg-primary-dark transition-colors disabled:opacity-70 font-medium"
                >
                  {loading ? (
                    <span className="animate-pulse">Evaluating Scenario...</span>
                  ) : (
                    <>
                      <Play className="h-4 w-4" /> Run Custom Scenario
                    </>
                  )}
                </button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Results */}
        <div className="lg:col-span-8 space-y-6">
          {error && <ErrorState title="Failed to Run Scenario" message={error} onRetry={() => executeScenario()} className="bg-white rounded-lg shadow-sm border border-gray-200" />}

          {!results && !loading && !error && (
            <EmptyState 
              title="No Scenario Active" 
              message="Configure and run a scenario to see the impact on inventory."
              icon={<Activity className="h-10 w-10 text-gray-300" />}
              className="bg-white rounded-lg shadow-sm border border-gray-200"
            />
          )}

          {loading && (
             <LoadingState 
               title="Simulating constraints..." 
               message="Evaluating impact of the selected parameters." 
               className="bg-white rounded-lg shadow-sm border border-gray-200"
             />
          )}

          {results && !loading && (
            <>
              {/* Copilot Explanation */}
              <Card className="bg-gradient-to-r from-indigo-50 to-blue-50 border-indigo-100 shadow-sm">
                <CardContent className="p-5 flex items-start gap-4">
                  <div className="bg-indigo-100 p-2 rounded-lg text-indigo-700 shrink-0">
                    <Cpu className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-indigo-900 uppercase tracking-wider">AI Scenario Intelligence</h3>
                    <p className="text-sm text-indigo-800">
                      Under this scenario ({inputs.uplift_pct}% demand uplift, {inputs.lead_time_extra_days} days supplier delay), 
                      <strong> {changedProductsCount} products</strong> require reorder adjustments. 
                      An additional <strong>{totalExtraUnits} units</strong> must be ordered across the portfolio to maintain service levels. 
                      There are {criticalCountAfter} critical items projected under these conditions.
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Before vs After Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                 <Card>
                    <CardContent className="p-4 space-y-1">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Impacted SKUs</p>
                      <p className="text-2xl font-bold text-gray-900">{changedProductsCount}</p>
                    </CardContent>
                 </Card>
                 <Card>
                    <CardContent className="p-4 space-y-1">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Extra Units Req.</p>
                      <p className={`text-2xl font-bold ${totalExtraUnits > 0 ? 'text-amber-600' : 'text-gray-900'}`}>
                        {totalExtraUnits > 0 ? `+${totalExtraUnits}` : totalExtraUnits}
                      </p>
                    </CardContent>
                 </Card>
                 <Card>
                    <CardContent className="p-4 space-y-1">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Baseline Critical</p>
                      <p className="text-2xl font-bold text-gray-900">{results.filter(r => r.status_before === 'CRITICAL').length}</p>
                    </CardContent>
                 </Card>
                 <Card className={criticalCountAfter > results.filter(r => r.status_before === 'CRITICAL').length ? 'bg-red-50 border-red-200' : ''}>
                    <CardContent className="p-4 space-y-1">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Scenario Critical</p>
                      <p className={`text-2xl font-bold ${criticalCountAfter > 0 ? 'text-red-600' : 'text-gray-900'}`}>{criticalCountAfter}</p>
                    </CardContent>
                 </Card>
              </div>

              {/* Comparison Table */}
              <Card>
                <CardHeader className="pb-0">
                  <CardTitle>Impact Comparison</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto mt-4 p-0">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-gray-50 text-gray-500 border-y border-gray-200">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Product</th>
                        <th className="px-4 py-3 font-semibold">Status (Before → After)</th>
                        <th className="px-4 py-3 font-semibold text-right">Order Qty (Before)</th>
                        <th className="px-4 py-3 font-semibold text-right">Order Qty (After)</th>
                        <th className="px-4 py-3 font-semibold text-right">Delta</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {results.map((row) => {
                        const statusChanged = row.status_before !== row.status_after;
                        const qtyChanged = row.delta !== 0;
                        return (
                          <tr key={row.product_id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 font-medium text-gray-900">
                              {row.name} <span className="text-xs text-gray-400 font-normal ml-1">({row.product_id})</span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <StatusIndicator status={row.status_before as any} />
                                {statusChanged && (
                                  <>
                                    <ArrowRight className="h-3 w-3 text-gray-400" />
                                    <StatusIndicator status={row.status_after as any} />
                                  </>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right text-gray-600">{row.order_qty_before}</td>
                            <td className={`px-4 py-3 text-right font-medium ${qtyChanged ? 'text-amber-600' : 'text-gray-900'}`}>
                              {row.order_qty_after}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {qtyChanged ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                                  +{row.delta}
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                      {results.length === 0 && (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                            No products match the selected criteria.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
