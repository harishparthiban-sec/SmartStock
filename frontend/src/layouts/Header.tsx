
import { Menu, Search, Bell } from 'lucide-react';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm sm:px-6">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="rounded-md p-2 text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary lg:hidden"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="hidden sm:flex items-center gap-2 text-sm text-gray-500">
          <span>SmartStock</span>
          <span>/</span>
          <span className="font-medium text-gray-900">Dashboard</span>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="relative hidden sm:block">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="search"
            placeholder="Search products..."
            className="h-9 rounded-md border border-gray-300 pl-9 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            aria-label="Search"
          />
        </div>
        <button className="relative rounded-full p-2 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary">
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-red-500"></span>
          <Bell className="h-5 w-5" />
          <span className="sr-only">View notifications</span>
        </button>
        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
          <span className="text-sm font-medium text-primary">AI</span>
        </div>
      </div>
    </header>
  );
}
