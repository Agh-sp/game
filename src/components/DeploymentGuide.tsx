import React, { useState } from 'react';
import { Terminal, Copy, Check, Server, Shield, Flame, Play, Clock, AlertCircle } from 'lucide-react';

export const DeploymentGuide: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const steps = [
    {
      id: 'step1',
      title: '۱. ورود به سرور مجازی (Linux VPS) و نصب پیش‌نیازها',
      desc: 'سیستم‌عامل پیشنهادی Ubuntu 22.04 یا 24.04 با پایتون نسخه 3.10 به بالا می‌باشد.',
      code: `sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git screen tmux`,
    },
    {
      id: 'step2',
      title: '۲. آماده‌سازی محیط مجازی و نصب کتابخانه‌های بازی',
      desc: 'کتابخانه‌های aiogram (نسخه 3) و aiosqlite و aiohttp نصب خواهند شد.',
      code: `cd game
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt`,
    },
    {
      id: 'step3',
      title: '۳. پیکربندی سکرت‌ها در فایل .env',
      desc: 'فایل .env.example را به .env تبدیل کنید و توکن‌های دو ربات و آیدی سوپرادمین را قرار دهید.',
      code: `cp .env.example .env
nano .env

# مقادیر زیر را در فایل وارد کرده و ذخیره نمایید:
GAME_BOT_TOKEN=9201202722:AAGuSaJQw16F_ugrKXUidttYfMqI9Cz3SVE
ADMIN_BOT_TOKEN=9000162449:AAG-xoIDUSgE1LFWr1L3BOZjygueYuCZOfU
SUPER_ADMIN_ID=8666501866`,
    },
    {
      id: 'step4',
      title: '۴. اجرای بازی، پنل وب و ساخت خودکار دیتابیس (کاملاً پایتونی)',
      desc: 'در اولین اجرا، دیتابیس wwgame.db با تمامی ۴۵ کشور، تجهیزات و ۸ تنگه به طور اتوماتیک ساخته و Seed می‌شود. پنل فرماندهی وب هم با پایتون اجرا می‌شود — دیگر نیازی به Node.js نیست.',
      code: `# اجرای پنل وب + هر دو ربات (پیشنهادی):
python3 server.py            # از ریشهٔ پروژه
# یا:
cd worldwar-game && python3 run_all.py

# فقط ربات‌ها (بدون پنل وب):
python3 run_bots.py

# یا اجرای جداگانه در دو پنجره یا دو سرور:
python3 run_game.py     # فقط ربات اصلی بازیکنان
python3 run_admin.py    # فقط پنل مدیریت ادمین

# پنل فرماندهی وب:  http://SERVER_IP:3000
# سلامت سرویس:      http://SERVER_IP:3000/health`,
    },
    {
      id: 'step5',
      title: '۵. اجرای دائمی و ۲۴ ساعته با Systemd (سرویس خودکار در پس‌زمینه)',
      desc: 'برای اینکه پس از بستن ترمینال، ربات‌ها همیشه روشن بمانند و در صورت ریبوت سرور خودکار بالا بیایند:',
      code: `sudo nano /etc/systemd/system/wwgame.service

[Unit]
Description=World War Telegram Game + Command Center (Python)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/game
ExecStart=/root/game/venv/bin/python3 server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# فعال‌سازی و استارت سرویس:
sudo systemctl daemon-reload
sudo systemctl enable wwgame
sudo systemctl start wwgame
sudo systemctl status wwgame`,
    },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-semibold">
            <Server className="w-3.5 h-3.5 text-amber-400" />
            راهنمای استقرار و میزبانی ۲۴ ساعته (Deployment & 24/7 Hosting)
          </div>
          <h2 className="text-xl font-black text-white">نحوه راه‌اندازی ربات‌ها روی سرور لینوکس یا هاست پایتون</h2>
          <p className="text-xs text-slate-400">
            آموزش قدم به قدم نصب پیش‌نیازها، تنظیم سکرت‌ها، سرویس Systemd و اتصال فایربیس
          </p>
        </div>
      </div>

      {/* Steps List */}
      <div className="space-y-4">
        {steps.map((step) => (
          <div
            key={step.id}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-lg hover:border-slate-700 transition-all"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
              <div>
                <h3 className="font-bold text-sm text-white">{step.title}</h3>
                <p className="text-xs text-slate-400 mt-0.5">{step.desc}</p>
              </div>

              <button
                onClick={() => handleCopy(step.code, step.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs transition-all cursor-pointer self-start sm:self-auto shrink-0"
              >
                {copiedId === step.id ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
                <span>{copiedId === step.id ? 'کپی شد' : 'کپی دستورات'}</span>
              </button>
            </div>

            <pre
              className="p-4 rounded-xl bg-slate-950 border border-slate-850 text-xs text-amber-200/90 font-mono overflow-x-auto select-all leading-relaxed"
              dir="ltr"
            >
              {step.code}
            </pre>
          </div>
        ))}
      </div>

      {/* Pro Tips Box */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-amber-500/30 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex items-center gap-2.5">
          <Shield className="w-5 h-5 text-amber-400" />
          <h3 className="text-base font-bold text-white">نکات طلایی مدیریت و رفع خطاهای متداول</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
            <span className="font-bold text-amber-300 block">ریست کامل و شروع سیزن جدید:</span>
            <p className="text-slate-300 leading-relaxed">
              برای پاک کردن تمام پیشرفت بازیکنان و شروع سیزن از اول، کافی است ربات را متوقف کرده و فایل <code className="text-amber-400 font-mono">wwgame.db</code> را حذف کنید؛ با اجرای بعدی دیتابیس مجدداً تازه تولید می‌شود.
            </p>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
            <span className="font-bold text-blue-300 block">ارسال پیام‌های ربات ادمین به بازیکنان:</span>
            <p className="text-slate-300 leading-relaxed">
              ربات ادمین برای ارسال پاسخ تیکت، تأیید فیش و پیام همگانی از توکن ربات اصلی بازی استفاده می‌کند تا پیام‌ها از دید بازیکن در همان چت بازی تحویل داده شوند.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
