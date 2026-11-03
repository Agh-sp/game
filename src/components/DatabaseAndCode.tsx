import React, { useState, useEffect } from 'react';
import { Database, FileCode, Folder, ChevronRight, Eye, Table, Check, Copy } from 'lucide-react';

export const DatabaseAndCode: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedFile, setSelectedFile] = useState<string>('core/config.py');
  const [fileContent, setFileContent] = useState<string>('');
  const [isLoadingFile, setIsLoadingFile] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const dbCategories = [
    { key: 'all', title: 'کل ۴۸ جدول' },
    { key: 'users', title: 'کاربران و ادمین‌ها' },
    { key: 'military', title: 'نظامی و پایگاه‌ها' },
    { key: 'world', title: 'کشورها و نفت' },
    { key: 'war', title: 'جنگ و سازمان ملل' },
    { key: 'treaties', title: 'تنگه‌ها و پیمان‌ها' },
    { key: 'finance', title: 'فیش‌ها و فایربیس' },
  ];

  const dbTables = [
    { name: 'admins', cat: 'users', rows: 'ادمین‌ها با سطح دسترسی تفکیک‌شده (perms)' },
    { name: 'users', cat: 'users', rows: 'بازیکنان، سکه شاهی، پول و وضعیت بن' },
    { name: 'states', cat: 'users', rows: 'امپراطوری کاربر: رضایت، مالیات، یارانه، قطعی برق/آب/گاز' },
    { name: 'admin_logs', cat: 'users', rows: 'ثبت تک‌تک عملیات ادمین‌ها' },
    { name: 'countries', cat: 'world', rows: '۴۵ کشور با پرچم، ویژه/رایگان، جمعیت و دریا' },
    { name: 'currencies', cat: 'world', rows: 'ارز هر کشور با امتیاز ۲۴ ساعته و ارز مرجع بازی' },
    { name: 'currency_proposals', cat: 'world', rows: 'درخواست تغییر نام یا ساخت ارز توسط بازیکن' },
    { name: 'equipment_categories', cat: 'military', rows: '۵ دسته اصلی: هوا، زمین، دریا، سایبر، فضا' },
    { name: 'equipment', cat: 'military', rows: '۲۴ تجهیزات با اتک، دف، سایبر، سرعت و قیمت' },
    { name: 'user_equipment', cat: 'military', rows: 'موجودی تسلیحات خریداری‌شده هر بازیکن' },
    { name: 'soldier_types', cat: 'military', rows: '۶ دسته نیرو: سرباز، تکاور، ویژه، خلبان، غواص، هکر' },
    { name: 'soldier_trainings', cat: 'military', rows: 'صف آموزش نیروها تا سقف ۵٪ جمعیت' },
    { name: 'bases', cat: 'military', rows: 'پایگاه‌های نظامی ساخته‌شده در خاک کشورهای دیگر' },
    { name: 'base_requests', cat: 'military', rows: 'درخواست احداث پایگاه بین رهبران' },
    { name: 'buildings', cat: 'world', rows: '۳۸ ساختمان: نیروگاه‌ها، چاه‌ها، مزارع، بیمارستان‌ها' },
    { name: 'user_buildings', cat: 'world', rows: 'ساختمان‌های ساخته‌شده هر کشور' },
    { name: 'projects', cat: 'world', rows: 'پروژه‌های ملی: موزه، برج ملی، ویروس، غنی‌سازی، ماه' },
    { name: 'user_projects', cat: 'world', rows: 'پژوهش‌ها و پروژه‌های فعال بازیکن' },
    { name: 'companies', cat: 'world', rows: '۶ نوع شرکت اقتصادی بازیکن‌ها با اعلان کانال' },
    { name: 'laws', cat: 'world', rows: '۱۰ قانون کشوری با اثرات اقتصادی و اجتماعی' },
    { name: 'religions', cat: 'world', rows: '۶ دین با اثرات مذهبی بر روحیه و قوانین' },
    { name: 'governments', cat: 'world', rows: '۶ نظام حکومتی با اثرات ساختاری بر کشور' },
    { name: 'straits', cat: 'treaties', rows: '۸ تنگه استراتژیک جهان و مالک فعلی' },
    { name: 'strait_history', cat: 'treaties', rows: 'تاریخچه تسخیر و نبردهای دریایی تنگه‌ها' },
    { name: 'treaties', cat: 'treaties', rows: '۵ پیمان: اتحاد دفاعی، رفیقای تجاری، صلح، اعتماد، برادران' },
    { name: 'treaty_history', cat: 'treaties', rows: 'ثبت خیانت‌ها و لغو پیمان‌ها با رسوایی در کانال' },
    { name: 'negotiations', cat: 'treaties', rows: 'مذاکرات مخفیانه بین دو یا سه کشور' },
    { name: 'direct_trades', cat: 'treaties', rows: 'معاوضه پایاپای نیرو، پول، نفت و تجهیزات' },
    { name: 'wars', cat: 'war', rows: 'جنگ‌های فعال با وضعیت رسمی یا غافلگیرانه' },
    { name: 'battles', cat: 'war', rows: 'نبردهای ثبت‌شده و محاسبه غنایم جنگی' },
    { name: 'cyber_attacks', cat: 'war', rows: 'عملیات سایبری دزدی خزانه، ترور رهبر و تداخل سرور' },
    { name: 'un_votes', cat: 'war', rows: 'رأی‌گیری‌های سازمان ملل با وزن ۲ برای ابرقدرت‌ها' },
    { name: 'un_user_votes', cat: 'war', rows: 'آرای ثبت‌شده تک‌تک کشورها در قطعنامه‌ها' },
    { name: 'un_statements', cat: 'war', rows: 'بیانیه‌های رسمی منتشرشده در صحن سازمان ملل' },
    { name: 'un_sanctions', cat: 'war', rows: 'تحریم‌های تسلیحاتی، تجاری و برکناری رهبران' },
    { name: 'oil_wells', cat: 'world', rows: 'مخازن زیرزمینی و دکل‌های استخراج نفت' },
    { name: 'oil_extractions', cat: 'world', rows: 'تولید خودکار هر ۳۰ دقیقه و رکوردهای حفاری' },
    { name: 'oil_trades', cat: 'world', rows: 'فروش نفت خام به خزانه یا تبدیل به سکه شاهی' },
    { name: 'rescue_campaigns', cat: 'treaties', rows: 'کمپین‌های امدادی سازمان نجات حین جنگ‌ها' },
    { name: 'rescue_votes', cat: 'treaties', rows: 'اهدای انرژی به سازمان نجات و بازکردن ذخیره ۱۰٪' },
    { name: 'seasons', cat: 'world', rows: 'سیزن‌های بازی: جنگ جهانی، صلیبی، عهد باستان' },
    { name: 'season_votes', cat: 'world', rows: 'نظرسنجی کانال برای تغییر مود سیزن بعدی' },
    { name: 'daily_missions', cat: 'users', rows: '۷ ماموریت روزانه همراه با پاداش سکه و پول' },
    { name: 'user_missions', cat: 'users', rows: 'وضعیت تکمیل ماموریت‌های هر بازیکن در روز' },
    { name: 'receipts', cat: 'finance', rows: 'فیش‌های بانکی کارت‌به‌کارت بازیکنان برای تأیید ادمین' },
    { name: 'tickets', cat: 'users', rows: 'تیکت‌های پشتیبانی ارسالی بازیکنان' },
    { name: 'ticket_replies', cat: 'users', rows: 'پاسخ‌های دوطرفه ادمین‌ها به بازیکن' },
    { name: 'fb_queue', cat: 'finance', rows: 'صف آفلاین همگام‌سازی REST با فایربیس ابری' },
  ];

  const sourceFiles = [
    { path: 'core/config.py', title: 'core/config.py (تنظیمات توکن‌ها)' },
    { path: 'core/db.py', title: 'core/db.py (اسکیمای ۴۸ جدول SQLite)' },
    { path: 'core/seed.py', title: 'core/seed.py (داده‌های اولیه کشورها و سلاح‌ها)' },
    { path: 'core/firebase.py', title: 'core/firebase.py (لایه اتصال فایربیس)' },
    { path: 'core/economy.py', title: 'core/economy.py (محاسبات رضایت و درآمد)' },
    { path: 'core/scheduler.py', title: 'core/scheduler.py (تیک خودکار ۳۰ دقیقه)' },
    { path: 'core/treaties.py', title: 'core/treaties.py (پیمان‌ها و سازوکار خیانت)' },
    { path: 'core/straits.py', title: 'core/straits.py (قواعد تنگه‌های دریایی)' },
    { path: 'core/oil.py', title: 'core/oil.py (مخازن و دکل‌های نفت)' },
    { path: 'gamebot/main.py', title: 'gamebot/main.py (هسته ربات بازی)' },
    { path: 'adminbot/main.py', title: 'adminbot/main.py (هسته ربات ادمین)' },
    { path: 'run_all.py', title: 'run_all.py (اجرای همزمان دو ربات)' },
  ];

  const filteredTables = dbTables.filter(
    (t) => selectedCategory === 'all' || t.cat === selectedCategory
  );

  const fetchFile = async (filePath: string) => {
    setSelectedFile(filePath);
    setIsLoadingFile(true);
    try {
      const res = await fetch(`/api/files/read?path=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.type === 'file') {
        setFileContent(data.content);
      } else {
        setFileContent(JSON.stringify(data, null, 2));
      }
    } catch (err: any) {
      setFileContent(`خطا در بارگذاری فایل: ${err.message}`);
    } finally {
      setIsLoadingFile(false);
    }
  };

  useEffect(() => {
    fetchFile('core/config.py');
  }, []);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(fileContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
            <Database className="w-3.5 h-3.5 text-indigo-400" />
            معماری دیتابیس ۴۸ جدوله و مرورگر سورس‌کد پروژه
          </div>
          <h2 className="text-xl font-black text-white">پایگاه داده کامل SQLite و فایل‌های پایتون پروژه جنگ جهانی</h2>
          <p className="text-xs text-slate-400">
            مشاهده آنلاین اسکیمای تمامی جدول‌ها و خواندن مستقیم کدهای ربات‌ها بدون نیاز به خارج شدن از وب‌اپلیکیشن
          </p>
        </div>
      </div>

      {/* Code Viewer & File Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <FileCode className="w-5 h-5 text-amber-400" />
            <h3 className="text-base font-bold text-white">مرورگر سورس‌کد پایتون پروژه</h3>
            <span className="text-xs font-mono text-slate-400">({selectedFile})</span>
          </div>

          <button
            onClick={handleCopyCode}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs transition-all cursor-pointer self-start sm:self-auto"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'کپی شد!' : 'کپی کل کد'}</span>
          </button>
        </div>

        {/* File Pills Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none">
          {sourceFiles.map((f) => (
            <button
              key={f.path}
              onClick={() => fetchFile(f.path)}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono whitespace-nowrap transition-all cursor-pointer ${
                selectedFile === f.path
                  ? 'bg-amber-500 text-slate-950 font-bold shadow-md shadow-amber-500/20'
                  : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-850'
              }`}
            >
              {f.title}
            </button>
          ))}
        </div>

        {/* Code Content Display */}
        <div className="relative">
          {isLoadingFile ? (
            <div className="h-96 flex items-center justify-center text-xs text-slate-400">
              در حال بارگذاری فایل...
            </div>
          ) : (
            <pre
              className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-emerald-200/90 font-mono h-[420px] overflow-y-auto select-all leading-relaxed"
              dir="ltr"
            >
              {fileContent}
            </pre>
          )}
        </div>
      </div>

      {/* 48 DB Tables Explorer */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Table className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-white">فهرست کامل ۴۸ جدول پایگاه داده SQLite</h3>
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1">
            {dbCategories.map((cat) => (
              <button
                key={cat.key}
                onClick={() => setSelectedCategory(cat.key)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  selectedCategory === cat.key
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                {cat.title}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredTables.map((t, idx) => (
            <div
              key={idx}
              className="bg-slate-900 border border-slate-800 hover:border-indigo-500/40 p-4 rounded-2xl transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-indigo-300 flex items-center gap-1.5" dir="ltr">
                  <Database className="w-3.5 h-3.5 text-indigo-400" />
                  {t.name}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                  جدول #{idx + 1}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{t.rows}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
