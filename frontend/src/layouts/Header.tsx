import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Menu, Search, Bell, X, ChevronRight,
  User, Settings, LogOut, AlertTriangle, ShoppingCart, Package
} from 'lucide-react';
import { MOCK_INVENTORY, MOCK_PRODUCTS } from '../data/mockData';

interface HeaderProps {
  onMenuClick: () => void;
}

// ─── Search ──────────────────────────────────────────────────────────────────
function SearchBox() {
  const [query, setQuery] = React.useState('');
  const [open, setOpen] = React.useState(false);
  const [focused, setFocused] = React.useState(false);
  const navigate = useNavigate();
  const ref = React.useRef<HTMLDivElement>(null);

  const results = React.useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return MOCK_PRODUCTS.filter(
      p =>
        p.name.toLowerCase().includes(q) ||
        p.product_id.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
    ).slice(0, 6);
  }, [query]);

  const inv = React.useMemo(() => {
    const map: Record<string, { status: string }> = {};
    MOCK_INVENTORY.forEach(i => { map[i.product_id] = { status: i.status }; });
    return map;
  }, []);

  function statusColor(status: string) {
    if (status === 'CRITICAL') return 'text-red-600 bg-red-50';
    if (status === 'WARNING') return 'text-amber-600 bg-amber-50';
    return 'text-emerald-600 bg-emerald-50';
  }

  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setFocused(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSelect(productId: string) {
    navigate(`/products/${productId}`);
    setQuery('');
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') { setOpen(false); setQuery(''); }
    if (e.key === 'Enter' && results.length > 0) handleSelect(results[0].product_id);
  }

  return (
    <div ref={ref} className="relative hidden sm:block">
      <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      <input
        id="global-search"
        type="search"
        value={query}
        placeholder="Search products..."
        autoComplete="off"
        className={`h-9 w-56 rounded-lg border pl-9 pr-4 text-sm transition-all focus:w-72 focus:outline-none
          ${focused
            ? 'border-indigo-400 ring-2 ring-indigo-100 bg-white'
            : 'border-gray-200 bg-gray-50 hover:bg-white hover:border-gray-300'
          }`}
        aria-label="Search products"
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => { setFocused(true); setOpen(true); }}
        onKeyDown={handleKeyDown}
      />
      {query && (
        <button
          onClick={() => { setQuery(''); setOpen(false); }}
          className="absolute right-2.5 top-2.5 text-gray-400 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
        </button>
      )}

      {open && results.length > 0 && (
        <div className="absolute top-11 left-0 w-80 rounded-xl border border-gray-200 bg-white shadow-xl z-50 overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-100 text-xs font-semibold text-gray-400 uppercase tracking-wide">
            Products ({results.length})
          </div>
          <ul>
            {results.map(p => {
              const ivStatus = inv[p.product_id]?.status ?? 'HEALTHY';
              return (
                <li key={p.product_id}>
                  <button
                    onClick={() => handleSelect(p.product_id)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 transition-colors text-left group"
                  >
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
                      <Package className="h-4 w-4 text-indigo-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-gray-900 truncate">{p.name}</div>
                      <div className="text-xs text-gray-400">{p.product_id} · {p.category}</div>
                    </div>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor(ivStatus)}`}>
                      {ivStatus}
                    </span>
                    <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-indigo-400 shrink-0" />
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="px-4 py-2 border-t border-gray-100 text-xs text-gray-400 flex items-center gap-1">
            Press <kbd className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 font-mono">↵</kbd> to open first result
          </div>
        </div>
      )}

      {open && query.trim() && results.length === 0 && (
        <div className="absolute top-11 left-0 w-72 rounded-xl border border-gray-200 bg-white shadow-xl z-50">
          <div className="px-4 py-6 text-center">
            <Package className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No products found for <strong>"{query}"</strong></p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Notifications ────────────────────────────────────────────────────────────
function NotificationPanel() {
  const [open, setOpen] = React.useState(false);
  const [dismissed, setDismissed] = React.useState<Set<string>>(new Set());
  const ref = React.useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const alerts = React.useMemo(() => {
    return MOCK_INVENTORY.filter(
      i => (i.status === 'CRITICAL' || i.status === 'WARNING') && !dismissed.has(i.product_id)
    ).map(i => ({
      id: i.product_id,
      name: i.name,
      status: i.status,
      message: i.status === 'CRITICAL'
        ? `Stockout in ${i.days_of_stock_left.toFixed(1)} days — order ${i.order_qty} units NOW`
        : `${i.days_of_stock_left.toFixed(1)} days of stock left — review soon`,
      time: 'Just now',
    }));
  }, [dismissed]);

  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function dismiss(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    setDismissed(prev => new Set([...prev, id]));
  }

  return (
    <div ref={ref} className="relative">
      <button
        id="notification-btn"
        onClick={() => setOpen(prev => !prev)}
        className={`relative rounded-full p-2 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-400
          ${open ? 'bg-indigo-50 text-indigo-600' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}
        aria-label="View notifications"
        aria-expanded={open}
      >
        <Bell className="h-5 w-5" />
        {alerts.length > 0 && (
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white ring-2 ring-white">
            {alerts.length > 9 ? '9+' : alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-96 rounded-2xl border border-gray-200 bg-white shadow-2xl z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div>
              <h3 className="text-sm font-bold text-gray-900">Notifications</h3>
              <p className="text-xs text-gray-400 mt-0.5">{alerts.length} active alert{alerts.length !== 1 ? 's' : ''}</p>
            </div>
            {alerts.length > 0 && (
              <button
                onClick={() => setDismissed(new Set(MOCK_INVENTORY.map(i => i.product_id)))}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Alert list */}
          <div className="max-h-80 overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="flex flex-col items-center py-10 text-center px-4">
                <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center mb-3">
                  <Bell className="h-6 w-6 text-emerald-500" />
                </div>
                <p className="text-sm font-medium text-gray-700">All clear!</p>
                <p className="text-xs text-gray-400 mt-1">No inventory alerts at the moment.</p>
              </div>
            ) : (
              alerts.map(alert => (
                <div
                  key={alert.id}
                  onClick={() => { navigate(`/products/${alert.id}`); setOpen(false); }}
                  className="flex items-start gap-3 px-5 py-4 hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0 transition-colors group"
                >
                  <div className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center mt-0.5
                    ${alert.status === 'CRITICAL' ? 'bg-red-100' : 'bg-amber-100'}`}>
                    <AlertTriangle className={`h-4 w-4 ${alert.status === 'CRITICAL' ? 'text-red-600' : 'text-amber-600'}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-semibold text-gray-900 truncate">{alert.name}</span>
                      <span className={`shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-full
                        ${alert.status === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                        {alert.status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 leading-relaxed">{alert.message}</p>
                    <p className="text-xs text-gray-300 mt-1">{alert.time}</p>
                  </div>
                  <button
                    onClick={(e) => dismiss(alert.id, e)}
                    className="shrink-0 p-1 rounded-full text-gray-300 hover:text-gray-500 hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Dismiss notification"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-gray-100 bg-gray-50">
            <button
              onClick={() => { navigate('/copilot'); setOpen(false); }}
              className="w-full flex items-center justify-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-800 py-1"
            >
              <ShoppingCart className="h-4 w-4" />
              Review all orders in AI Copilot
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Account Menu ─────────────────────────────────────────────────────────────
function AccountMenu() {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const menuItems = [
    { label: 'My Profile', icon: User, action: () => {} },
    { label: 'Settings', icon: Settings, action: () => navigate('/model-impact') },
  ];

  return (
    <div ref={ref} className="relative">
      <button
        id="account-menu-btn"
        onClick={() => setOpen(prev => !prev)}
        className={`flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-400
          ${open ? 'bg-indigo-50' : 'hover:bg-gray-100'}`}
        aria-label="Account menu"
        aria-expanded={open}
      >
        <div className="h-8 w-8 rounded-full bg-indigo-600 flex items-center justify-center">
          <span className="text-xs font-bold text-white">SS</span>
        </div>
        <div className="hidden md:block text-left">
          <div className="text-xs font-semibold text-gray-900 leading-tight">Store Manager</div>
          <div className="text-xs text-gray-400 leading-tight">admin@smartstock.io</div>
        </div>
      </button>

      {open && (
        <div className="absolute right-0 top-12 w-64 rounded-2xl border border-gray-200 bg-white shadow-2xl z-50 overflow-hidden">
          {/* Profile header */}
          <div className="px-5 py-4 bg-gradient-to-br from-indigo-50 to-purple-50 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-indigo-600 flex items-center justify-center">
                <span className="text-sm font-bold text-white">SS</span>
              </div>
              <div>
                <div className="text-sm font-bold text-gray-900">Store Manager</div>
                <div className="text-xs text-gray-500">admin@smartstock.io</div>
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-indigo-100 text-indigo-700">Admin</span>
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">Active</span>
            </div>
          </div>

          {/* Menu items */}
          <div className="py-2">
            {menuItems.map(item => (
              <button
                key={item.label}
                onClick={() => { item.action(); setOpen(false); }}
                className="w-full flex items-center gap-3 px-5 py-2.5 text-sm text-gray-700 hover:bg-gray-50 hover:text-indigo-600 transition-colors group"
              >
                <item.icon className="h-4 w-4 text-gray-400 group-hover:text-indigo-500" />
                {item.label}
              </button>
            ))}
          </div>

          <div className="border-t border-gray-100 py-2">
            <button
              onClick={() => {
                setOpen(false);
                alert('You have been signed out. Goodbye!');
              }}
              className="w-full flex items-center gap-3 px-5 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>

          <div className="px-5 py-3 border-t border-gray-100 bg-gray-50">
            <p className="text-xs text-gray-400">SmartStock v2.0 · AI Forecasting Module</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────
export function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm sm:px-6">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="rounded-md p-2 text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 lg:hidden"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="hidden sm:flex items-center gap-2 text-sm text-gray-400">
          <span className="font-semibold text-indigo-600">SmartStock</span>
          <span className="text-gray-300">/</span>
          <span className="font-medium text-gray-700">Dashboard</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <SearchBox />
        <NotificationPanel />
        <div className="w-px h-6 bg-gray-200" />
        <AccountMenu />
      </div>
    </header>
  );
}
