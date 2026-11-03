import React, { useState } from 'react';
import { Bot, Send, Shield, RefreshCw, CheckCircle2, ChevronRight, User, DollarSign, Flame, Swords, Anchor, Globe, ArrowLeft, Award, HelpCircle } from 'lucide-react';

interface BotSimulatorProps {
  botStatus: any;
}

export const BotSimulator: React.FC<BotSimulatorProps> = ({ botStatus }) => {
  const [activeBot, setActiveBot] = useState<'game' | 'admin'>('game');

  // Simulated Game Bot State
  const [currentScreen, setCurrentScreen] = useState<string>('home');
  const [selectedCountry, setSelectedCountry] = useState<string>('ایران 🇮🇷');
  const [treasury, setTreasury] = useState<number>(50_000_000);
  const [royalCoins, setRoyalCoins] = useState<number>(120);
  const [oilBarrels, setOilBarrels] = useState<number>(4500);
  const [oilRigs, setOilRigs] = useState<number>(3);
  const [satisfaction, setSatisfaction] = useState<number>(78);
  const [messages, setMessages] = useState<Array<{ sender: 'bot' | 'user'; text: string; buttons?: string[][]; time: string }>>([
    {
      sender: 'bot',
      text: `🌍 سلام به بازی استراتژیک «جنگ جهانی» خوش آمدید!\n\nشما هم‌اکنون رهبر کشور **ایران 🇮🇷** هستید.\nخزانه ملی: ۵۰,۰۰۰,۰۰۰ ریال | سکه شاهی: ۱۲۰ 🪙\nدرصد رضایت عمومی مردم: ۷۸٪`,
      time: '12:00',
    },
  ]);

  const addMessage = (userText: string, botResponse: string, buttons?: string[][]) => {
    const time = new Date().toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    setMessages((prev) => [
      ...prev,
      { sender: 'user', text: userText, time },
      { sender: 'bot', text: botResponse, buttons, time },
    ]);
  };

  // Simulated actions
  const handleAction = (btn: string) => {
    switch (btn) {
      case '🏰 امپراطوری من':
        setCurrentScreen('empire');
        addMessage(
          btn,
          `🏰 **کاخ فرمانروایی امپراطوری شما**\n\nکشور: ${selectedCountry}\n💰 موجودی خزانه: ${treasury.toLocaleString()} ریال\n🪙 سکه شاهی: ${royalCoins} عدد\n🛢️ ذخایر استخراج‌شده نفت: ${oilBarrels.toLocaleString()} بشکه\n😊 ضریب رضایت مردمی: ${satisfaction}٪\n⚡ برق: پایدار | 💧 آب: نرمال | 🔥 گاز: متصل\n\nیک بخش را جهت هدایت انتخاب فرمایید:`,
          [
            ['👥 مردم و انرژی', '🛢️ صنعت نفت و دکل‌ها'],
            ['🏗️ پروژه‌های ملی', '🪖 ارتش و تسلیحات'],
            ['⛪ دین و حکومت', '💵 اقتصاد و نرخ ارز'],
            ['🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '👥 مردم و انرژی':
        setCurrentScreen('people');
        addMessage(
          btn,
          `👥 **مدیریت امور مردم، زیرساخت‌ها و خدمات**\n\n⚡ شبکه برق: ۳ نیروگاه فعال\n💧 منابع آب: تصفیه‌خانه + استخراج چاه عمیق\n🔥 شبکه گاز: ۲ ایستگاه تقویت فشار\n🍞 وضعیت غذا و آرد: کافی برای ۴۵ روز\n\nگزینه مورد نظر را جهت تخصیص بودجه برگزینید:`,
          [
            ['⚡ احداث نیروگاه جدید', '💧 حفاری چاه عمیق'],
            ['🍞 خرید گندم و غلات', '🏥 توسعه مراکز درمانی'],
            ['🏰 بازگشت به امپراطوری من'],
          ]
        );
        break;

      case '🛢️ صنعت نفت و دکل‌ها':
        setCurrentScreen('oil');
        addMessage(
          btn,
          `🛢️ **سازمان اکتشاف و استخراج نفت خام**\n\nمخزن زیرزمینی برآورد شده: ۲۰۸ میلیارد بشکه\nتعداد دکل‌های فعال: ${oilRigs} دکل دریایی و زمینی\nنرخ استخراج خودکار: هر ۳۰ دقیقه ${oilRigs * 250} بشکه\nموجودی آماده فروش: ${oilBarrels.toLocaleString()} بشکه\nقیمت روز هر بشکه: ۸۵,۰۰۰ ریال`,
          [
            ['🏗️ ساخت دکل نفتی جدید (-۱۲ میلیون)', '🔍 عملیات اکتشاف میدان جدید'],
            ['💵 فروش ۵,۰۰۰ بشکه نفت به خزانه', '🪙 صادرات در ازای سکه شاهی'],
            ['🏰 بازگشت به امپراطوری من'],
          ]
        );
        break;

      case '🏗️ ساخت دکل نفتی جدید (-۱۲ میلیون)':
        if (treasury >= 12_000_000) {
          setTreasury((t) => t - 12_000_000);
          setOilRigs((r) => r + 1);
          setOilBarrels((b) => b + 1000);
          addMessage(
            btn,
            `✅ دکل نفتی جدید با موفقیت احداث شد!\nتعداد کل دکل‌ها به ${oilRigs + 1} عدد رسید.\nظرفیت استخراج کشور شما افزایش یافت.`
          );
        } else {
          addMessage(btn, `❌ موجودی خزانه شما برای احداث دکل کافی نیست! (نیازمند ۱۲ میلیون ریال)`);
        }
        break;

      case '💵 فروش ۵,۰۰۰ بشکه نفت به خزانه':
        if (oilBarrels >= 5000) {
          setOilBarrels((b) => b - 5000);
          setTreasury((t) => t + 5000 * 85000);
          addMessage(
            btn,
            `💰 ۵,۰۰۰ بشکه نفت خام به ارزش ۴۲۵,۰۰۰,۰۰۰ ریال به فروش رفت و به خزانه کشور واریز شد!`
          );
        } else {
          addMessage(btn, `⚠️ موجودی نفت استخراج‌شده شما کمتر از ۵,۰۰۰ بشکه است!`);
        }
        break;

      case '⚔️ اتاق جنگ':
        setCurrentScreen('war');
        addMessage(
          btn,
          `⚔️ **اتاق فرماندهی ستاد کل نیروهای مسلح**\n\nنیروهای ارتش شما آماده دریافت دستور نبرد هستند:\n✈️ اسکادران هوایی: ۱۲ جنگنده و بمب‌افکن\n🪖 لشکرهای زرهی: ۵۰ تانک و نفربر\n⚓ ناوگان دریایی: ۴ ناو و زیردریایی\n💻 یگان جنگ سایبری: ۵ تیم هک دولتی\n\nنوع عملیات مورد نظر را تعیین فرمایید:`,
          [
            ['🎯 اعلان جنگ رسمی با مجوز سازمان ملل', '⚡ تهاجم غافلگیرانه و برق‌آسا'],
            ['💻 حمله سایبری به خزانه و سرور دشمن', '🛡️ آماده‌باش پدافند یکپارچه'],
            ['🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '💻 حمله سایبری به خزانه و سرور دشمن':
        const win = Math.random() > 0.4;
        if (win) {
          const loot = 25_000_000;
          setTreasury((t) => t + loot);
          addMessage(
            btn,
            `💻 **پیروزی سایبری درخشان!**\nتیم هک شما فایروال‌های بانک مرکزی هدف را دور زد و مبلغ ${loot.toLocaleString()} ریال به حساب مخفی خزانه شما منتقل شد!`
          );
        } else {
          setSatisfaction((s) => Math.max(10, s - 5));
          addMessage(
            btn,
            `🛡️ **دفاع سایبری دشمن مانع شد!**\nحمله شما توسط سپرهای الکترونیک هدف خنثی گردید و ردپای تیم ردیابی شد (-۵٪ رضایت مردم).`
          );
        }
        break;

      case '🤝 تجارت و تنگه‌ها':
        setCurrentScreen('trade');
        addMessage(
          btn,
          `🤝 **دیپلماسی بین‌المللی و کنترل تنگه‌های راهبردی**\n\n۸ تنگه استراتژیک جهان:\n⚓ تنگه هرمز | 🚢 کانال سوئز | 🌊 تنگه مالاکا | ⚓ جبل‌الطارق\n🌊 باب‌المندب | ⚓ بسفر و داردانل | 🚢 کانال پاناما | ❄️ تنگه برینگ\n\nپیمان‌های ۵گانه:\n۱. اتحاد دفاعی ۳۰٪ | ۲. رفیقای تجاری با امکان خیانت\n۳. صلح پایدار | ۴. پیمان اعتماد با شاهد ملل | ۵. برادران تنی`,
          [
            ['🕊️ آغاز مذاکره مخفیانه با کشور دیگر', '⚓ تسخیر تنگه هرمز با نیروی دریایی'],
            ['📜 امضای پیمان اتحاد نظامی', '🔄 تبادل کالا و انرژی پایاپای'],
            ['🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🪙 سکه شاهی':
        setCurrentScreen('royal_coins');
        addMessage(
          btn,
          `🪙 **درگاه تهیه سکه سلطنتی شاهی**\n\nارز مرجع خرید کشورهای ویژه، تسلیحات فضایی و پروژه‌های برتر.\nقیمت روز هر سکه شاهی: ۳۴,۰۰۰,۰۰۰ تومان\n\nپکیج‌های تخفیفی:\n📦 پکیج برنزی: ۵۰ سکه\n📦 پکیج نقره‌ای: ۱۵۰ سکه\n📦 پکیج طلایی: ۵۰۰ سکه (+۲۰٪ رایگان)`,
          [
            ['💳 خرید آنلاین و ارسال عکس فیش', '🔄 تبدیل سکه شاهی به ریال'],
            ['📦 انتخاب پکیج سکه تخفیف‌دار', '🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🎯 ماموریت روزانه':
        setCurrentScreen('daily');
        addMessage(
          btn,
          `🎯 **ماموریت‌های روزانه (ساعت ۰۰:۰۰ ریست می‌شود)**\n\n۱. احداث یک پروژه زیربنایی: 🪙 ۵ سکه شاهی (انجام نشده ❌)\n۲. مانور مشترک یا آموزش ۵۰ سرباز: 💰 ۱۰ میلیون ریال (انجام شد ✅)\n۳. فروش حداقل ۳۰۰۰ بشکه نفت: 🪙 ۱۰ سکه شاهی (انجام شد ✅)\n۴. رأی در مجمع عمومی سازمان ملل: 💰 ۵ میلیون ریال (آماده دریافت 🎁)`,
          [
            ['🎁 دریافت پاداش ماموریت‌های تکمیل‌شده', '🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🇺🇳 سازمان ملل':
        setCurrentScreen('un');
        addMessage(
          btn,
          `🇺🇳 **مجمع عمومی و شورای امنیت سازمان ملل متحد**\n\nرأی‌گیری‌های در جریان:\nقطعنامه ۲۲۸۴: تحریم تسلیحاتی کشورهای متخاصم حوزه اقیانوس هند\nوضعیت رأی شما: ثبت نشده\nحق وتوی قدرت‌ها: ۵ قدرت بزرگ دارای ضریب رأی ۲ برابری می‌باشند.`,
          [
            ['✅ رأی موافق به قطعنامه', '❌ رأی مخالف', '🚫 وتو قطعنامه (مخصوص ابرقدرت‌ها)'],
            ['📜 ثبت بیانیه رسمی جدید', '🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🔙 بازگشت به منوی اصلی':
      case '🏰 بازگشت به امپراطوری من':
      default:
        setCurrentScreen('home');
        addMessage(
          btn,
          `🏰 **منوی اصلی امپراطوری شما**\nرهبر محترم، جهت نظارت بر قلمرو خود یک بخش را انتخاب فرمایید:`,
          [
            ['🏰 امپراطوری من', '⚔️ اتاق جنگ'],
            ['🤝 تجارت و تنگه‌ها', '🇺🇳 سازمان ملل'],
            ['🪙 سکه شاهی', '🎯 ماموریت روزانه'],
          ]
        );
        break;
    }
  };

  // Admin Bot actions
  const handleAdminAction = (btn: string) => {
    const time = new Date().toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    let reply = '';
    let adminBtns: string[][] = [];

    switch (btn) {
      case '👥 مدیریت کاربران':
        reply = `👥 **پنل کاربران بازی**\n\nتعداد کل اعضا: ۱,۴۲۰ بازیکن\nکاربران فعال امروز: ۶۸۰ نفر\nوضعیت مسدودیت‌ها: ۱۲ کاربر`;
        adminBtns = [['🔍 جستجوی کاربر با آیدی', '🪙 واریز/کسر سکه شاهی'], ['🚫 مسدودسازی (Ban)', '🔙 منوی مدیریت']];
        break;

      case '🪙 اقتصاد و فیش‌ها':
        reply = `🪙 **مدیریت مالی و نرخ‌ها**\n\nقیمت هر سکه شاهی: ۳۴,۰۰۰,۰۰۰ تومان\nفیش‌های در انتظار بررسی: ۳ فیش جدید\nشماره کارت فعال: ۶۰۳۷-۹۹۷۵-****-۲۸۱۴`;
        adminBtns = [['🧾 مشاهده فیش‌های جدید', '✏️ تغییر قیمت سکه شاهی'], ['💳 تغییر شماره کارت', '🔙 منوی مدیریت']];
        break;

      case '📣 پیام همگانی':
        reply = `📣 **ارسال برودکست به تمام کاربران**\n\nاین پیام از طریق توکن ربات اصلی بازی به تمام ۱,۴۲۰ بازیکن ارسال خواهد شد. متن پیام را آماده فرمایید.`;
        adminBtns = [['📝 نوشتن پیام اعلان عمومی', '🔙 منوی مدیریت']];
        break;

      case '🗄️ مرورگر دیتابیس خام':
        reply = `🗄️ **مرور مستقیم ۴۸ جدول SQLite**\n\nجداول اصلی:\n• users (۱,۴۲۰ سطر)\n• countries (۴۵ سطر)\n• equipment (۲۴ سطر)\n• straits (۸ سطر)\n• treaties (۱۲ سطر)\n• wars (۳ جنگ فعال)`;
        adminBtns = [['📊 مشاهده وضعیت جداول', '🔙 منوی مدیریت']];
        break;

      default:
        reply = `🛡️ **پنل مدیریت کل بازی جنگ جهانی (سوپرادمین)**\n\nشناسه شما: 8358901937 (SuperAdmin ✅)\nوضعیت سرور: 🟢 آنلاین و متصل به دیتابیس\nسکرت‌ها: هر دو توکن احراز هویت شده‌اند.`;
        adminBtns = [
          ['👥 مدیریت کاربران', '🪙 اقتصاد و فیش‌ها'],
          ['🪖 تسلیحات و کشورها', '📣 پیام همگانی'],
          ['🗄️ مرورگر دیتابیس خام', '⚙️ تنظیمات و کانال‌ها'],
        ];
        break;
    }

    setMessages((prev) => [
      ...prev,
      { sender: 'user', text: btn, time },
      { sender: 'bot', text: reply, buttons: adminBtns, time },
    ]);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Bot Switcher Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-xl">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-semibold">
            <Bot className="w-3.5 h-3.5 text-blue-400" />
            شبیه‌ساز زنده محیط تلگرام (Telegram In-Browser Emulator)
          </div>
          <h2 className="text-xl font-black text-white">تست گیم‌پلی دو ربات تلگرام در محیط وب</h2>
          <p className="text-xs text-slate-400">
            شما می‌توانید دکمه‌ها، منطق‌های استراتژیک، تولید درآمد، استخراج نفت و پنل ادمین را عیناً مانند تلگرام در این بخش آزمایش کنید.
          </p>
        </div>

        {/* Switcher Buttons */}
        <div className="flex items-center bg-slate-950 p-1.5 rounded-xl border border-slate-800 shrink-0">
          <button
            onClick={() => {
              setActiveBot('game');
              handleAction('🔙 بازگشت به منوی اصلی');
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeBot === 'game'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Bot className="w-4 h-4" />
            <span>ربات اصلی بازی (@TetrisBEQRQEBot)</span>
          </button>
          <button
            onClick={() => {
              setActiveBot('admin');
              handleAdminAction('🔙 منوی مدیریت');
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeBot === 'admin'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Shield className="w-4 h-4" />
            <span>ربات ادمین (@ADmminFIREWOrldBOT)</span>
          </button>
        </div>
      </div>

      {/* Main Telegram Phone Mockup */}
      <div className="max-w-2xl mx-auto bg-slate-950 border-2 border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col h-[680px]">
        {/* Telegram Header */}
        <div className="bg-slate-900 border-b border-slate-800 px-5 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm ${
                activeBot === 'game' ? 'bg-gradient-to-tr from-amber-600 to-rose-600' : 'bg-gradient-to-tr from-blue-600 to-indigo-600'
              }`}
            >
              {activeBot === 'game' ? 'WW' : 'AD'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-sm">
                  {activeBot === 'game' ? 'FF (ربات بازی جنگ جهانی)' : 'AdminBOT_WOF (پنل ادمین)'}
                </span>
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                {activeBot === 'game' ? '@TetrisBEQRQEBot' : '@ADmminFIREWOrldBOT'}
              </span>
            </div>
          </div>

          <div className="text-right text-[11px] text-slate-400">
            <span>bot token verified ✅</span>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-950/70">
          {messages.map((m, idx) => (
            <div key={idx} className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl p-4 text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-amber-500 text-slate-950 font-medium rounded-br-none'
                    : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-md'
                }`}
              >
                <div className="whitespace-pre-line">{m.text}</div>
                <div
                  className={`text-[10px] mt-2 text-right ${
                    m.sender === 'user' ? 'text-slate-800' : 'text-slate-500'
                  }`}
                >
                  {m.time}
                </div>
              </div>

              {/* Inline Telegram Action Buttons attached to Bot Message */}
              {m.buttons && m.buttons.length > 0 && idx === messages.length - 1 && (
                <div className="w-full max-w-[90%] mt-3 space-y-2">
                  {m.buttons.map((row, rIdx) => (
                    <div key={rIdx} className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {row.map((btn, bIdx) => (
                        <button
                          key={bIdx}
                          onClick={() => (activeBot === 'game' ? handleAction(btn) : handleAdminAction(btn))}
                          className="w-full bg-slate-850 hover:bg-slate-800 active:scale-95 text-slate-200 hover:text-white border border-slate-750 hover:border-amber-500/50 py-2.5 px-3 rounded-xl text-xs font-semibold transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer text-center"
                        >
                          {btn}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Telegram Input Bar */}
        <div className="bg-slate-900 border-t border-slate-800 p-3 shrink-0 flex items-center gap-2">
          <input
            type="text"
            placeholder="دستوری مثل /start بنویسید یا از دکمه‌های بالا انتخاب کنید..."
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.currentTarget.value) {
                if (activeBot === 'game') {
                  handleAction(e.currentTarget.value);
                } else {
                  handleAdminAction(e.currentTarget.value);
                }
                e.currentTarget.value = '';
              }
            }}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
          <button
            onClick={() => {
              if (activeBot === 'game') {
                handleAction('🏰 امپراطوری من');
              } else {
                handleAdminAction('🔙 منوی مدیریت');
              }
            }}
            className="p-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all cursor-pointer"
            title="منو"
          >
            <Send className="w-4 h-4 rotate-180" />
          </button>
        </div>
      </div>
    </div>
  );
};
