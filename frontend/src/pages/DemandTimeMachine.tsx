import * as React from 'react';
import { getProducts, getDemandAnalogSummary } from '../services/api';
import type { Product, DemandAnalogSummary } from '../types/contracts';
import { History, Search, ShieldCheck, ShieldAlert, BarChart3, AlertTriangle, Info, ShieldQuestion } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';

export default function DemandTimeMachine() {
  const [products, setProducts] = React.useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = React.useState<string>('P001');
  const [analogSummary, setAnalogSummary] = React.useState<DemandAnalogSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = React.useState(false);

  React.useEffect(() => {
    async function init() {
      try {
        const prods = await getProducts();
        setProducts(prods);
        if (prods.length > 0) {
          setSelectedProductId(prods[0].product_id);
        }
      } catch (err) {
        setError("Failed to load products.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  React.useEffect(() => {
    if (!selectedProductId) return;
    
    async function loadSummary() {
      setLoadingSummary(true);
      try {
        const summary = await getDemandAnalogSummary(selectedProductId);
        setAnalogSummary(summary);
      } catch (err) {
        console.error(err);
        setAnalogSummary(null);
      } finally {
        setLoadingSummary(false);
      }
    }
    loadSummary();
  }, [selectedProductId]);

  const selectedProduct = products.find(p => p.product_id === selectedProductId);

  const getAgreementBadge = (agreement: string) => {
    switch (agreement) {
      case 'STRONG_AGREEMENT':
      case 'HIGH':
        return <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 px-2 py-1 rounded text-xs font-semibold"><ShieldCheck className="w-3 h-3"/> Strong Agreement</span>;
      case 'AGREEMENT':
      case 'MEDIUM':
        return <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-semibold"><ShieldCheck className="w-3 h-3"/> Agreement</span>;
      case 'CONFLICT':
        return <span className="inline-flex items-center gap-1 bg-rose-100 text-rose-800 px-2 py-1 rounded text-xs font-semibold"><ShieldAlert className="w-3 h-3"/> Conflict</span>;
      case 'LOW':
      case 'NONE':
      default:
        return <span className="inline-flex items-center gap-1 bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs font-semibold"><ShieldQuestion className="w-3 h-3"/> Low / None</span>;
    }
  };

  const getConfidenceColor = (conf: string) => {
    if (conf === 'HIGH') return 'text-emerald-700 bg-emerald-50 border-emerald-200';
    if (conf === 'MEDIUM') return 'text-blue-700 bg-blue-50 border-blue-200';
    return 'text-amber-700 bg-amber-50 border-amber-200';
  };

  if (loading) return <LoadingState title="Loading Demand Time Machine" message="Please wait while we initialize the historical analysis engine." />;
  if (error) return <ErrorState title="Initialization Failed" message={error} onRetry={() => window.location.reload()} />;
  if (products.length === 0) return <EmptyState title="No Products Available" message="There are no products to analyze in the time machine." />;

  return (
    <div className="space-y-6 pb-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-3">
          <History className="h-8 w-8 text-indigo-600" />
          Demand Time Machine
        </h1>
        <p className="text-sm text-gray-500 mt-2 max-w-3xl">
          SmartStock searches historical demand patterns for situations similar to the present. By analyzing past outcomes, we can evaluate the reliability of current forecasts.
        </p>
      </div>

      <Card className="p-4 bg-white border border-gray-200 shadow-sm flex items-center gap-4">
        <Search className="h-5 w-5 text-gray-400" />
        <div className="flex-1">
          <label htmlFor="product-select" className="sr-only">Select Product</label>
          <select
            id="product-select"
            className="block w-full rounded-md border-gray-300 py-2 pl-3 pr-10 text-base focus:border-indigo-500 focus:outline-none focus:ring-indigo-500 sm:text-sm"
            value={selectedProductId}
            onChange={(e) => setSelectedProductId(e.target.value)}
          >
            {products.map(p => (
              <option key={p.product_id} value={p.product_id}>
                {p.name} ({p.product_id}) - {p.category}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {loadingSummary ? (
        <LoadingState title="Analyzing History" message="Scanning historical vectors for matches..." className="min-h-[200px]" />
      ) : analogSummary ? (
        <div className="space-y-6">
          {/* Top Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-5 border-l-4 border-l-indigo-500 shadow-sm">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Best Historical Analog</h3>
              <p className="text-2xl font-bold text-gray-900">{analogSummary.best_match_date}</p>
              <p className="text-sm text-gray-500 mt-1">Similarity Score: <strong className="text-gray-900">{(analogSummary.best_similarity_score * 100).toFixed(0)}%</strong></p>
            </Card>

            <Card className="p-5 shadow-sm">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Analog Confidence</h3>
              <div className={`inline-flex px-3 py-1 mt-1 border rounded-full text-sm font-semibold ${getConfidenceColor(analogSummary.analog_confidence)}`}>
                {analogSummary.analog_confidence} Confidence
              </div>
            </Card>

            <Card className="p-5 shadow-sm">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Forecast Agreement</h3>
              <div className="mt-2">
                {getAgreementBadge(analogSummary.forecast_agreement)}
              </div>
            </Card>
          </div>

          {/* Evidence vs Forecast Panel */}
          <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
            <div className="grid grid-cols-1 md:grid-cols-2">
              
              {/* Left: Historical Evidence */}
              <div className="p-6 border-b md:border-b-0 md:border-r border-gray-200 bg-slate-50">
                <div className="flex items-center gap-2 mb-4">
                  <History className="h-5 w-5 text-slate-500" />
                  <h3 className="text-lg font-bold text-slate-900">Historical Evidence</h3>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-slate-500 uppercase text-xs">Historical Demand Change</p>
                    <p className={`text-xl font-bold mt-1 ${analogSummary.top_3_consensus_growth_pct > 0 ? 'text-emerald-600' : analogSummary.top_3_consensus_growth_pct < 0 ? 'text-rose-600' : 'text-slate-700'}`}>
                      {analogSummary.top_3_consensus_growth_pct > 0 ? '+' : ''}{analogSummary.top_3_consensus_growth_pct}%
                    </p>
                  </div>
                  
                  <div>
                    <p className="text-sm font-medium text-slate-500 uppercase text-xs mb-1">Event Alignment</p>
                    {getAgreementBadge(analogSummary.event_alignment)}
                  </div>
                </div>
              </div>

              {/* Right: Current Forecast */}
              <div className="p-6 bg-white">
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="h-5 w-5 text-indigo-500" />
                  <h3 className="text-lg font-bold text-slate-900">Current Forecast</h3>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-slate-500 uppercase text-xs">Prophet Predicted Change</p>
                    <p className={`text-xl font-bold mt-1 ${analogSummary.prophet_change_pct > 0 ? 'text-emerald-600' : analogSummary.prophet_change_pct < 0 ? 'text-rose-600' : 'text-slate-700'}`}>
                      {analogSummary.prophet_change_pct > 0 ? '+' : ''}{analogSummary.prophet_change_pct}%
                    </p>
                  </div>

                  <div>
                    <p className="text-sm font-medium text-slate-500 uppercase text-xs mb-1">Relationship</p>
                    <div className="text-sm text-slate-700 font-medium">
                      {analogSummary.forecast_agreement.includes('AGREEMENT') 
                        ? "Historical analog and current forecast point in the same direction." 
                        : analogSummary.forecast_agreement === 'CONFLICT' 
                        ? "Historical evidence conflicts with the current forecast." 
                        : "No clear relationship between historical and current signals."}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Explanation Section */}
            <div className="p-6 bg-indigo-50 border-t border-indigo-100 flex items-start gap-4 text-indigo-900">
              <Info className="h-5 w-5 shrink-0 mt-0.5 text-indigo-500" />
              <div>
                <p className="font-semibold mb-1">SmartStock Synthesis</p>
                <p className="text-sm leading-relaxed">{analogSummary.historical_evidence}</p>
                {analogSummary.analog_confidence === 'LOW' && (
                  <p className="text-sm font-medium mt-2 text-rose-700 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" /> Analog confidence is low, so this signal should be treated cautiously.
                  </p>
                )}
              </div>
            </div>
          </div>

        </div>
      ) : (
        <EmptyState title="No Historical Analog Available" message={`Insufficient historical evidence for ${selectedProduct?.name}. Not enough data or no matching patterns found.`} icon={<ShieldQuestion className="mx-auto h-12 w-12 text-gray-300" />} />
      )}
    </div>
  );
}
