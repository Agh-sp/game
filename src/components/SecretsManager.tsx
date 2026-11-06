import React, { useState, useEffect } from 'react';
import {
  Key,
  Shield,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  RefreshCw,
  Send,
  Lock,
  Eye,
  EyeOff,
  Info,
  ExternalLink,
  Terminal,
  Download,
  Flame,
  Server,
  Zap,
  Globe,
  Power,
  Play,
  Square,
  Bot,
  Activity,
  MessageSquare
} from 'lucide-react';
import { SECRETS_EXPLANATION } from '../data/gameData';

interface SecretsManagerProps {
  configuredSecrets: any;
  botStatus: any;
  onRefresh: () => void;
}

export const SecretsManager: React.FC<SecretsManagerProps> = ({ configuredSecrets, botStatus, onRefresh }) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showTokens, setShowTokens] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);

  // Form states
  const [gameTokenInput, setGameTokenInput] = useState<string>(configuredSecrets?.rawGameToken || '');
  const [adminTokenInput, setAdminTokenInput] = useState<string>(configuredSecrets?.rawAdminToken || '');
  const [superAdminIdInput, setSuperAdminIdInput] = useState<string>(configuredSecrets?.SUPER_ADMIN_ID || '');
  const [firebaseUrlInput, setFirebaseUrlInput] = useState<string>(configuredSecrets?.FIREBASE_DB_URL || '');
  const [firebaseAuthInput, setFirebaseAuthInput] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<{ text: string; isError: boolean } | null>(null);

  // Standalone custom token test
  const [customToken, setCustomToken] = useState<string>('');
  const [customTestResult, setCustomTestResult] = useState<any>(null);
  const [isTestingCustom, setIsTestingCustom] = useState<boolean>(false);

  // Firebase Live Test state
  const [isTestingFirebase, setIsTestingFirebase] = useState<boolean>(false);
  const [firebaseTestResult, setFirebaseTestResult] = useState<any>(null);

  // Bot process & live console state
  const [botProcessState, setBotProcessState] = useState<{ isRunning: boolean; pid: number | null }>({ isRunning: false, pid: null });
  const [botLogs, setBotLogs] = useState<string[]>([]);
  const [isProcessAction, setIsProcessAction] = useState<boolean>(false);

  const gameBotUsername = botStatus?.gameBot?.result?.username || 'TetrisBEQRQEBot';
  const adminBotUsername = botStatus?.adminBot?.result?.username || 'Tetr23343isBot';

  const fetchBotLogsAndProcess = async () => {
    try {
      const [statusRes, logsRes] = await Promise.all([
        fetch('/api/bot-process/status'),
        fetch('/api/bot-process/logs')
      ]);
      const statusData = await statusRes.json();
      const logsData = await logsRes.json();
      if (statusData) setBotProcessState(statusData);
      if (logsData && Array.isArray(logsData.logs)) setBotLogs(logsData.logs);
    } catch (_) {}
  };

  useEffect(() => {
    fetchBotLogsAndProcess();
    const timer = setInterval(fetchBotLogsAndProcess, 4000);
    return () => clearInterval(timer);
  }, []);

  const handleProcessAction = async (action: 'restart' | 'start' | 'stop') => {
    setIsProcessAction(true);
    try {
      await fetch(`/api/bot-process/${action}`, { method: 'POST' });
      await new Promise(r => setTimeout(r, 800));
      await fetchBotLogsAndProcess();
      onRefresh();
    } catch (err) {
      console.error('Process action error:', err);
    } finally {
      setIsProcessAction(false);
    }
  };

  const handleCopy = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  const handleSaveSecrets = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveMessage(null);
    try {
      const res = await fetch('/api/secrets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          GAME_BOT_TOKEN: gameTokenInput,
          ADMIN_BOT_TOKEN: adminTokenInput,
          SUPER_ADMIN_ID: superAdminIdInput,
          FIREBASE_DB_URL: firebaseUrlInput,
          FIREBASE_AUTH: firebaseAuthInput,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setSaveMessage({ text: 'سکرت‌ها و توکن‌ها با موفقیت در .env ذخیره و اعمال شدند!', isError: false });
        setIsEditing(false);
        onRefresh();
        // restart bots to take new env
        await handleProcessAction('restart');
      } else {
        setSaveMessage({ text: data.error || 'خطا در ذخیره‌سازی سکرت‌ها', isError: true });
      }
    } catch (err: any) {
      setSaveMessage({ text: err.message || 'خطا در ارتباط با سرور', isError: true });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestCustomToken = async () => {
    if (!customToken) return;
    setIsTestingCustom(true);
    setCustomTestResult(null);
    try {
      const res = await fetch('/api/test-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: customToken }),
      });
      const data = await res.json();
      setCustomTestResult(data);
    } catch (err: any) {
      setCustomTestResult({ ok: false, error: err.message });
    } finally {
      setIsTestingCustom(false);
    }
  };

  const handleTestFirebase = async () => {
    setIsTestingFirebase(true);
    setFirebaseTestResult(null);
    try {
      const res = await fetch('/api/test-firebase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firebaseUrl: firebaseUrlInput || configuredSecrets?.FIREBASE_DB_URL,
          firebaseAuth: firebaseAuthInput || configuredSecrets?.FIREBASE_AUTH,
        }),
      });
      const data = await res.json();
      setFirebaseTestResult(data);
    } catch (err: any) {
      setFirebaseTestResult({ ok: false, error: err.message });
    } finally {
      setIsTestingFirebase(false);
    }
  };

  const envFileSnippet = `# ─── تنظیمات بازی جنگ جهانی ───
# توکن ربات اصلی بازی (از @BotFather)
GAME_BOT_TOKEN=${configuredSecrets?.rawGameToken || '9201202722:AAGuSaJQw16F_ugrKXUidttYfMqI9Cz3SVE'}

# توکن ربات ادمین (ربات جداگانه از @BotFather)
ADMIN_BOT_TOKEN=${configuredSecrets?.rawAdminToken || '9000162449:AAG-xoIDUSgE1LFWr1L3BOZjygueYuCZOfU'}

# آیدی عددی ادمین اصلی (سوپرادمین) — برای گرفتن آیدی خود به @userinfobot پیام بدهید
SUPER_ADMIN_ID=${configuredSecrets?.SUPER_ADMIN_ID || '8666501866'}

# مسیر دیتابیس (پیش‌فرض wwgame.db)
DB_PATH=wwgame.db

# اتصال فایربیس (اختیاری جهت همگام‌سازی ابری زنده)
FIREBASE_DB_URL=${configuredSecrets?.FIREBASE_DB_URL || 'https://wofgame-b2188-default-rtdb.firebaseio.com'}
FIREBASE_AUTH=${configuredSecrets?.FIREBASE_AUTH || 'F4vmRrXnlHHU7K5LGfl0Ylwx1iavXJwhrykmN5Iy'}`;

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* ─── LIVE TELEGRAM BOTS STATUS & DIRECT LINKS ─── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/50 to-slate-900 border border-emerald-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
              ربات‌ها متصل و فعال هستند (Telegram Polling Active)
            </div>
            <h2 className="text-2xl font-black text-white tracking-wide">
              اتصال زنده به هر دو ربات تلگرام برقرار شد
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed max-w-3xl">
              کتابخانه‌های پایتونی تلگرام (Aiogram 3) با موفقیت روی سرور نصب و راه‌اندازی شدند. 
              فرآیند اجرای ربات‌ها با <strong className="text-emerald-400 font-mono">PID {botProcessState.pid || 'فعال'}</strong> در حال دریافت پیام‌های بازیکنان و پردازش رویدادها است.
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => handleProcessAction('restart')}
              disabled={isProcessAction}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition-all cursor-pointer shadow-md"
              title="راه‌اندازی مجدد سرویس ربات‌ها"
            >
              <RefreshCw className={`w-4 h-4 text-amber-400 ${isProcessAction ? 'animate-spin' : ''}`} />
              <span>ری‌استارت ربات‌ها</span>
            </button>

            <button
              onClick={() => setIsEditing(!isEditing)}
              className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/20 cursor-pointer"
            >
              <Key className="w-4 h-4" />
              <span>ویرایش سکرت‌ها و توکن‌ها</span>
            </button>
          </div>
        </div>

        {/* Big Telegram Open Buttons */}
        <div className="mt-6 pt-6 border-t border-slate-800 grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href={`https://t.me/${gameBotUsername}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-blue-600/20 to-emerald-600/20 border border-emerald-500/40 hover:border-emerald-400 hover:bg-emerald-600/30 transition-all group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center text-blue-400 group-hover:scale-105 transition-transform">
                <Bot className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block">ربات اصلی بازی بازیکنان</span>
                <span className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5 font-mono">
                  @{gameBotUsername}
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-sans">آنلاین</span>
                </span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 group-hover:text-emerald-300">
              <span>ورود به ربات و ارسال /start</span>
              <ExternalLink className="w-4 h-4" />
            </div>
          </a>

          <a
            href={`https://t.me/${adminBotUsername}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border border-indigo-500/40 hover:border-indigo-400 hover:bg-indigo-600/30 transition-all group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
                <Shield className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block">ربات پنل مدیریت ادمین</span>
                <span className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5 font-mono">
                  @{adminBotUsername}
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-sans">آنلاین</span>
                </span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-400 group-hover:text-indigo-300">
              <span>ورود به پنل ادمین</span>
              <ExternalLink className="w-4 h-4" />
            </div>
          </a>
        </div>
      </div>

      {/* ─── LIVE TELEGRAM LOGS CONSOLE ─── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white">کنسول زنده لاگ‌های تلگرام (Live Server Output)</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
              PID: {botProcessState.pid || '—'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleCopy(botLogs.join('\n'), 'bot-logs')}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs flex items-center gap-1 cursor-pointer"
              title="کپی لاگ‌ها"
            >
              {copiedKey === 'bot-logs' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>کپی لاگ</span>
            </button>
            <button
              onClick={fetchBotLogsAndProcess}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs flex items-center gap-1 cursor-pointer"
              title="تازه‌سازی لاگ"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 max-h-64 overflow-y-auto font-mono text-[11px] text-emerald-300 space-y-1 select-all" dir="ltr">
          {botLogs.length > 0 ? (
            botLogs.map((line, idx) => (
              <div
                key={idx}
                className={`leading-relaxed ${
                  line.includes('ERROR')
                    ? 'text-rose-400 font-bold'
                    : line.includes('ربات') || line.includes('Start polling') || line.includes('Run polling')
                    ? 'text-amber-300 font-semibold'
                    : line.includes('Update')
                    ? 'text-cyan-300'
                    : 'text-slate-300'
                }`}
              >
                {line}
              </div>
            ))
          ) : (
            <div className="text-slate-500">درحال دریافت لاگ‌های ربات...</div>
          )}
        </div>
      </div>

      {/* Edit Form Modal/Drawer if opened */}
      {isEditing && (
        <form onSubmit={handleSaveSecrets} className="bg-slate-900 border border-amber-500/40 rounded-2xl p-6 shadow-2xl space-y-5 animate-slideDown">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <Key className="w-5 h-5 text-amber-400" />
              <h3 className="text-base font-bold text-white">ویرایش سکرت‌ها و ذخیره در فایل .env</h3>
            </div>
            <span className="text-xs text-slate-400">تغییرات بلافاصله در فایل worldwar-game/.env اعمال خواهد شد</span>
          </div>

          {saveMessage && (
            <div className={`p-3 rounded-xl text-xs font-medium flex items-center gap-2 ${saveMessage.isError ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'}`}>
              <Info className="w-4 h-4 shrink-0" />
              <span>{saveMessage.text}</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                ۱. توکن ربات بازی اصلی (GAME_BOT_TOKEN) <span className="text-rose-400">*الزامی</span>
              </label>
              <input
                type="text"
                dir="ltr"
                value={gameTokenInput}
                onChange={(e) => setGameTokenInput(e.target.value)}
                placeholder="123456789:ABCDEF..."
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">از ربات @BotFather در تلگرام با دستور /newbot</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                ۲. توکن ربات ادمین (ADMIN_BOT_TOKEN) <span className="text-rose-400">*الزامی</span>
              </label>
              <input
                type="text"
                dir="ltr"
                value={adminTokenInput}
                onChange={(e) => setAdminTokenInput(e.target.value)}
                placeholder="123456789:ABCDEF..."
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">ربات دوم و مستقل از @BotFather مخصوص پنل ادمین</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                ۳. آیدی عددی سوپرادمین (SUPER_ADMIN_ID) <span className="text-rose-400">*الزامی</span>
              </label>
              <input
                type="text"
                dir="ltr"
                value={superAdminIdInput}
                onChange={(e) => setSuperAdminIdInput(e.target.value)}
                placeholder="8666501866"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">از ربات @userinfobot برای پیدا کردن آیدی خود استفاده کنید</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                ۴. آدرس فایربیس (FIREBASE_DB_URL) <span className="text-blue-400">اختیاری</span>
              </label>
              <input
                type="text"
                dir="ltr"
                value={firebaseUrlInput}
                onChange={(e) => setFirebaseUrlInput(e.target.value)}
                placeholder="https://YOUR-PROJECT-default-rtdb.firebaseio.com"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">آدرس پایگاه داده Realtime Database</span>
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                ۵. رمز/سکرت فایربیس (FIREBASE_AUTH) <span className="text-blue-400">اختیاری</span>
              </label>
              <input
                type="password"
                dir="ltr"
                value={firebaseAuthInput}
                onChange={(e) => setFirebaseAuthInput(e.target.value)}
                placeholder="Database Secret یا توکن احراز هویت"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">از منوی Project Settings &gt; Service Accounts &gt; Database Secrets در فایربیس</span>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20 cursor-pointer disabled:opacity-50"
            >
              {isSaving ? 'در حال ذخیره‌سازی...' : 'ذخیره در .env'}
            </button>
          </div>
        </form>
      )}

      {/* ─── LIVE FIREBASE CONNECTION TESTER ─── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Flame className="w-5 h-5 text-amber-500" />
              تست زنده اتصال به پایگاه داده Firebase Realtime Database
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              آدرس پایگاه داده: <span className="text-slate-200 font-mono" dir="ltr">{configuredSecrets?.FIREBASE_DB_URL || 'تنظیم نشده'}</span>
            </p>
          </div>

          <button
            onClick={handleTestFirebase}
            disabled={isTestingFirebase}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md shadow-amber-500/20 disabled:opacity-50"
          >
            {isTestingFirebase ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                در حال بررسی ارتباط...
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5" />
                تست زنده اتصال فایربیس
              </>
            )}
          </button>
        </div>

        {firebaseTestResult && (
          <div
            className={`p-4 rounded-xl text-xs space-y-2 border animate-fadeIn ${
              firebaseTestResult.ok
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-950/30 border-rose-500/30 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-sm">
              {firebaseTestResult.ok ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  اتصال به Firebase Realtime Database با موفقیت تایید شد!
                </>
              ) : (
                <>
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  خطا در اتصال به فایربیس:
                </>
              )}
            </div>

            {firebaseTestResult.ok ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-2 font-mono text-xs">
                <div className="bg-slate-950/80 p-2.5 rounded-lg border border-emerald-500/20">
                  <span className="text-slate-400 text-[10px] block">کد پاسخ:</span>
                  <span className="font-bold text-emerald-400">HTTP {firebaseTestResult.statusCode} OK</span>
                </div>
                <div className="bg-slate-950/80 p-2.5 rounded-lg border border-emerald-500/20">
                  <span className="text-slate-400 text-[10px] block">سرعت پینگ (Latency):</span>
                  <span className="font-bold text-white">{firebaseTestResult.latencyMs} ms</span>
                </div>
                <div className="bg-slate-950/80 p-2.5 rounded-lg border border-emerald-500/20">
                  <span className="text-slate-400 text-[10px] block">وضعیت دیتابیس:</span>
                  <span className="font-bold text-emerald-400">آنلاین و قابل خواندن</span>
                </div>
              </div>
            ) : (
              <p className="text-rose-200 mt-1">{firebaseTestResult.error}</p>
            )}
          </div>
        )}
      </div>

      {/* Breakdown Cards for Each Secret */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Key className="w-4 h-4 text-amber-400" />
            جداول تشریحی سکرت‌های مورد نیاز بازی جنگ جهانی
          </h3>
          <button
            onClick={() => setShowTokens(!showTokens)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded bg-slate-800 border border-slate-700 cursor-pointer"
          >
            {showTokens ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{showTokens ? 'مخفی‌سازی توکن‌ها' : 'نمایش کامل مقادیر محرمانه'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {SECRETS_EXPLANATION.map((item) => {
            const isConfigured = Boolean(
              item.key === 'GAME_BOT_TOKEN'
                ? configuredSecrets?.rawGameToken
                : item.key === 'ADMIN_BOT_TOKEN'
                ? configuredSecrets?.rawAdminToken
                : item.key === 'SUPER_ADMIN_ID'
                ? configuredSecrets?.SUPER_ADMIN_ID
                : item.key === 'FIREBASE_DB_URL'
                ? configuredSecrets?.FIREBASE_DB_URL
                : true
            );

            const displayVal =
              item.key === 'GAME_BOT_TOKEN'
                ? showTokens
                  ? configuredSecrets?.rawGameToken || item.example
                  : configuredSecrets?.GAME_BOT_TOKEN || 'تنظیم نشده'
                : item.key === 'ADMIN_BOT_TOKEN'
                ? showTokens
                  ? configuredSecrets?.rawAdminToken || item.example
                  : configuredSecrets?.ADMIN_BOT_TOKEN || 'تنظیم نشده'
                : item.key === 'SUPER_ADMIN_ID'
                ? configuredSecrets?.SUPER_ADMIN_ID || item.example
                : item.key === 'FIREBASE_DB_URL'
                ? configuredSecrets?.FIREBASE_DB_URL || '(تنظیم نشده — استفاده از ذخیره محلی)'
                : item.example;

            return (
              <div
                key={item.key}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-all space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                      <Key className="w-4 h-4" />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-amber-300">{item.key}</span>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                            item.type.includes('Required')
                              ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                              : 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
                          }`}
                        >
                          {item.type}
                        </span>
                      </div>
                      <span className="text-xs text-slate-400">{item.title}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {isConfigured ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        ثبت و فعال
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/20">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        نیاز به ثبت
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="space-y-1.5">
                    <span className="text-slate-400 font-semibold flex items-center gap-1">
                      <Info className="w-3.5 h-3.5 text-slate-500" />
                      کاربرد و نقش این سکرت در بازی:
                    </span>
                    <p className="text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
                      {item.purpose}
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <span className="text-slate-400 font-semibold flex items-center gap-1">
                      <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
                      نحوه استخراج و دریافت این متغیر:
                    </span>
                    <p className="text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
                      {item.howToGet}
                    </p>
                  </div>
                </div>

                {/* Current Value / Copy Box */}
                <div className="bg-slate-950 rounded-xl p-3 border border-slate-800 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Lock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span className="text-slate-400 text-xs shrink-0">مقدار فعلی:</span>
                    <span className="font-mono text-xs text-slate-200 truncate select-all" dir="ltr">
                      {displayVal}
                    </span>
                  </div>

                  <button
                    onClick={() =>
                      handleCopy(
                        item.key === 'GAME_BOT_TOKEN'
                          ? configuredSecrets?.rawGameToken || item.example
                          : item.key === 'ADMIN_BOT_TOKEN'
                          ? configuredSecrets?.rawAdminToken || item.example
                          : item.key === 'SUPER_ADMIN_ID'
                          ? configuredSecrets?.SUPER_ADMIN_ID || item.example
                          : item.example,
                        item.key
                      )
                    }
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all shrink-0 cursor-pointer"
                    title="کپی در حافظه"
                  >
                    {copiedKey === item.key ? (
                      <Check className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Complete .env Raw Snippet */}
      <div className="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            <span className="text-xs font-mono font-bold text-slate-300">محتوای کامل فایل .env پروژه (Ready to Copy)</span>
          </div>
          <button
            onClick={() => handleCopy(envFileSnippet, 'full-env')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition-all cursor-pointer"
          >
            {copiedKey === 'full-env' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>کپی کل فایل .env</span>
          </button>
        </div>

        <pre className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-amber-200/90 font-mono overflow-x-auto select-all leading-relaxed" dir="ltr">
          {envFileSnippet}
        </pre>
      </div>
    </div>
  );
};
