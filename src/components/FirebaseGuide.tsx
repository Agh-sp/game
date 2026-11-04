import React, { useState } from 'react';
import { Flame, CheckCircle2, AlertTriangle, Copy, Check, ExternalLink, ShieldAlert, Zap, RefreshCw, Lock, Terminal, Info, Database } from 'lucide-react';

interface FirebaseGuideProps {
  configuredSecrets: any;
  onRefresh: () => void;
}

export const FirebaseGuide: React.FC<FirebaseGuideProps> = ({ configuredSecrets, onRefresh }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Live test states
  const [testUrl, setTestUrl] = useState<string>(configuredSecrets?.FIREBASE_DB_URL || '');
  const [testAuth, setTestAuth] = useState<string>('');
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<any>(null);

  // Save state
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleTestConnection = async () => {
    if (!testUrl) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch('/api/test-firebase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firebaseUrl: testUrl,
          firebaseAuth: testAuth,
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err: any) {
      setTestResult({ ok: false, error: err.message || 'خطا در شبکه' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveToEnv = async () => {
    if (!testUrl) return;
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const res = await fetch('/api/secrets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          FIREBASE_DB_URL: testUrl,
          FIREBASE_AUTH: testAuth,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setSaveSuccess(true);
        onRefresh();
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const recommendedRules = `{
  "rules": {
    "status": {
      ".read": true,
      ".write": true
    },
    "game": {
      ".read": true,
      ".write": true
    }
  }
}`;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Hero Banner */}
      <div className="bg-gradient-to-r from-orange-950/40 via-slate-900 to-amber-950/30 border border-amber-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-semibold">
              <Flame className="w-4 h-4 text-amber-400" />
              راهنمای گام‌به‌گام اتصال به دیتابیس ابری فایربیس (Firebase Realtime Database)
            </div>
            <h2 className="text-2xl font-black text-white">
              چگونه بازی را در ۵ دقیقه به سرور فایربیس وصل کنیم؟
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed max-w-3xl">
              اتصال فایربیس در این بازی برای <strong className="text-amber-400">پشتیبان‌گیری ابری زنده (Cloud Backup)</strong>، هارت‌بیت سرور، 
              و ارسال اسنپ‌شات دوره‌ای جدول‌ها استفاده می‌شود. توجه داشته باشید این سیستم از <strong>Firebase Realtime Database (RTDB)</strong> با 
              پروتکل سبک REST بهره می‌برد و نیازی به SDK پیچیده ندارد.
            </p>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs shrink-0 space-y-1.5">
            <span className="text-slate-400 block">وضعیت فعلی اتصال:</span>
            <div className="flex items-center gap-2">
              {configuredSecrets?.FIREBASE_DB_URL ? (
                <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  آدرس فایربیس ثبت شده
                </span>
              ) : (
                <span className="text-amber-400 font-bold flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
                  حالت محلی (ذخیره روی فایل fb_local.json)
                </span>
              )}
            </div>
            <span className="text-[10px] text-slate-500 block">بازی حتی بدون فایربیس هم ۱۰۰٪ سالم کار می‌کند</span>
          </div>
        </div>
      </div>

      {/* Step-by-Step Action Guide */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          مراحل اتصال به ترتیب (از ساخت تا فعال‌سازی)
        </h3>

        <div className="grid grid-cols-1 gap-4">
          {/* Step 1 */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-xl bg-amber-500/10 text-amber-400 font-bold text-xs flex items-center justify-center border border-amber-500/20">
                  ۱
                </span>
                <h4 className="font-bold text-sm text-white">ورود به کنسول فایربیس و ایجاد پروژه رایگان</h4>
              </div>
              <a
                href="https://console.firebase.google.com"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 bg-amber-500/10 px-3 py-1.5 rounded-lg border border-amber-500/20"
              >
                <span>باز کردن Firebase Console</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pr-9">
              به <strong className="text-white">console.firebase.google.com</strong> بروید، با جیمیل خود وارد شوید و دکمه <strong className="text-amber-300">Add project</strong> یا ساخت پروژه را بزنید. 
              یک نام دلخواه (مثلاً <code className="text-amber-400 font-mono">worldwar-game</code>) بنویسید و پروژه را ایجاد نمایید (Google Analytics اختیاری است).
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2.5">
              <span className="w-7 h-7 rounded-xl bg-amber-500/10 text-amber-400 font-bold text-xs flex items-center justify-center border border-amber-500/20">
                ۲
              </span>
              <h4 className="font-bold text-sm text-white">
                فعال‌سازی Realtime Database <span className="text-rose-400 text-xs font-normal">(نکته مهم: نه Firestore!)</span>
              </h4>
            </div>
            <div className="pr-9 space-y-2 text-xs text-slate-300 leading-relaxed">
              <p>
                در منوی سمت چپ پنل فایربیس، زیر بخش <strong>Build</strong> روی گزینه <strong className="text-amber-400">Realtime Database</strong> کلیک کنید (دقت کنید با Cloud Firestore اشتباه نگیرید).
              </p>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-slate-400">
                روی دکمه <strong>Create Database</strong> بزنید، ریجن مورد نظر (مثلاً <code className="text-white">United States</code> یا <code className="text-white">Belgium</code>) را تایید کرده و در مرحله قوانین امنیتی، گزینه <strong className="text-emerald-300">Start in test mode</strong> را انتخاب نمایید.
              </div>
            </div>
          </div>

          {/* Step 3 */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-xl bg-amber-500/10 text-amber-400 font-bold text-xs flex items-center justify-center border border-amber-500/20">
                  ۳
                </span>
                <h4 className="font-bold text-sm text-white">برداشتن آدرس دیتابیس (FIREBASE_DB_URL)</h4>
              </div>
            </div>
            <div className="pr-9 space-y-2 text-xs text-slate-300 leading-relaxed">
              <p>
                پس از ساخت، در بالای تب <strong>Data</strong>، یک لینک آدرس مشاهده می‌کنید که با <code className="text-amber-400 font-mono">https://</code> شروع شده و با <code className="text-amber-400 font-mono">firebaseio.com</code> پایان می‌یابد.
              </p>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between gap-3">
                <div className="font-mono text-amber-300 text-xs" dir="ltr">
                  https://your-project-id-default-rtdb.firebaseio.com
                </div>
                <span className="text-[10px] text-slate-500 shrink-0">نمونه فرمت آدرس</span>
              </div>
            </div>
          </div>

          {/* Step 4 */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2.5">
              <span className="w-7 h-7 rounded-xl bg-amber-500/10 text-amber-400 font-bold text-xs flex items-center justify-center border border-amber-500/20">
                ۴
              </span>
              <h4 className="font-bold text-sm text-white">مجوز دسترسی و سکرت (FIREBASE_AUTH)</h4>
            </div>
            <div className="pr-9 space-y-3 text-xs text-slate-300 leading-relaxed">
              <p>
                برای احراز هویت درخواست‌های ربات، یکی از دو روش زیر را انتخاب کنید:
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-1.5">
                  <span className="font-bold text-amber-300 block">روش اول: Database Secret (پیشنهادی و امن)</span>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    به بخش تنظیمات پروژه ⚙️ Project Settings ← سربرگ <strong>Service accounts</strong> ← زیربخش <strong>Database secrets</strong> بروید و سکرت دیتابیس را کپی کرده و در فیلد <code className="text-amber-400 font-mono">FIREBASE_AUTH</code> قرار دهید.
                  </p>
                </div>

                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-1.5">
                  <span className="font-bold text-blue-300 block">روش دوم: باز کردن قوانین Rules (سریع و ساده)</span>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    در همان صفحه Realtime Database به تب <strong>Rules</strong> بروید و قوانین را روی مجاز (true) قرار دهید تا نیازی به سکرت نباشد.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Security Rules Snippet */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold text-white">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>کد پیشنهادی تب Rules در Realtime Database (برای کپی آسان):</span>
          </div>

          <button
            onClick={() => handleCopy(recommendedRules, 'rules')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs transition-all cursor-pointer"
          >
            {copiedId === 'rules' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>کپی قوانین</span>
          </button>
        </div>

        <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-850 text-xs text-amber-300/90 font-mono select-all leading-relaxed" dir="ltr">
          {recommendedRules}
        </pre>
      </div>

      {/* Live Interactive Tester & Setup Tool */}
      <div className="bg-slate-900 border border-amber-500/40 rounded-2xl p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2.5">
            <Flame className="w-5 h-5 text-amber-400" />
            <h3 className="text-base font-bold text-white">تست زنده اتصال فایربیس و ذخیره در .env</h3>
          </div>
          <span className="text-xs text-slate-400">آدرس دیتابیس خود را اینجا وارد کرده و تست کنید</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              آدرس پایگاه داده فایربیس (FIREBASE_DB_URL) <span className="text-amber-400">*</span>
            </label>
            <input
              type="text"
              dir="ltr"
              placeholder="https://YOUR-PROJECT-default-rtdb.firebaseio.com"
              value={testUrl}
              onChange={(e) => setTestUrl(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              کلید یا سکرت فایربیس (FIREBASE_AUTH) <span className="text-slate-500">(اختیاری)</span>
            </label>
            <input
              type="password"
              dir="ltr"
              placeholder="Database Secret یا توکن احراز هویت"
              value={testAuth}
              onChange={(e) => setTestAuth(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-white font-mono focus:border-amber-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <button
            onClick={handleTestConnection}
            disabled={isTesting || !testUrl}
            className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50 shadow-md shadow-amber-500/20"
          >
            {isTesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Flame className="w-4 h-4" />}
            <span>{isTesting ? 'در حال برقراری ارتباط با فایربیس...' : 'تست زنده اتصال فایربیس'}</span>
          </button>

          <button
            onClick={handleSaveToEnv}
            disabled={isSaving || !testUrl}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50 shadow-md shadow-emerald-600/20"
          >
            {saveSuccess ? <Check className="w-4 h-4" /> : <Database className="w-4 h-4" />}
            <span>{saveSuccess ? 'در .env ذخیره شد! ✅' : 'ذخیره در فایل .env'}</span>
          </button>
        </div>

        {/* Test Result Message */}
        {testResult && (
          <div
            className={`p-4 rounded-xl text-xs space-y-2 border animate-fadeIn ${
              testResult.ok
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
            }`}
          >
            <div className="flex items-center justify-between font-bold text-sm">
              <span className="flex items-center gap-2">
                {testResult.ok ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    {testResult.message}
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    اتصال برقرار نشد:
                  </>
                )}
              </span>
              {testResult.latencyMs && (
                <span className="text-xs font-mono text-slate-400">
                  تاخیر پینگ: {testResult.latencyMs}ms
                </span>
              )}
            </div>

            {!testResult.ok ? (
              <p className="text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                {testResult.error}
              </p>
            ) : (
              <div className="text-slate-300 text-xs">
                ربات‌های پایتون اکنون می‌توانند به طور خودکار رویدادها، وضعیت‌ها و بکاپ جدول‌ها را روی این پایگاه داده ثبت کنند.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
