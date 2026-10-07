import * as React from 'react';
import { Link } from 'react-router-dom';
import { askCopilot } from '../services/api';
import type { CopilotResponse, TimelineItem } from '../services/api';
import type { InventoryResult } from '../types/contracts';
import { Bot, Send, User, ExternalLink, AlertTriangle } from 'lucide-react';
import { Card } from '../components/ui/Card';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  items?: InventoryResult[];
  timeline?: TimelineItem[];
  intent?: string;
  isError?: boolean;
};

export default function Copilot() {
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'assistant',
      text: "Hi! I'm your SmartStock AI Reorder Copilot. Ask me which items will run out of stock first, what to order today, or why a product needs attention.",
    }
  ]);
  const [inputValue, setInputValue] = React.useState("");
  const [isTyping, setIsTyping] = React.useState(false);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async (query: string) => {
    if (!query.trim() || isTyping) return;
    
    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', text: query.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInputValue("");
    setIsTyping(true);

    try {
      const history = messages
        .filter(m => m.id !== 'init' && !m.isError)
        .map(m => ({ role: m.role === 'user' ? 'user' : 'model', content: m.text }));
      const response: CopilotResponse = await askCopilot(query, history);
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: response.message,
        items: response.items,
        timeline: response.timeline,
        intent: response.intent,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: "I couldn't retrieve the SmartStock recommendation right now. Please try again.",
        isError: true,
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(inputValue);
  };

  const getRiskBadge = (status: string) => {
    switch (status) {
      case 'CRITICAL': return <span className="bg-rose-100 text-rose-800 text-xs font-bold px-2 py-1 rounded">ORDER NOW</span>;
      case 'WARNING': return <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-1 rounded">ORDER SOON</span>;
      case 'OVERSTOCKED': return <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded">OVERSTOCK</span>;
      case 'HEALTHY': return <span className="bg-emerald-100 text-emerald-800 text-xs font-bold px-2 py-1 rounded">OK</span>;
      default: return <span className="bg-gray-100 text-gray-800 text-xs font-bold px-2 py-1 rounded">UNKNOWN</span>;
    }
  };

  const renderTimeline = (timeline: TimelineItem[]) => {
    if (!timeline || timeline.length === 0) return null;
    return (
      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            Stockout Depletion Priority Order
          </span>
          <span className="text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
            Immediate Action Required
          </span>
        </div>
        <div className="space-y-2.5">
          {timeline.map((item) => {
            const isCritical = item.urgency === 'CRITICAL' || item.is_breached;
            return (
              <div
                key={item.product_id}
                className={`p-3.5 rounded-xl border transition-all ${
                  isCritical
                    ? 'bg-rose-50/70 border-rose-200 shadow-sm'
                    : 'bg-white border-gray-200 shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-black shrink-0 ${
                        isCritical ? 'bg-rose-600 text-white' : 'bg-gray-200 text-gray-800'
                      }`}
                    >
                      #{item.rank}
                    </span>
                    <div>
                      <h4 className="text-sm font-bold text-gray-900">{item.name}</h4>
                      <span className="text-xs text-gray-500 font-mono">{item.product_id}</span>
                    </div>
                  </div>
                  {isCritical ? (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200 shrink-0">
                      CRITICAL
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200 shrink-0">
                      ORDER SOON
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-2 mt-3 pt-2.5 border-t border-gray-100 text-xs">
                  <div>
                    <span className="text-gray-500 block text-[10px] uppercase font-semibold">Stock Cover</span>
                    <span
                      className={`font-black text-sm ${
                        item.days_left <= item.lead_time_days ? 'text-rose-600' : 'text-gray-900'
                      }`}
                    >
                      {item.days_left} days
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[10px] uppercase font-semibold">Supplier Lead Time</span>
                    <span className="font-semibold text-gray-800 text-sm">{item.lead_time_days} days</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[10px] uppercase font-semibold">Recommended Order</span>
                    <span className="font-black text-indigo-700 text-sm">
                      {item.order_qty.toLocaleString()} units
                    </span>
                  </div>
                </div>

                {item.is_breached && (
                  <div className="mt-2.5 text-xs font-medium text-rose-800 bg-rose-100/70 rounded-md px-2.5 py-1.5 flex items-center gap-1.5 border border-rose-200">
                    <span>⚠️</span>
                    <span>
                      Stock covers {item.days_left}d vs {item.lead_time_days}d supplier lead time! Order by{' '}
                      <strong className="underline">{item.order_by_date}</strong> to prevent shelf stockout.
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderItems = (items: InventoryResult[], intent: string) => {
    if (!items || items.length === 0) return null;

    if (intent === 'WHY_ORDER') {
      const item = items[0];
      return (
        <Card className="mt-3 border border-indigo-100 shadow-sm overflow-hidden bg-white">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-bold text-gray-900">{item.name}</h3>
            {getRiskBadge(item.status)}
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-bold text-gray-500 uppercase">Recommendation</p>
                <p className="text-sm font-bold text-gray-900 mt-1">
                  {item.status === 'OVERSTOCKED' ? 'Hold Orders' : 
                   item.status === 'HEALTHY' ? 'No Action' : 
                   `Order ${item.order_qty} units`}
                </p>
              </div>
              <div>
                <p className="text-xs font-bold text-gray-500 uppercase">Timing</p>
                <p className="text-sm font-bold text-gray-900 mt-1">
                  {item.status === 'HEALTHY' || item.status === 'OVERSTOCKED' ? 'N/A' : `Order by ${item.order_by_date}`}
                </p>
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-100 rounded p-3">
              <p className="text-xs font-bold text-blue-800 uppercase mb-1">Reason</p>
              <p className="text-sm text-blue-900">{item.reason}</p>
            </div>
            <Link to={`/products/${item.product_id}`} className="inline-flex items-center text-sm font-medium text-indigo-600 hover:text-indigo-800">
              View Product Detail <ExternalLink className="ml-1 h-3 w-3" />
            </Link>
          </div>
        </Card>
      );
    }

    return (
      <div className="mt-3 grid gap-3 grid-cols-1 sm:grid-cols-2">
        {items.map(item => (
          <Card key={item.product_id} className="p-4 border border-gray-200 bg-white hover:border-indigo-300 transition-colors">
            <div className="flex justify-between items-start mb-2">
              <div className="text-sm font-bold text-gray-900">{item.name}</div>
              {getRiskBadge(item.status)}
            </div>
            {item.order_qty > 0 && (
              <div className="text-sm text-gray-700 mb-1">
                Order: <span className="font-bold">{item.order_qty} units</span>
              </div>
            )}
            {item.order_by_date && item.order_qty > 0 && (
              <div className="text-sm text-gray-700 mb-2">
                By: <span className="font-medium text-rose-600">{item.order_by_date}</span>
              </div>
            )}
            {item.status === 'OVERSTOCKED' && (
              <div className="text-sm text-gray-700 mb-2">
                Cover: <span className="font-medium text-blue-600">{item.days_of_stock_left} days</span>
              </div>
            )}
            <div className="text-xs text-gray-500 line-clamp-2">{item.reason}</div>
          </Card>
        ))}
      </div>
    );
  };

  const renderCleanMessageText = (rawText: string) => {
    if (!rawText) return null;
    const lines = rawText.split('\n');
    return (
      <div className="space-y-1">
        {lines.map((line, lIdx) => {
          let cleaned = line.replace(/^#{1,6}\s*/, '');
          if (cleaned.trim().startsWith('- ') || cleaned.trim().startsWith('* ') || cleaned.trim().startsWith('• ')) {
            cleaned = cleaned.replace(/^\s*[-*•]\s+/, '• ');
          }

          if (cleaned.trim() === '') {
            return <div key={lIdx} className="h-2" />;
          }

          const parts = cleaned.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);

          return (
            <div key={lIdx} className="min-h-[1.25rem]">
              {parts.map((part, pIdx) => {
                if (part.startsWith('**') && part.endsWith('**')) {
                  return (
                    <strong key={pIdx} className="font-semibold text-gray-900">
                      {part.slice(2, -2)}
                    </strong>
                  );
                }
                if (part.startsWith('`') && part.endsWith('`')) {
                  return (
                    <span key={pIdx} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs font-mono font-medium text-gray-800">
                      {part.slice(1, -1)}
                    </span>
                  );
                }
                const textContent = part.replace(/\*/g, '');
                return <span key={pIdx}>{textContent}</span>;
              })}
            </div>
          );
        })}
      </div>
    );
  };

  const suggestions = [
    "Which items will run out of stock first?",
    "What should I order today?",
    "Why should I order Milk 1L?",
    "What markdown promotions should we run?"
  ];

  return (
    <div className="max-w-4xl mx-auto pb-8 h-[calc(100vh-8rem)] flex flex-col">
      <div className="mb-6 shrink-0">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <Bot className="h-8 w-8 text-indigo-600" />
          AI Reorder Copilot
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Your SmartStock inventory assistant
        </p>
      </div>

      <div className="flex flex-col flex-1 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden min-h-0">
        {/* Chat Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-50/50">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                  <Bot className="h-5 w-5 text-indigo-700" />
                </div>
              )}
              <div className={`max-w-[85%] ${msg.role === 'user' ? 'order-1' : 'order-2'}`}>
                <div 
                  className={`px-4 py-3 rounded-2xl text-sm shadow-sm leading-relaxed
                    ${msg.role === 'user' 
                      ? 'bg-indigo-600 text-white rounded-tr-sm whitespace-pre-line' 
                      : msg.isError
                        ? 'bg-rose-50 text-rose-800 border border-rose-200 rounded-tl-sm'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-tl-sm'
                    }
                  `}
                >
                  {msg.role === 'user' ? msg.text : renderCleanMessageText(msg.text)}
                </div>
                {msg.timeline && renderTimeline(msg.timeline)}
                {!msg.timeline && msg.items && renderItems(msg.items, msg.intent || '')}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center shrink-0 order-2">
                  <User className="h-5 w-5 text-gray-600" />
                </div>
              )}
            </div>
          ))}
          
          {isTyping && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                <Bot className="h-5 w-5 text-indigo-700" />
              </div>
              <div className="px-4 py-3 rounded-2xl text-sm shadow-sm bg-white text-gray-500 border border-gray-200 rounded-tl-sm flex items-center gap-2">
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                <span className="ml-1">SmartStock is analyzing...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input Area */}
        <div className="p-4 bg-white border-t border-gray-200 shrink-0">
          <div className="flex flex-wrap gap-2 mb-3">
            {suggestions.map((s, idx) => (
              <button 
                key={idx}
                onClick={() => handleSend(s)}
                disabled={isTyping}
                className="text-xs bg-gray-100 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 text-gray-600 border border-transparent px-3 py-1.5 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {s}
              </button>
            ))}
          </div>
          <form onSubmit={onSubmit} className="relative">
            <label htmlFor="chat-input" className="sr-only">Ask SmartStock anything</label>
            <input
              id="chat-input"
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isTyping}
              placeholder="Ask SmartStock anything..."
              className="w-full pl-4 pr-12 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isTyping}
              aria-label="Send message"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
