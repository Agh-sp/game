import React, { useState } from 'react';
import { Anchor, ShieldCheck, Scroll, Waves, AlertTriangle, CheckCircle2, Eye, Skull, HeartHandshake, Ship } from 'lucide-react';
import { STRAITS_DATA, TREATIES_DATA, Strait, Treaty } from '../data/gameData';

export const StraitsAndTreaties: React.FC = () => {
  const [selectedStrait, setSelectedStrait] = useState<Strait | null>(STRAITS_DATA[0]);
  const [selectedTreaty, setSelectedTreaty] = useState<Treaty | null>(TREATIES_DATA[0]);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-xs font-semibold">
            <Anchor className="w-3.5 h-3.5 text-cyan-400" />
            شریان‌های دریایی جهان و دیپلماسی پیمان‌ها (Straits & Treaties)
          </div>
          <h2 className="text-xl font-black text-white">۸ تنگه استراتژیک بین‌المللی و ۵ پیمان دیپلماتیک با سازوکار خیانت</h2>
          <p className="text-xs text-slate-400">
            تصاحب آبراه‌ها با قدرت دریایی، اخذ عوارض ۱.۵ درصدی از تجارت جهان و پیمان‌های نظامی و تجاری
          </p>
        </div>
      </div>

      {/* 8 Straits Showcase */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Waves className="w-4 h-4 text-cyan-400" />
            ۸ تنگه و آبراه استراتژیک جهان (تسخیر و عوارض دریایی)
          </h3>
          <span className="text-xs text-slate-400">عوارض خودکار هر ۳۰ دقیقه محاسبه می‌شود</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {STRAITS_DATA.map((s) => {
            const isSelected = selectedStrait?.key === s.key;
            return (
              <div
                key={s.key}
                onClick={() => setSelectedStrait(s)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer space-y-3 ${
                  isSelected
                    ? 'bg-slate-900 border-cyan-500 shadow-lg shadow-cyan-950/50'
                    : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-2xl p-2 rounded-xl bg-slate-950 border border-slate-800">{s.emoji}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                    عوارض: {s.tollPercent}٪
                  </span>
                </div>

                <div>
                  <h4 className="font-bold text-sm text-white">{s.name}</h4>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">{s.desc}</p>
                </div>

                <div className="pt-2 border-t border-slate-800 flex justify-between text-[11px] text-slate-400">
                  <span>حداقل قدرت دریایی:</span>
                  <span className="font-bold text-cyan-300 font-mono">{s.minSeaPower} ناوگان</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Strait Detailed Rules */}
        {selectedStrait && (
          <div className="bg-slate-950 border border-cyan-500/30 rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-cyan-300 font-bold text-sm">
              <Ship className="w-4 h-4" />
              قوانین تسخیر و دریافت عوارض «{selectedStrait.name}»:
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[10px]">شرط تسخیر تنگه آزاد:</span>
                <span className="font-bold text-white mt-0.5 block">داشتن حداقل ۵۰۰ قدرت دریایی فعال</span>
              </div>
              <div className="bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[10px]">شرط تصاحب از مالک فعلی:</span>
                <span className="font-bold text-amber-300 mt-0.5 block">قدرت دریایی ۲.۵ برابر قدرت مالک</span>
              </div>
              <div className="bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[10px]">درآمد هر ۳۰ دقیقه:</span>
                <span className="font-bold text-emerald-400 mt-0.5 block">۱.۵٪ از درآمدهای غیرمالیاتی کل حوزه</span>
              </div>
              <div className="bg-slate-900 p-3 rounded-xl border border-rose-500/30">
                <span className="text-rose-400 block text-[10px] font-bold">⛔ محاصره و تحریم تنگه:</span>
                <span className="font-bold text-rose-300 mt-0.5 block">کاهش ۱۰٪ درآمد کشور هدف به ازای هر تنگه</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 5 Treaties Showcase */}
      <div className="space-y-4 pt-4 border-t border-slate-800">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Scroll className="w-4 h-4 text-amber-400" />
            ۵ پیمان بین‌المللی با اثرات استراتژیک و مکانیسم خیانت
          </h3>
          <span className="text-xs text-slate-400">ثبت با عکس رسمی در کانال اعلانات</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TREATIES_DATA.map((t) => {
            const isSelected = selectedTreaty?.id === t.id;
            return (
              <div
                key={t.id}
                onClick={() => setSelectedTreaty(t)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer space-y-3 ${
                  isSelected
                    ? 'bg-slate-900 border-amber-500 shadow-lg shadow-amber-950/50'
                    : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl p-2 rounded-xl bg-slate-950 border border-slate-800">{t.emoji}</span>
                  <div>
                    <h4 className="font-bold text-sm text-white">{t.name}</h4>
                    <span className="text-[11px] text-amber-300/80">{t.summary}</span>
                  </div>
                </div>

                <div className="text-xs space-y-2 pt-2 border-t border-slate-800/80">
                  <div>
                    <span className="text-slate-400 block text-[10px]">اثر اصلی پیمان:</span>
                    <p className="text-slate-300 leading-relaxed mt-0.5">{t.effect}</p>
                  </div>

                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-850">
                    <span className="text-rose-400 font-bold block text-[10px] flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      قواعد و ریسک خیانت:
                    </span>
                    <p className="text-slate-400 text-[11px] mt-0.5 leading-relaxed">{t.riskOrRules}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Rescue Organization (سازمان نجات) Spotlight */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-950 border border-emerald-500/30 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <HeartHandshake className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">🛟 سازمان نجات جهانی (Global Rescue Organization)</h3>
            <p className="text-xs text-slate-400">
              بخش انسان‌دوستانه امپراطوری من: امدادرسانی در حین جنگ‌ها، جذب سرمایه و اهدای ذخایر پنهان
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
            <span className="text-slate-400 font-bold block mb-1">۱. کمپین‌های جنگی فعال</span>
            <p className="text-slate-300 leading-relaxed">
              برای هر جنگ فعال یک کمپین جداگانه ایجاد می‌شود تا کشورهای بی‌طرف بتوانند با اهدای انرژی یا پول، از ملت‌های آسیب‌دیده حمایت کنند.
            </p>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
            <span className="text-slate-400 font-bold block mb-1">۲. بازکردن ذخیره مخفی ۱۰٪</span>
            <p className="text-slate-300 leading-relaxed">
              کشوری که در رأی‌گیری سازمان نجات به اکثریت آرا برسد، ۱۰٪ از ذخایر استراتژیک اورژانسی را به عنوان پاداش بلاعوض دریافت می‌نماید.
            </p>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
            <span className="text-slate-400 font-bold block mb-1">۳. اعلام عمومی در کانال با تصویر</span>
            <p className="text-slate-300 leading-relaxed">
              فروش انرژی یا مشارکت در سازمان نجات با بنر اختصاصی سوپرادمین در کانال اعلانات منتشر شده و رضایت مردم را به شدت بالا می‌برد.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
