import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ProfileModal } from './ProfileModal';
import { useStore } from '../store/useStore';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { isSidebarCollapsed } = useStore();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  return (
    <div className="min-h-screen bg-canvas text-navy-850 flex">
      {/* 1. Left Navigation Rail (Persistent desktop + mobile drawer) */}
      <Sidebar
        isOpenMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
        onOpenProfile={() => setIsProfileModalOpen(true)}
      />

      {/* 2. Main Content Canvas */}
      <div
        className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${
          isSidebarCollapsed ? 'lg:pl-20' : 'lg:pl-64'
        }`}
      >
        {/* Top Application Bar */}
        <TopBar
          onToggleMobileMenu={() => setIsMobileMenuOpen(prev => !prev)}
          onOpenProfile={() => setIsProfileModalOpen(true)}
        />

        {/* Content Area with Top Padding for Fixed TopBar (82px) */}
        <main className="flex-1 pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>

      {/* 3. Patient Demographics Modal */}
      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
    </div>
  );
};
