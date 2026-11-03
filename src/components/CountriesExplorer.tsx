import React, { useState } from 'react';
import { Globe, Search, Filter, Fuel, Coins, Users, Compass, Waves, CheckCircle2, Star } from 'lucide-react';
import { COUNTRIES_DATA, Country } from '../data/gameData';

export const CountriesExplorer: React.FC = () => {
  const [search, setSearch] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'free' | 'special'>('all');
  const [seaFilter, setSeaFilter] = useState<'all' | 'sea' | 'landlocked'>('all');
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);

  const regions = ['all', 'خاورمیانه', 'آسیا', 'اروپا', 'آمریکای شمالی', 'آمریکای جنوبی', 'آفریقا', 'اقیانوسیه'];

  const filteredCountries = COUNTRIES_DATA.filter((c) => {
    const matchSearch = c.name.includes(search) || c.currency.includes(search) || c.region.includes(search);
    const matchRegion = selectedRegion === 'all' || c.region === selectedRegion;
    const matchType = typeFilter === 'all' || (typeFilter === 'free' ? !c.isSpecial : c.isSpecial);
    const matchSea = seaFilter === 'all' || (seaFilter === 'sea' ? c.hasSea : !c.hasSea);
    return matchSearch && matchRegion && matchType && matchSea;
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-semibold">
            <Globe className="w-3.5 h-3.5 text-emerald-400" />
            اطلس ژئوپلیتیک ۴۵ کشور واقعی (World Map & Countries Data)
          </div>
          <h2 className="text-xl font-black text-white">کشورهای جهان، ذخایر عظیم نفت، ارزهای ملی و دسترسی دریایی</h2>
          <p className="text-xs text-slate-400">
            شامل ۱۵ کشور رایگان برای شروع بازی و ۳۰ کشور ویژه قدرتمند با قابلیت ارتقاء و تسخیر در نسخه ۲ بازی
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-slate-950 px-3.5 py-2 rounded-xl border border-slate-800 text-xs text-slate-300">
            <span className="text-slate-500 ml-1">تعداد نمایش:</span>
            <span className="font-bold text-amber-400 font-mono">{filteredCountries.length}</span> از ۴۵ کشور
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="relative md:col-span-1">
            <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3" />
            <input
              type="text"
              placeholder="جستجوی نام کشور، ارز یا منطقه..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl pr-10 pl-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
            />
          </div>

          {/* Region Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto md:col-span-2 scrollbar-none py-0.5">
            {regions.map((reg) => (
              <button
                key={reg}
                onClick={() => setSelectedRegion(reg)}
                className={`px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                  selectedRegion === reg
                    ? 'bg-amber-500 text-slate-950 font-bold'
                    : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                {reg === 'all' ? 'همه قاره‌ها' : reg}
              </button>
            ))}
          </div>

          {/* Type Switcher */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setTypeFilter('all')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${
                typeFilter === 'all' ? 'bg-slate-800 text-white' : 'text-slate-400'
              }`}
            >
              همه
            </button>
            <button
              onClick={() => setTypeFilter('free')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${
                typeFilter === 'free' ? 'bg-emerald-500/20 text-emerald-300 font-bold' : 'text-slate-400'
              }`}
            >
              رایگان
            </button>
            <button
              onClick={() => setTypeFilter('special')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${
                typeFilter === 'special' ? 'bg-amber-500/20 text-amber-300 font-bold' : 'text-slate-400'
              }`}
            >
              ویژه 🪙
            </button>
          </div>
        </div>
      </div>

      {/* Countries Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCountries.map((c) => (
          <div
            key={c.id}
            onClick={() => setSelectedCountry(c)}
            className="bg-slate-900 border border-slate-800 hover:border-amber-500/50 rounded-2xl p-5 transition-all cursor-pointer group hover:shadow-xl space-y-3 relative overflow-hidden"
          >
            {c.isSpecial && (
              <div className="absolute -top-1 -left-1 bg-gradient-to-r from-amber-500 to-rose-500 text-slate-950 font-black text-[10px] px-3 py-1 rounded-br-xl shadow-md">
                ویژه • {c.coinPrice} 🪙
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-3">
                <div className="relative w-11 h-8 rounded-lg overflow-hidden shadow-md border border-slate-700/80 bg-slate-950 flex-shrink-0 group-hover:scale-105 transition-transform">
                  <img
                    src={c.flagUrl || `https://flagcdn.com/w160/${c.isoCode || 'un'}.png`}
                    alt={`پرچم ${c.name}`}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </div>
                <div>
                  <h3 className="font-bold text-base text-white group-hover:text-amber-400 transition-colors flex items-center gap-1.5">
                    {c.name}
                    <span className="text-sm filter drop-shadow">{c.flag}</span>
                  </h3>
                  <span className="text-[11px] text-slate-400 flex items-center gap-1">
                    <Compass className="w-3 h-3 text-slate-500" />
                    {c.region}
                    <span className="text-[10px] font-mono text-slate-500 uppercase ml-1">({c.isoCode})</span>
                  </span>
                </div>
              </div>

              <div className="text-left">
                {c.hasSea ? (
                  <span className="inline-flex items-center gap-1 text-[11px] text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20">
                    <Waves className="w-3 h-3" />
                    دریایی
                  </span>
                ) : (
                  <span className="text-[11px] text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    محصور در خشکی
                  </span>
                )}
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-2 text-xs pt-2 border-t border-slate-800/80">
              <div className="bg-slate-950/70 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">جمعیت:</span>
                <span className="font-semibold text-slate-200">{(c.population / 1_000_000).toFixed(0)}M نفر</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">ارز ملی:</span>
                <span className="font-semibold text-amber-300 truncate block">{c.currency}</span>
              </div>
              <div className="bg-slate-950/70 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">شاخص نفت:</span>
                <span className="font-semibold text-emerald-400">{c.oilRichness}٪ غنی</span>
              </div>
            </div>

            {/* Oil Reserve Bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-400">
                <span className="flex items-center gap-1">
                  <Fuel className="w-3 h-3 text-amber-400" />
                  مخزن زیرزمینی:
                </span>
                <span className="font-mono text-slate-300">
                  {c.oilReserve > 0 ? `${(c.oilReserve / 1_000_000_000).toFixed(1)} میلیارد بشکه` : 'فاقد نفت'}
                </span>
              </div>
              <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-600 to-emerald-500 rounded-full"
                  style={{ width: `${Math.min(100, c.oilRichness)}%` }}
                ></div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Country Detail Modal */}
      {selectedCountry && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl p-6 max-w-lg w-full space-y-5 shadow-2xl animate-scaleUp">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-16 h-11 rounded-xl overflow-hidden shadow-lg border border-slate-700 bg-slate-950 flex-shrink-0">
                  <img
                    src={selectedCountry.flagUrl || `https://flagcdn.com/w320/${selectedCountry.isoCode || 'un'}.png`}
                    alt={`پرچم ${selectedCountry.name}`}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div>
                  <h3 className="text-xl font-black text-white flex items-center gap-2">
                    {selectedCountry.name}
                    <span className="text-sm">{selectedCountry.flag}</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    کد بین‌المللی: {selectedCountry.isoCode.toUpperCase()} | {selectedCountry.region}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedCountry(null)}
                className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex justify-between">
                <span className="text-slate-400">وضعیت کشور در بازی:</span>
                <span className="font-bold text-white">
                  {selectedCountry.isSpecial ? `ویژه (خرید با ${selectedCountry.coinPrice} سکه شاهی)` : 'رایگان در دسترس'}
                </span>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex justify-between">
                <span className="text-slate-400">واحد پول ملی:</span>
                <span className="font-bold text-amber-300">{selectedCountry.currency}</span>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex justify-between">
                <span className="text-slate-400">کل جمعیت کشور:</span>
                <span className="font-bold text-slate-200">{selectedCountry.population.toLocaleString()} نفر</span>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex justify-between">
                <span className="text-slate-400">ذخیره تخمینی نفت زیرزمینی:</span>
                <span className="font-bold text-emerald-400 font-mono">
                  {selectedCountry.oilReserve.toLocaleString()} بشکه
                </span>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex justify-between">
                <span className="text-slate-400">دسترسی به آب‌های آزاد و تنگه‌ها:</span>
                <span className="font-bold text-sky-400">
                  {selectedCountry.hasSea ? 'دارای مرز دریایی (امکان تسخیر تنگه‌ها)' : 'محصور در خشکی'}
                </span>
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => setSelectedCountry(null)}
                className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs cursor-pointer"
              >
                بستن پنجره
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
