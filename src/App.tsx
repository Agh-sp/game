import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { SecretsManager } from './components/SecretsManager';
import { UsersManager } from './components/UsersManager';
import { CountriesExplorer } from './components/CountriesExplorer';
import { Globe, Key, Users } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('countries');
  const [configuredSecrets, setConfiguredSecrets] = useState<any>(null);
  const [botStatus, setBotStatus] = useState<any>(null);
  const [botProcess, setBotProcess] = useState<{ isRunning: boolean; pid: number | null }>({ isRunning: false, pid: null });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchSecretsAndStatus = async () => {
    try {
      const res = await fetch('/api/secrets');
      const data = await res.json();
      setConfiguredSecrets(data.configured);
      setBotStatus(data.checks);
      if (data.process) {
        setBotProcess(data.process);
      }
    } catch (err) {
      console.error('Failed to load status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestartProcess = async () => {
    try {
      const res = await fetch('/api/bot-process/restart', { method: 'POST' });
      const data = await res.json();
      if (data.pid) {
        setBotProcess({ isRunning: true, pid: data.pid });
      }
      setTimeout(fetchSecretsAndStatus, 1500);
    } catch (err) {
      console.error('Failed to restart bot:', err);
    }
  };

  useEffect(() => {
    fetchSecretsAndStatus();
    // Poll every 20s to keep token status fresh
    const interval = setInterval(fetchSecretsAndStatus, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans" dir="rtl">
      {/* Navbar with live status */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        botStatus={botStatus}
        configuredSecrets={configuredSecrets}
        botProcess={botProcess}
        onRestartProcess={handleRestartProcess}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
        {isLoading ? (
          <div className="h-96 flex flex-col items-center justify-center gap-3">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-xs text-slate-400">در حال بارگذاری اطلاعات سکرت‌ها، پرچم‌های واقعی و پایگاه داده...</span>
          </div>
        ) : (
          <>
            {activeTab === 'countries' && <CountriesExplorer />}
            {activeTab === 'users' && <UsersManager />}
            {activeTab === 'secrets' && (
              <SecretsManager
                configuredSecrets={configuredSecrets}
                botStatus={botStatus}
                onRefresh={fetchSecretsAndStatus}
              />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 py-6 mt-12 text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-amber-400" />
            <span className="text-slate-300 font-semibold">سامانه کنترل و مدیریت بازی جنگ جهانی تلگرام</span>
            <span className="text-slate-600">|</span>
            <span>۴۵ کشور با پرچم‌های واقعی FlagCDN، پایگاه داده SQLite و همگام‌سازی زنده</span>
          </div>

          <div className="flex items-center gap-4 text-slate-400">
            <button
              onClick={() => setActiveTab('countries')}
              className={`hover:text-amber-400 transition-colors flex items-center gap-1 cursor-pointer ${
                activeTab === 'countries' ? 'text-amber-400 font-bold' : ''
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>اطلس و پرچم‌های کشورها</span>
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className={`hover:text-amber-400 transition-colors flex items-center gap-1 cursor-pointer ${
                activeTab === 'users' ? 'text-amber-400 font-bold' : ''
              }`}
            >
              <Users className="w-3.5 h-3.5" />
              <span>مدیریت بازیکنان</span>
            </button>
            <button
              onClick={() => setActiveTab('secrets')}
              className={`hover:text-amber-400 transition-colors flex items-center gap-1 cursor-pointer ${
                activeTab === 'secrets' ? 'text-amber-400 font-bold' : ''
              }`}
            >
              <Key className="w-3.5 h-3.5" />
              <span>سکرت‌ها و توکن‌ها</span>
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
