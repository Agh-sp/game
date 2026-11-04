import React, { useState, useRef, useEffect } from 'react';
import { Bot, Shield, Send, MessageSquare, Award, Coins, RefreshCw, CheckCircle2, AlertTriangle, ArrowRight, Globe } from 'lucide-react';

interface ChatMessage {
  sender: 'user' | 'bot';
  text: string;
  buttons?: string[][];
  time: string;
  isOfficial?: boolean;
}

interface ActiveNegotiation {
  id: number;
  countryName: string;
  countryFlag: string;
  status: 'open' | 'pending' | 'agreed';
  messages: { sender: string; text: string; time: string }[];
}

export const BotSimulator: React.FC = () => {
  const [activeBot, setActiveBot] = useState<'game' | 'admin'>('game');
  const [inputMsg, setInputMsg] = useState<string>('');
  const [currentScreen, setCurrentScreen] = useState<string>('home');
  const [treasury, setTreasury] = useState<number>(450_000_000);
  const [satisfaction, setSatisfaction] = useState<number>(82);
  const [oilBarrels, setOilBarrels] = useState<number>(24_500);
  const [oilRigs, setOilRigs] = useState<number>(4);
  const [navalPower, setNavalPower] = useState<number>(680);
  const [activeNegotiation, setActiveNegotiation] = useState<ActiveNegotiation | null>(null);
  const [signedTreaties, setSignedTreaties] = useState<string[]>([
    '🤝 پیمان دفاع مشترک با روسیه (۳۰٪ توان کمکی)',
    '💼 رفیقای تجاری با آلمان (۱۰٪ تسهیم سود فروش)',
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      sender: 'bot',
      text: `🇮🇷 **به بازی جنگ جهانی خوش آمدید!**\nرهبر مقتدر ایران، امپراطوری شما آماده است.\n\n🏛️ خزانه ملی: ۴۵۰,۰۰۰,۰۰۰ ریال\n👥 رضایت مردم: ۸۲٪\n🪖 قدرت نظامی: ۱,۸۵۰ (شامل ۶۸۰ ناوگان دریایی)\n🛢️ موجودی نفت: ۲۴,۵۰۰ بشکه\n\nجهت هدایت کشور، گزینه‌ای را انتخاب فرمایید:`,
      buttons: [
        ['🏰 امپراطوری من', '⚔️ اتاق جنگ'],
        ['🤝 تجارت و تنگه‌ها', '🇺🇳 سازمان ملل'],
        ['🪙 سکه شاهی', '🎯 ماموریت روزانه'],
      ],
      time: '12:00',
    },
  ]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addMessage = (userText: string | null, botText: string, buttons?: string[][], isOfficial?: boolean) => {
    const time = new Date().toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    setMessages((prev) => {
      const next = [...prev];
      if (userText) {
        next.push({ sender: 'user', text: userText, time });
      }
      next.push({ sender: 'bot', text: botText, buttons, time, isOfficial });
      return next;
    });
  };

  // Process game bot actions
  const handleAction = (btn: string) => {
    const trimmed = btn.trim();

    // 1. Specific negotiation button cases
    if (trimmed === '🕊️ آغاز مذاکره مخفیانه با کشور دیگر' || trimmed === '🕊 مذاکره' || trimmed === '➕ مذاکره جدید') {
      setCurrentScreen('neg_select');
      addMessage(
        trimmed,
        `🕊 **مرکز مذاکرات بین‌المللی و دیپلماسی محرمانه**\n\nکشور مورد نظر خود را جهت افتتاح کانال مذاکره محرمانه و انعقاد پیمان‌ها انتخاب فرمایید:\n(آغاز مذاکره در کانال رسمی اعلام شده اما گفتگوها کاملاً محرمانه خواهد بود)`,
        [
          ['🇷🇺 مذاکره با روسیه', '🇨🇳 مذاکره با چین'],
          ['🇩🇪 مذاکره با آلمان', '🇮🇶 مذاکره با عراق'],
          ['🇸🇦 مذاکره با عربستان', '🇹🇷 مذاکره با ترکیه'],
          ['🔙 بازگشت به تجارت', '🏰 بازگشت به امپراطوری من'],
        ]
      );
      return;
    }

    if (trimmed.startsWith('🇷🇺') || trimmed.startsWith('🇨🇳') || trimmed.startsWith('🇩🇪') || trimmed.startsWith('🇮🇶') || trimmed.startsWith('🇸🇦') || trimmed.startsWith('🇹🇷')) {
      const country = trimmed.replace('مذاکره با', '').trim();
      const flag = country.slice(0, 2);
      const cname = country.slice(2).trim();
      const negId = Math.floor(Math.random() * 800 + 100);

      const newNeg: ActiveNegotiation = {
        id: negId,
        countryName: cname,
        countryFlag: flag,
        status: 'open',
        messages: [
          {
            sender: `${flag} سفیر ${cname}`,
            text: `درود بر رهبر عالی‌مقام کشور ایران. کانال مذاکره رسمی گشوده شد. آماده دریافت پیشنهادات امنیتی، دفاع مشترک، تسهیم سود بازرگانی و معاهدات صلح هستیم.`,
            time: 'لحظاتی پیش',
          },
        ],
      };
      setActiveNegotiation(newNeg);
      setCurrentScreen('neg_room');

      addMessage(
        trimmed,
        `🕊 **اتاق مذاکره محرمانه #${negId} با ${flag} ${cname}**\n\nکانال مستقیم دیپلماتیک باز شد!\n\n📜 **پیام دریافتی از سفیر ${cname}:**\n«درود بر رهبر عالی‌مقام کشور ایران. کانال مذاکره رسمی گشوده شد. آماده دریافت پیشنهادات امنیتی، دفاع مشترک، تسهیم سود بازرگانی و معاهدات صلح هستیم.»\n\n✍️ جهت گفتگو، دکمه «ارسال پیام» را فشرده یا مستقیماً در کادر زیر متن خود را ارسال فرمایید:`,
        [
          ['✍️ ارسال پیام در چت مذاکره', '🤝 به توافق رسیدیم (انعقاد معاهده)'],
          ['➕ عضو کردن کشور سوم (شاهد)', '🔄 بروزرسانی چت'],
          ['📜 پیمان‌های فعال من', '❌ پایان مذاکره و خروج'],
          ['🔙 بازگشت به منوی اصلی'],
        ]
      );
      return;
    }

    if (trimmed === '✍️ ارسال پیام در چت مذاکره' || trimmed === '✍️ ارسال پیام بعدی') {
      addMessage(
        trimmed,
        `💬 **ارسال پیام به ${activeNegotiation?.countryFlag || '🏛️'} ${activeNegotiation?.countryName || 'هیئت دیپلماتیک'}**\n\nمتن پیشنهاد یا پیام محرمانه خود را در کادر زیر بنویسید و ارسال کنید:\n(طرف مقابل فوراً پیام شما را ارزیابی و پاسخ رسمی ارسال خواهد کرد)`,
        [
          ['🤝 به توافق رسیدیم (انعقاد معاهده)', '🔄 بروزرسانی چت'],
          ['🔙 بازگشت به اتاق مذاکره'],
        ]
      );
      return;
    }

    if (trimmed === '🤝 به توافق رسیدیم (انعقاد معاهده)' || trimmed === '🤝 به توافق رسیدیم') {
      setCurrentScreen('treaty_list');
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : 'کشور مقابل';
      addMessage(
        trimmed,
        `📜 **انعقاد پیمان رسمی بین‌المللی با ${partner}**\n\nپیمان مورد نظر خود را جهت ثبت نهایی برگزینید:\n\n۱. 🤝 **پیمان نظامی**: افزودن ۳۰٪ توان دفاعی در صورت اعلان جنگ\n۲. 💼 **رفیقای تجاری**: ۱۵٪ تسهیم سود فروش بازرگانی طرفین\n۳. 🕊️ **پیمان صلح**: پایان منازعه و آتش‌بس رسمی\n۴. 🤫 **پیمان اعتماد**: مشاهده آنی اطلاعات تسلیحاتی با ضامن سازمان ملل\n۵. 👥 **برادران تنی**: اعمال همزمان تمامی پیمان‌های فوق`,
        [
          ['🤝 انعقاد پیمان نظامی (دفاع ۳۰٪)', '💼 انعقاد رفیقای تجاری (۱۵٪ سود)'],
          ['🕊️ انعقاد پیمان صلح و آتش‌بس', '🤫 انعقاد پیمان اعتماد با شاهد'],
          ['👥 انعقاد برادران تنی (همه پیمان‌ها)', '🔙 بازگشت به اتاق مذاکره'],
        ]
      );
      return;
    }

    if (trimmed.startsWith('🤝 انعقاد پیمان نظامی') || trimmed === '📜 امضای پیمان اتحاد نظامی') {
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : '🇷🇺 فدراسیون روسیه';
      const treatyTitle = `🤝 پیمان اتحاد نظامی با ${partner}`;
      if (!signedTreaties.includes(treatyTitle)) {
        setSignedTreaties((prev) => [...prev, treatyTitle]);
      }
      setSatisfaction((s) => Math.min(100, s + 5));
      addMessage(
        trimmed,
        `📜 **اعلان رسمی معاهده بین‌المللی!**\n\n✅ **پیمان نظامی بین‌المللی** میان ایران و ${partner} با موفقیت به امضا رسید!\n\n🛡️ **اثر فعال:** در صورت هرگونه حمله یا اعلان جنگ، ۳۰٪ از توان نظامی ${partner} به صورت خودکار به پدافند و دفاع کشور شما اضافه خواهد شد.\n📢 خبر امضای پیمان با عکس رسمی در کانال اعلانات منتشر گردید (+۵٪ رضایت مردم).`,
        [
          ['📜 مشاهده پیمان‌های فعال من', '🕊️ آغاز مذاکره با کشوری دیگر'],
          ['🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed.startsWith('💼 انعقاد رفیقای تجاری')) {
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : '🇩🇪 آلمان';
      const treatyTitle = `💼 رفیقای تجاری با ${partner} (۱۵٪ سود)`;
      if (!signedTreaties.includes(treatyTitle)) {
        setSignedTreaties((prev) => [...prev, treatyTitle]);
      }
      setTreasury((t) => t + 50_000_000);
      addMessage(
        trimmed,
        `💼 **انعقاد موفق پیمان رفیقای تجاری!**\n\nتوافق بازرگانی میان ایران و ${partner} برقرار شد.\n۱۵٪ از سود حاصل از تمام فروش‌ها و صادرات طرفین تسهیم می‌گردد.\n💰 پاداش امضای قرارداد: ۵۰,۰۰۰,۰۰۰ ریال به خزانه شما واریز شد.\n⚠️ *نکته قوانین:* در صورت عدم پرداخت سهم تجاری، طرف مقابل حق اعلام خیانت و ابطال پیمان را دارد.`,
        [
          ['📜 مشاهده پیمان‌های فعال من', '🤝 تجارت و تنگه‌ها'],
          ['🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed.startsWith('🕊️ انعقاد پیمان صلح')) {
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : 'کشور مقابل';
      setSatisfaction((s) => Math.min(100, s + 8));
      addMessage(
        trimmed,
        `🕊️ **انعقاد پیمان صلح پایدار با ${partner}**\n\nآتش‌بس فوری اعلام شد و کلیه عملیات‌های تهاجمی متوقف گردید.\nسازمان ملل متحد این توافق صلح را ثبت و در مجمع عمومی تایید نمود.\nمردم از برقراری صلح شادمانند (+۸٪ رضایت عمومی).`,
        [
          ['📜 مشاهده پیمان‌های فعال من', '🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed.startsWith('🤫 انعقاد پیمان اعتماد')) {
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : 'کشور مقابل';
      addMessage(
        trimmed,
        `🤫 **پیمان اعتماد با نظارت شاهد سازمان ملل امضا شد!**\n\nشاهد قرارداد: 🇨🇭 سوئیس (ضامن رسمی ملل)\n👁️ **دسترسی فعال:** از این پس از دکمه «اعتماد» در امپراطوری می‌توانید به صورت بلادرنگ تمام لیست تجهیزات نظامی، موجودی خزانه‌ها و انبارهای ${partner} را مشاهده فرمایید.`,
        [
          ['📜 مشاهده پیمان‌های فعال من', '🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed.startsWith('👥 انعقاد برادران تنی')) {
      const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : 'کشور متحد';
      setTreasury((t) => t + 100_000_000);
      setSatisfaction((s) => Math.min(100, s + 10));
      addMessage(
        trimmed,
        `👥 **پیمان برادران تنی (اتحاد کامل استراتژیک) منعقد شد!**\n\nایران و ${partner} وارد عمیق‌ترین سطح اتحاد بین‌المللی شدند:\n• اتحاد دفاعی ۳۰٪ فعال شد ✅\n• رفیقای تجاری ۱۰٪ فعال شد ✅\n• پیمان اعتماد کامل تسلیحاتی فعال شد ✅\n💰 پاداش ویژه اتحاد: ۱۰۰,۰۰۰,۰۰۰ ریال به خزانه واریز شد!`,
        [
          ['📜 مشاهده پیمان‌های فعال من', '🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed === '📜 پیمان‌های من' || trimmed === '📜 مشاهده پیمان‌های فعال من') {
      const listStr = signedTreaties.length > 0
        ? signedTreaties.map((t, idx) => `${idx + 1}. ${t}`).join('\n')
        : '— هنوز پیمان فعالی منعقد نشده است —';
      addMessage(
        trimmed,
        `📜 **پیمان‌های رسمی و فعال شما:**\n\n${listStr}\n\nبرای انعقاد پیمان‌های جدید با کشورهای دیگر وارد مذاکره شوید.`,
        [
          ['🕊️ آغاز مذاکره مخفیانه با کشور دیگر', '🤝 تجارت و تنگه‌ها'],
          ['🏰 بازگشت به امپراطوری من'],
        ]
      );
      return;
    }

    if (trimmed === '⚓ تسخیر تنگه هرمز با نیروی دریایی' || trimmed === '⚓ تصاحب تنگه برینگ (نبرد ناوگان روسیه و ژاپن)') {
      if (navalPower >= 500) {
        const tollReward = 38_000_000;
        setTreasury((t) => t + tollReward);
        const lostShips = Math.floor(Math.random() * 3) + 2;
        const enemyDestroyed = Math.floor(Math.random() * 6) + 7;
        setNavalPower((p) => Math.max(300, p - lostShips * 35));
        addMessage(
          trimmed,
          `⚓ **نبرد سنگین دریایی و تصرف تنگه استراتژیک!**\n\n` +
          `🔥 **گزارش درگیری نیروهای دریایی:**\n` +
          `ناوگان رزمی شما با شلیک اژدر و موشک‌های ضدکشتی مواضع گشتی و دفاعی دشمن را هدف قرار دادند.\n` +
          `💥 **تلفات ناوگان دشمن:** ${enemyDestroyed} فروند ناوشکن و ناوچه موشک‌انداز دشمن در عمق آب‌های تنگه غرق و منهدم شدند!\n` +
          `⚓ **خسارات ناوگان خودی:** ${lostShips} فروند شناور در جریان تبادل آتش سنگین آسیب دید یا غرق شد.\n\n` +
          `🏆 **نتیجه نبرد:** پس از ساعت‌ها درگیری سهمگین، تنگه تحت حاکمیت کامل شما درآمد.\n` +
          `💰 عوارض وصول‌شده: ${tollReward.toLocaleString()} ریال (۱.۵٪ درآمد غیرمالیاتی حوزه ترانزیت).\n` +
          `📢 خبر پیروزی دریایی و تسخیر تنگه با عکس رسمی در کانال اعلانات منتشر شد.`,
          [
            ['⚓ بررسی وضعیت سایر تنگه‌ها', '🚫 اعمال انسداد بر کشور متخاصم (-۱۰٪ درآمد)'],
            ['🤝 تجارت و تنگه‌ها', '🏰 بازگشت به امپراطوری من'],
          ],
          true
        );
      } else {
        addMessage(
          trimmed,
          `❌ **قدرت دریایی ناکافی!**\nجهت تسخیر تنگه حداقل به ۵۰۰ توان دریایی نیاز است (توان فعلی شما: ${navalPower}). از بخش ارتش ناوشکن، زیردریایی و ناو هواپیمابر بسازید.`,
          [
            ['🪖 ساخت تجهیزات دریایی', '🤝 تجارت و تنگه‌ها'],
          ]
        );
      }
      return;
    }

    if (trimmed === '🚀 حمله موشکی بالستیک به پایگاه دشمن') {
      const missileCount = 20;
      const intercepted = 14;
      const hit = missileCount - intercepted;
      const damageMoney = hit * 4_500_000;
      setTreasury((t) => t + damageMoney);
      addMessage(
        trimmed,
        `🚀 **شلیک رگبار موشک‌های بالستیک دوربرد!**\n\n` +
        `تعداد موشک‌های پرتاب‌شده: ${missileCount} فروند موشک هایپرسونیک و هایمارس\n\n` +
        `🛡️ **عملکرد پدافند هوایی دشمن (سامانه‌های پاتریوت و اس ۴۰۰):**\n` +
        `• ${intercepted} فروند موشک توسط پدافند هوایی متخاصم در آسمان رهگیری و منهدم شد (دفاع موثر ۷۰٪)!\n` +
        `• ${hit} فروند موشک با عبور از سپر دفاعی مستقیماً به مراکز فرماندهی و زاغه مهمات دشمن اصابت کرد! 💥\n\n` +
        `🔥 **تخریب حاصله:**\n` +
        `• انهدام ۳ دستگاه تانک سنگین و ۲ سامانه راداری دشمن\n` +
        `• تخریب زیرساخت‌های نظامی و کاهش ۴٪ رضایت ملی دشمن\n` +
        `• غارت و خسارت وارده به خزانه دشمن: ${damageMoney.toLocaleString()} ریال`,
        [
          ['🛡️ بررسی وضعیت پدافند خودی', '⚔️ حمله هوایی ترکیبی'],
          ['⚔️ اتاق جنگ', '🏰 بازگشت به امپراطوری من'],
        ],
        true
      );
      return;
    }

    if (trimmed === '🛡️ سامانه پدافند موشکی' || trimmed === '🛡️ بررسی وضعیت پدافند خودی') {
      addMessage(
        trimmed,
        `🛡️ **شبکه یکپارچه پدافند هوایی و ضد موشکی**\n\n` +
        `سامانه‌های پدافندی مستقر:\n` +
        `• ۲ گردان سامانه برد بلند اس ۴۰۰ پیروزی (سپر ضدبالستیک تا ارتفاع ۳۰ کیلومتر)\n` +
        `• ۳ آتشبار پاتریوت PAC-3 (رهگیری موشک‌های کروز و پهپادها)\n` +
        `• ۵ سامانه متحرک تور ام۱ (دفاع نقطه از مراکز حساس و نیروگاه‌ها)\n\n` +
        `📡 نرخ رهگیری موشک‌های دشمن در صورت حمله هوایی: **۷۵٪ تا ۸۵٪** (کاهش چشمگیر خسارات تهاجم)`,
        [
          ['🚀 حمله موشکی بالستیک به پایگاه دشمن', '📢 اعلان جنگ رسمی'],
          ['🪖 ارتقای تسلیحات ارتش', '⚔️ اتاق جنگ'],
        ]
      );
      return;
    }

    if (trimmed === '📢 اعلان جنگ رسمی') {
      addMessage(
        trimmed,
        `📢 **اعلان جنگ رسمی علیه کشور متخاصم**\n\n` +
        `کشور هدف را انتخاب فرمایید:\n` +
        `۱. با مجوز سازمان ملل (رأی‌گیری عمومی در مجمع)\n` +
        `۲. بدون مجوز (آغاز فوری عملیات تهاجمی هوایی، زمینی، دریایی و فضایی)`,
        [
          ['🇯🇵 اعلان جنگ به ژاپن (نبرد بر سر تنگه برینگ)', '🇺🇸 اعلان جنگ به آمریکا'],
          ['🇨🇳 اعلان جنگ به چین', '🔙 بازگشت به اتاق جنگ'],
        ]
      );
      return;
    }

    if (trimmed.startsWith('🇯🇵 اعلان جنگ به ژاپن')) {
      addMessage(
        trimmed,
        `⚔️ **اعلان جنگ علیه ژاپن 🇯🇵 ثبت گردید!**\n\nناوگان دریایی و یگان‌های موشکی در وضعیت آماده‌باش قرمز قرار گرفتند. شما می‌توانید مستقیماً به ناوگان ژاپن در تنگه حمله کرده یا مواضع آنها را موشک‌باران کنید.`,
        [
          ['⚓ تصاحب تنگه برینگ (نبرد ناوگان روسیه و ژاپن)', '🚀 حمله موشکی بالستیک به پایگاه دشمن'],
          ['💻 عملیات سایبری به بانک دشمن', '⚔️ اتاق جنگ'],
        ],
        true
      );
      return;
    }

    if (trimmed === '🔄 تبادل کالا و انرژی پایاپای') {
      setTreasury((t) => t + 30_000_000);
      setOilBarrels((b) => Math.max(0, b - 1000));
      addMessage(
        trimmed,
        `🔄 **معاوضه مستقیم کالا و انرژی انجام شد!**\n\n۱,۰۰۰ بشکه نفت خام در ازای ۳۰,۰۰۰,۰۰۰ ریال وجه نقد و مصالح ساختمانی با کشور همسایه مبادله شد.\nاین معامله مستقیم بوده و محرمانه باقی می‌ماند.`,
        [
          ['🤝 تجارت و تنگه‌ها', '🏰 بازگشت به امپراطوری من'],
        ]
      );
      return;
    }

    // 2. Default screen router
    switch (trimmed) {
      case '🏰 امپراطوری من':
        setCurrentScreen('empire');
        addMessage(
          trimmed,
          `🏰 **امپراطوری جمهوری اسلامی ایران**\nرهبر معظم و عالی‌مقام:\n\n👥 جمعیت: ۸۵,۰۰۰,۰۰۰ نفر\n⚡ شبکه توزیع برق: ۳,۲۰۰ مگاوات (پایدار)\n💧 ذخایر آب شرب: ۶۴٪ مخازن سدها\n🔥 گاز شهری: پایدار و پرفشار\n\nبخش مورد نظر خود را جهت توسعه انتخاب کنید:`,
          [
            ['👥 مردم و خدمات', '🛢️ صنعت نفت و گاز'],
            ['🏗️ پروژه‌های ملی', '🪙 تبدیل سکه شاهی به بودجه'],
            ['🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '⚔️ اتاق جنگ':
        setCurrentScreen('war');
        addMessage(
          trimmed,
          `⚔️ **اتاق عملیات و ستاد کل نیروهای مسلح**\n\nقدرت نظامی کل: ۱,۸۵۰ واحد\n• پدافند هوایی و پهپادها: ۷۴۰\n• زرهی و توپخانه زمینی: ۴۳۰\n• ناوگان دریایی: ${navalPower}\n\nعملیات مد نظر خود را انتخاب نمایید:`,
          [
            ['📢 اعلان جنگ رسمی', '💻 عملیات سایبری به بانک دشمن'],
            ['🛡️ سامانه پدافند موشکی', '🪖 ارتقای تسلیحات ارتش'],
            ['🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '💻 عملیات سایبری به بانک دشمن': {
        const loot = 25_000_000;
        setTreasury((t) => t + loot);
        addMessage(
          trimmed,
          `💻 **پیروزی سایبری درخشان!**\nتیم هک ارتش سایبری شما فایروال‌های هدف را نفوذ کرد و مبلغ ${loot.toLocaleString()} ریال به حساب مخفی خزانه شما منتقل شد!`
        );
        break;
      }

      case '🤝 تجارت و تنگه‌ها':
        setCurrentScreen('trade');
        addMessage(
          trimmed,
          `🤝 **دیپلماسی بین‌المللی و کنترل تنگه‌های راهبردی**\n\n۸ تنگه استراتژیک جهان:\n⚓ تنگه هرمز | 🚢 کانال سوئز | 🌊 تنگه مالاکا | ⚓ جبل‌الطارق\n🌊 باب‌المندب | ⚓ بسفر و داردانل | 🚢 کانال پاناما | ❄️ تنگه برینگ\n\nپیمان‌های ۵گانه:\n۱. اتحاد دفاعی ۳۰٪ | ۲. رفیقای تجاری با امکان خیانت\n۳. صلح پایدار | ۴. پیمان اعتماد با شاهد ملل | ۵. برادران تنی`,
          [
            ['🕊️ آغاز مذاکره مخفیانه با کشور دیگر', '⚓ تسخیر تنگه هرمز با نیروی دریایی'],
            ['📜 امضای پیمان اتحاد نظامی', '🔄 تبادل کالا و انرژی پایاپای'],
            ['📜 مشاهده پیمان‌های فعال من', '🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🪙 سکه شاهی':
        setCurrentScreen('royal_coins');
        addMessage(
          trimmed,
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
          trimmed,
          `🎯 **ماموریت‌های روزانه (ساعت ۰۰:۰۰ ریست می‌شود)**\n\n۱. احداث یک پروژه زیربنایی: 🪙 ۵ سکه شاهی (انجام نشده ❌)\n۲. مانور مشترک یا آموزش ۵۰ سرباز: 💰 ۱۰ میلیون ریال (انجام شد ✅)\n۳. فروش حداقل ۳۰۰۰ بشکه نفت: 🪙 ۱۰ سکه شاهی (انجام شد ✅)\n۴. رأی در مجمع عمومی سازمان ملل: 💰 ۵ میلیون ریال (آماده دریافت 🎁)`,
          [
            ['🎁 دریافت پاداش ماموریت‌های تکمیل‌شده', '🔙 بازگشت به منوی اصلی'],
          ]
        );
        break;

      case '🇺🇳 سازمان ملل':
        setCurrentScreen('un');
        addMessage(
          trimmed,
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
        // Handle natural language text inputs
        if (currentScreen === 'neg_room' || activeNegotiation) {
          handleNegotiationChatText(trimmed);
          return;
        }

        setCurrentScreen('home');
        addMessage(
          trimmed,
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

  // Handle custom diplomatic chat text
  const handleNegotiationChatText = (text: string) => {
    const partner = activeNegotiation ? `${activeNegotiation.countryFlag} ${activeNegotiation.countryName}` : 'هیئت دیپلماتیک';
    const cname = activeNegotiation?.countryName || 'کشور مقابل';
    const time = new Date().toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });

    let reply = `پیام شما توسط وزارت امور خارجه ${cname} بررسی شد. ما از گسترش روابط سازنده استقبال می‌کنیم. جهت نهایی‌سازی قرارداد دکمه «🤝 به توافق رسیدیم» را بزنید.`;
    const lower = text.toLowerCase();

    if (lower.includes('صلح') || lower.includes('آتش') || lower.includes('جنگ')) {
      reply = `مقامات ارشد ${cname} از پیشنهاد صلح و توقف تخاصم استقبال کردند. آماده‌ایم پیمان صلح رسمی را بلافاصله به امضا برسانیم.`;
    } else if (lower.includes('نظامی') || lower.includes('دفاع') || lower.includes('کمک')) {
      reply = `ستاد مشترک نیروهای مسلح ${cname} موافقت خود را با بندهای اتحاد دفاعی ۳۰٪ اعلام می‌دارد. آماده امضای پیمان نظامی هستیم.`;
    } else if (lower.includes('تجارت') || lower.includes('پول') || lower.includes('سود') || lower.includes('نفت') || lower.includes('گاز')) {
      reply = `وزارت بازرگانی ${cname} آماده تسهیم سود تجاری و انعقاد پیمان رفیقای تجاری (۱۵٪ سود) می‌باشد.`;
    }

    addMessage(
      `👤 شما: «${text}»`,
      `🏛️ **پاسخ سفیر ${cname}:**\n\n«${reply}»`,
      [
        ['✍️ ارسال پیام بعدی', '🤝 به توافق رسیدیم (انعقاد معاهده)'],
        ['📜 مشاهده پیمان‌های من', '🔙 بازگشت به اتاق مذاکره'],
        ['🏰 بازگشت به امپراطوری من'],
      ]
    );
  };

  // Admin Bot actions
  const handleAdminAction = (btn: string) => {
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
        reply = `📣 **ارسال برودکست به تمام کاربران**\n\nاین پیام از طریق توکن ربات اصلی بازی به تمام بازیکنان ارسال خواهد شد. متن پیام را آماده فرمایید.`;
        adminBtns = [['📝 نوشتن پیام اعلان عمومی', '🔙 منوی مدیریت']];
        break;

      case '🗄️ مرورگر دیتابیس خام':
        reply = `🗄️ **مرور مستقیم جداول SQLite**\n\nجداول اصلی:\n• negotiations (مذاکرات محرمانه زنده)\n• negotiation_msgs (چت مذاکره)\n• treaties (۵ پیمان استراتژیک)\n• users (بازیکنان فعال)`;
        adminBtns = [['📊 مشاهده وضعیت جداول', '🔙 منوی مدیریت']];
        break;

      default:
        reply = `🛡️ **پنل مدیریت کل بازی جنگ جهانی (سوپرادمین)**\n\nشناسه شما: SuperAdmin ✅\nوضعیت سرور: 🟢 آنلاین و متصل به دیتابیس\nمذاکرات و چت زنده: فعال بدون قطعی`;
        adminBtns = [
          ['👥 مدیریت کاربران', '🪙 اقتصاد و فیش‌ها'],
          ['🪖 تسلیحات و کشورها', '📣 پیام همگانی'],
          ['🗄️ مرورگر دیتابیس خام', '⚙️ تنظیمات و کانال‌ها'],
        ];
        break;
    }

    addMessage(btn, reply, adminBtns);
  };

  const handleInputSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMsg.trim()) return;
    const text = inputMsg.trim();
    setInputMsg('');
    if (activeBot === 'game') {
      handleAction(text);
    } else {
      handleAdminAction(text);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn" dir="rtl">
      {/* Bot Switcher Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-xl">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-semibold">
            <Bot className="w-3.5 h-3.5 text-blue-400" />
            شبیه‌ساز زنده تلگرام (Telegram In-Browser Emulator)
          </div>
          <h2 className="text-xl font-black text-white">تست تعاملی مذاکرات، پیام‌ها و پیمان‌های ۵گانه</h2>
          <p className="text-xs text-slate-400">
            تست مستقیم چت محرمانه مذاکره با کشورها، پاسخ هوشمند دیپلماتیک، انعقاد معاهدات و تسخیر تنگه‌ها
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
            <span>ربات اصلی بازی</span>
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
            <span>ربات ادمین</span>
          </button>
        </div>
      </div>

      {/* Main Telegram Phone Mockup */}
      <div className="max-w-2xl mx-auto bg-slate-950 border-2 border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col h-[700px]">
        {/* Telegram Header */}
        <div className="bg-slate-900 border-b border-slate-800 px-5 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm ${
                activeBot === 'game' ? 'bg-amber-600 shadow-md shadow-amber-600/30' : 'bg-blue-600 shadow-md shadow-blue-600/30'
              }`}
            >
              {activeBot === 'game' ? '🌍' : '🛡️'}
            </div>
            <div>
              <h3 className="font-bold text-sm text-white flex items-center gap-1.5">
                {activeBot === 'game' ? 'بازی جنگ جهانی (World War)' : 'کنترل پنل ادمین جنگ جهانی'}
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />
              </h3>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                ربات آنلاین | متصل به SQLite و چت زنده
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-lg bg-slate-800/80 text-amber-300 font-mono text-[11px] border border-slate-700">
              💰 {treasury.toLocaleString()} ریال
            </span>
          </div>
        </div>

        {/* Telegram Messages Viewport */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-radial from-slate-900/60 to-slate-950">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'} space-y-1.5`}
            >
              {/* Message Bubble */}
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-md text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-amber-500 text-slate-950 font-medium rounded-bl-sm'
                    : m.isOfficial
                    ? 'bg-gradient-to-r from-emerald-950/80 to-slate-900 border border-emerald-500/40 text-slate-100 rounded-br-sm'
                    : 'bg-slate-900 border border-slate-800 text-slate-100 rounded-br-sm'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>
                <div
                  className={`text-[9px] mt-1 text-left ${
                    m.sender === 'user' ? 'text-slate-900/70' : 'text-slate-500'
                  }`}
                >
                  {m.time}
                </div>
              </div>

              {/* Inline Buttons (Telegram style) */}
              {m.buttons && m.buttons.length > 0 && (
                <div className="w-full max-w-[85%] space-y-1.5 pt-1">
                  {m.buttons.map((row, rIdx) => (
                    <div key={rIdx} className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}>
                      {row.map((btn, bIdx) => (
                        <button
                          key={bIdx}
                          onClick={() => (activeBot === 'game' ? handleAction(btn) : handleAdminAction(btn))}
                          className="w-full bg-slate-900 hover:bg-slate-850 active:scale-95 text-slate-200 hover:text-white border border-slate-800 hover:border-amber-500/50 py-2.5 px-3 rounded-xl text-xs font-semibold transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer text-center"
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
          <div ref={messagesEndRef} />
        </div>

        {/* Telegram Input Bar */}
        <form onSubmit={handleInputSubmit} className="bg-slate-900 border-t border-slate-800 p-3 shrink-0 flex items-center gap-2">
          <input
            type="text"
            value={inputMsg}
            onChange={(e) => setInputMsg(e.target.value)}
            placeholder={
              currentScreen === 'neg_room'
                ? 'متن پیام یا شرایط معاهده را بنویسید و ارسال کنید...'
                : 'دستوری مثل /start بنویسید یا روی دکمه‌های بالا بزنید...'
            }
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
          <button
            type="submit"
            className="p-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all cursor-pointer flex items-center justify-center shrink-0"
            title="ارسال پیام"
          >
            <Send className="w-4 h-4 rotate-180" />
          </button>
        </form>
      </div>
    </div>
  );
};
