import * as React from 'react';
import { Link } from 'react-router-dom';
import { askCopilot } from '../services/api';
import type { CopilotResponse } from '../services/api';
import type { InventoryResult } from '../types/contracts';
import { Bot, Send, User, ExternalLink } from 'lucide-react';
import { Card } from '../components/ui/Card';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  items?: InventoryResult[];
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
                  className={`px-4 py-3 rounded-2xl text-sm shadow-sm whitespace-pre-wrap leading-relaxed
                    ${msg.role === 'user' 
                      ? 'bg-indigo-600 text-white rounded-tr-sm' 
                      : msg.isError
                        ? 'bg-rose-50 text-rose-800 border border-rose-200 rounded-tl-sm'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-tl-sm'
                    }
                  `}
                >
                  {msg.text}
                </div>
                {msg.items && renderItems(msg.items, msg.intent || '')}
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
