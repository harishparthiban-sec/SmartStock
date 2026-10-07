
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PackageSearch, Split, Activity, PackagePlus, History, Bot } from 'lucide-react';
import { cn } from '../utils/cn';

interface SidebarProps {
  className?: string;
  onNavClick?: () => void;
}

export function Sidebar({ className, onNavClick }: SidebarProps) {
  const navItems = [
    { to: "/", label: "Overview", icon: LayoutDashboard, exact: true },
    { to: "/copilot", label: "AI Copilot", icon: Bot },
    { to: "/products/P001", label: "Product Detail", icon: PackageSearch },
    { to: "/what-if", label: "What-If", icon: Split },
    { to: "/overstock", label: "Overstock", icon: PackagePlus },
    { to: "/time-machine", label: "Time Machine", icon: History },
    { to: "/model-impact", label: "Model & Impact", icon: Activity },
  ];

  return (
    <aside className={cn("flex flex-col bg-gray-900 text-gray-300", className)}>
      <div className="flex h-16 items-center px-6 border-b border-gray-800">
        <span className="text-lg font-bold text-white flex items-center gap-2">
          <Activity className="h-5 w-5 text-emerald-400" />
          SmartStock
        </span>
      </div>
      <nav className="flex-1 py-6 px-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            onClick={onNavClick}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive 
                  ? "bg-gray-800 text-white" 
                  : "hover:bg-gray-800/50 hover:text-white"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-800 text-xs text-gray-500">
        AI Forecasting Module
      </div>
    </aside>
  );
}
