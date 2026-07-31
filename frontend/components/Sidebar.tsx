'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();

  const navItems = [
    { name: 'Home', path: '/' },
    { name: 'Create', path: '/create' },
    { name: 'Runs', path: '/runs' },
    { name: 'Library', path: '/library' },
    { name: 'Calendar', path: '/calendar' },
    { name: 'Analytics', path: '/analytics' },
  ];

  const systemItems = [
    { name: 'Models', path: '/models' },
    { name: 'Team', path: '/team' },
    { name: 'Settings', path: '/settings' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="header-logo">P</div>
        <span className="header-title" style={{ fontSize: '18px' }}>PRODAGENTI</span>
        <span className="workspace-badge">Workspace Pro</span>
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-section">
          <span className="sidebar-section-title">Content operating system</span>
          <nav className="sidebar-links">
            {navItems.map((item) => (
              <Link 
                key={item.path} 
                href={item.path} 
                className={`sidebar-link ${pathname === item.path || pathname.startsWith(item.path + '/') ? 'active' : ''}`}
              >
                {item.name}
              </Link>
            ))}
          </nav>
        </div>

        <div className="sidebar-section">
          <span className="sidebar-section-title">SYSTEM</span>
          <nav className="sidebar-links">
            {systemItems.map((item) => (
              <Link 
                key={item.path} 
                href={item.path} 
                className={`sidebar-link ${pathname === item.path ? 'active' : ''}`}
              >
                {item.name}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="user-profile">
          <div className="user-avatar">EF</div>
          <div className="user-info">
            <span className="user-name">Eduardo Farid</span>
            <span className="user-plan">Creator plan</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
