import React, { useState } from 'react';
import { Shield, Key, Globe, CheckCircle2, AlertCircle, Users, Power, RefreshCw, ExternalLink } from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  botStatus: {
    gameBot: any;
    adminBot: any;
  } | null;
  configuredSecrets: any;
  botProcess?: {
    isRunning: boolean;
    pid: number | null;
  };
  onRestartProcess?: () => Promise<void>;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  botStatus,
  configuredSecrets,
  botProcess,
  onRestartProcess,
}) => {
  const [isRestarting, setIsRestarting] = useState<boolean>(false);
  const gameBotUsername = botStatus?.gameBot?.result?.username || 'TetrisBEQRQEBot';
  const adminBotUsername = botStatus?.adminBot?.result?.username || 'Tetr23343isBot';
  const gameBotOk = botStatus?.gameBot?.ok;
  const adminBotOk = botStatus?.adminBot?.ok;

  const tabs = [
    { id: 'countries', label: 'اطلس و پرچم‌های کشورها', icon: Globe, badge: '۴۵ پرچم واقعی' },
    { id: 'users', label: 'مدیریت کاربران و بازیکنان', icon: Users, badge: 'زنده' },
    { id: 'secrets', label: 'سکرت‌ها و اتصال ربات‌ها', icon: Key, badge: 'آنلاین' },
  ];

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      {/* Top Banner / Info bar */}
      <div className="bg-slate-950 px-4 py-2 border-b border-slate-800/80 text-xs">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-slate-300">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-amber-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              پنل مدیریت و اتصال زنده بازی جنگ جهانی
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400 hidden sm:inline">اتصال زنده به تلگرام، SQLite و Firebase Realtime Database</span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 text-xs">
            {/* Game Bot live indicator with direct Telegram link */}
            <div className="flex items-center gap-1.5 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
              <span className="text-slate-400">ربات بازی:</span>
              {gameBotOk ? (
                <a
                  href={`https://t.me/${gameBotUsername}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-mono font-medium hover:underline"
                  title="باز کردن در تلگرام"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  @{gameBotUsername}
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              ) : (
                <span className="flex items-center gap-1 text-amber-400 font-mono">
                  <AlertCircle className="w-3.5 h-3.5" />
                  بررسی توکن...
                </span>
              )}
            </div>

            {/* Admin Bot live indicator with direct Telegram link */}
            <div className="flex items-center gap-1.5 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
              <span className="text-slate-400">ربات ادمین:</span>
              {adminBotOk ? (
                <a
                  href={`https://t.me/${adminBotUsername}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-mono font-medium hover:underline"
                  title="باز کردن در تلگرام"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  @{adminBotUsername}
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              ) : (
                <span className="flex items-center gap-1 text-amber-400 font-mono">
                  <AlertCircle className="w-3.5 h-3.5" />
                  بررسی توکن...
                </span>
              )}
            </div>

            {/* Bot Server Process Status */}
            <div className="flex items-center gap-1.5 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
              <span className="text-slate-400">سرور ربات:</span>
              {botProcess?.isRunning ? (
                <span className="flex items-center gap-1 text-emerald-400 font-medium font-mono text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  آنلاین (PID: {botProcess.pid})
                </span>
              ) : (
                <span className="flex items-center gap-1 text-rose-400 font-medium font-mono text-[11px]">
                  <Power className="w-3 h-3 text-rose-400" />
                  متوقف
                </span>
              )}
              {onRestartProcess && (
                <button
                  onClick={async () => {
                    setIsRestarting(true);
                    await onRestartProcess();
                    setIsRestarting(false);
                  }}
                  disabled={isRestarting}
                  className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-all cursor-pointer mr-0.5"
                  title="ری‌استارت پروسس ربات‌ها"
                >
                  <RefreshCw className={`w-3 h-3 ${isRestarting ? 'animate-spin text-amber-400' : ''}`} />
                </button>
              )}
            </div>

            {/* Super Admin ID */}
            <div className="hidden lg:flex items-center gap-1 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800 text-slate-300">
              <Shield className="w-3.5 h-3.5 text-blue-400" />
              <span>سوپرادمین:</span>
              <span className="font-mono text-blue-300">{configuredSecrets?.SUPER_ADMIN_ID || '8358901937'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Navigation Bar */}
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-600 via-rose-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-950/40">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                مرکز مدیریت و مانیتورینگ بازی جنگ جهانی
                <span className="text-[11px] font-normal px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  متصل به ربات‌ها ✅
                </span>
              </h1>
              <p className="text-xs text-slate-400">World War Telegram Game — Secrets & Player Accounts Center</p>
            </div>
          </div>

          {/* Navigation Tabs - Focused strictly on Users & Secrets */}
          <nav className="flex items-center gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    isActive
                      ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-lg shadow-amber-500/20'
                      : 'text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-slate-950' : 'text-slate-400'}`} />
                  <span>{tab.label}</span>
                  {tab.badge && (
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                        isActive ? 'bg-slate-950/20 text-slate-950' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      }`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
};
