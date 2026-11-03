import React, { useState } from 'react';
import { Swords, Shield, Plane, ShieldAlert, Cpu, Sparkles, Crosshair, Zap, DollarSign, Award } from 'lucide-react';
import { EQUIPMENT_DATA, Equipment, COUNTRIES_DATA } from '../data/gameData';

export const MilitaryArsenal: React.FC = () => {
  const [activeCategory, setActiveCategory] = useState<string>('all');

  // Battle Simulator States
  const [attackerCountry, setAttackerCountry] = useState<string>('ایران 🇮🇷');
  const [defenderCountry, setDefenderCountry] = useState<string>('آمریکا 🇺🇸');
  const [attackerAtk, setAttackerAtk] = useState<number>(3500);
  const [attackerCyber, setAttackerCyber] = useState<number>(120000);
  const [defenderDef, setDefenderDef] = useState<number>(3200);
  const [defenderCyber, setDefenderCyber] = useState<number>(80000);
  const [battleResult, setBattleResult] = useState<any>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  const categories = [
    { key: 'all', label: 'همه تسلیحات (۳۹ جنگ‌افزار)', icon: Swords },
    { key: 'air', label: 'هوایی و پهپادی ✈️', icon: Plane },
    { key: 'land', label: 'زرهی و توپخانه 🪖', icon: Shield },
    { key: 'sea', label: 'دریایی و زیرسطحی ⚓', icon: Crosshair },
    { key: 'cyber', label: 'سایبری و اخلال 💻', icon: Cpu },
    { key: 'space', label: 'سلاح‌های مداری 🛰️', icon: Sparkles },
  ];

  const filteredEquipment = EQUIPMENT_DATA.filter(
    (e) => activeCategory === 'all' || e.category === activeCategory
  );

  const handleSimulateBattle = async () => {
    setIsSimulating(true);
    setBattleResult(null);
    try {
      const res = await fetch('/api/simulate/battle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attacker: { attackPower: attackerAtk, cyberPower: attackerCyber },
          defender: { defensePower: defenderDef, cyberPower: defenderCyber, treasury: 60000000 },
        }),
      });
      const data = await res.json();
      setBattleResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-semibold">
            <Swords className="w-3.5 h-3.5 text-rose-400" />
            آرسنال تسلیحات و شبیه‌ساز جنگ هوشمند
          </div>
          <h2 className="text-xl font-black text-white">۳۹ جنگ‌افزار دسته‌بندی‌شده شامل پهپاد، جنگنده، زرهی و فضایی</h2>
          <p className="text-xs text-slate-400">
            دسته‌بندی سلسله‌مراتبی، تجهیزات پایه ارزان و ادوات پیشرفته استراتژیک به همراه شبیه‌ساز نبرد
          </p>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeCategory === cat.key;
            return (
              <button
                key={cat.key}
                onClick={() => setActiveCategory(cat.key)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-rose-500 text-slate-950 font-bold shadow-md shadow-rose-500/20'
                    : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Equipment Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredEquipment.map((eq) => (
          <div
            key={eq.id}
            className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 space-y-3 transition-all hover:shadow-xl relative overflow-hidden"
          >
            {eq.priceCoins > 0 && (
              <div className="absolute top-0 left-0 bg-amber-500 text-slate-950 font-bold text-[10px] px-2.5 py-0.5 rounded-br-lg shadow-sm">
                سکه شاهی: {eq.priceCoins} 🪙
              </div>
            )}

            <div className="flex items-center gap-3">
              <span className="text-3xl p-2.5 rounded-xl bg-slate-950 border border-slate-800">{eq.emoji}</span>
              <div>
                <h3 className="font-bold text-sm text-white">{eq.name}</h3>
                <span className="text-[11px] text-slate-400 capitalize">
                  شاخه {eq.category === 'air' ? 'نیروی هوایی' : eq.category === 'land' ? 'نیروی زمینی' : eq.category === 'sea' ? 'نیروی دریایی' : eq.category === 'cyber' ? 'جنگ سایبری' : 'فناوری فضایی'}
                </span>
              </div>
            </div>

            {/* Combat Specs */}
            <div className="grid grid-cols-3 gap-2 text-xs pt-1">
              <div className="bg-slate-950/80 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">قدرت حمله:</span>
                <span className="font-bold text-rose-400">{eq.atk.toLocaleString()}</span>
              </div>
              <div className="bg-slate-950/80 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">قدرت دفاع:</span>
                <span className="font-bold text-blue-400">{eq.def.toLocaleString()}</span>
              </div>
              <div className="bg-slate-950/80 p-2 rounded-xl border border-slate-850">
                <span className="text-[10px] text-slate-500 block">سایبری/سرعت:</span>
                <span className="font-bold text-emerald-400">
                  {eq.cyber > 0 ? `${(eq.cyber / 1000).toFixed(0)}k` : `سرعت ${eq.speed}`}
                </span>
              </div>
            </div>

            {/* Price & Requirements */}
            <div className="text-[11px] space-y-1 pt-2 border-t border-slate-800/80">
              <div className="flex justify-between text-slate-400">
                <span>قیمت ساخت:</span>
                <span className="font-mono text-slate-200">
                  {eq.priceMoney > 0 ? `${(eq.priceMoney / 1_000_000).toLocaleString()} میلیون ریال` : `${eq.priceCoins} سکه شاهی`}
                </span>
              </div>
              {eq.requiresText && (
                <div className="text-amber-400 font-medium text-[10px] bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20">
                  ⚠️ پیش‌نیاز: {eq.requiresText}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Interactive Combat Battle Simulator */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
        <div className="flex items-center gap-2.5 border-b border-slate-800 pb-4">
          <Crosshair className="w-5 h-5 text-rose-400" />
          <div>
            <h3 className="text-base font-bold text-white">شبیه‌ساز هوشمند نبرد اتاق جنگ (War Room Combat Engine)</h3>
            <p className="text-xs text-slate-400">
              بر اساس دقیق‌ترین فرمول موجود در core/economy.py و gamebot/handlers/war.py با احتساب شانس و برتری سایبری
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Attacker Setup */}
          <div className="bg-slate-950 p-5 rounded-2xl border border-rose-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-rose-300 flex items-center gap-2">
                <Zap className="w-4 h-4 text-rose-400" />
                کشور مهاجم (Attacking Force)
              </span>
              <select
                value={attackerCountry}
                onChange={(e) => setAttackerCountry(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-xs text-white rounded-lg px-2.5 py-1"
              >
                {COUNTRIES_DATA.map((c) => (
                  <option key={c.id} value={`${c.name} ${c.flag}`}>
                    {c.flag} {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>قدرت حمله ترکیبی (هوا + زمین + دریا):</span>
                  <span className="font-bold text-rose-400 font-mono">{attackerAtk.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="500"
                  max="15000"
                  step="250"
                  value={attackerAtk}
                  onChange={(e) => setAttackerAtk(Number(e.target.value))}
                  className="w-full accent-rose-500 cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>قدرت نفوذ سایبری (اختلال پدافند):</span>
                  <span className="font-bold text-emerald-400 font-mono">{attackerCyber.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="10000"
                  max="300000"
                  step="10000"
                  value={attackerCyber}
                  onChange={(e) => setAttackerCyber(Number(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
              </div>
            </div>
          </div>

          {/* Defender Setup */}
          <div className="bg-slate-950 p-5 rounded-2xl border border-blue-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-blue-300 flex items-center gap-2">
                <Shield className="w-4 h-4 text-blue-400" />
                کشور مدافع (Defending Force)
              </span>
              <select
                value={defenderCountry}
                onChange={(e) => setDefenderCountry(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-xs text-white rounded-lg px-2.5 py-1"
              >
                {COUNTRIES_DATA.map((c) => (
                  <option key={c.id} value={`${c.name} ${c.flag}`}>
                    {c.flag} {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>استحکام پدافند دفاعی (زمین + هوا + سپر):</span>
                  <span className="font-bold text-blue-400 font-mono">{defenderDef.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="500"
                  max="15000"
                  step="250"
                  value={defenderDef}
                  onChange={(e) => setDefenderDef(Number(e.target.value))}
                  className="w-full accent-blue-500 cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>سپر الکترونیک سایبری:</span>
                  <span className="font-bold text-emerald-400 font-mono">{defenderCyber.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="10000"
                  max="300000"
                  step="10000"
                  value={defenderCyber}
                  onChange={(e) => setDefenderCyber(Number(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-center">
          <button
            onClick={handleSimulateBattle}
            disabled={isSimulating}
            className="px-8 py-3 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-bold text-xs shadow-lg shadow-rose-900/40 flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
          >
            <Swords className="w-4 h-4" />
            {isSimulating ? 'در حال شبیه‌سازی محاسبات جنگ...' : `شروع نبرد بین ${attackerCountry} و ${defenderCountry}`}
          </button>
        </div>

        {/* Battle Result Output */}
        {battleResult && (
          <div
            className={`p-5 rounded-2xl border text-xs space-y-4 animate-scaleUp ${
              battleResult.isVictory
                ? 'bg-emerald-950/30 border-emerald-500/40'
                : 'bg-rose-950/30 border-rose-500/40'
            }`}
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-base font-bold">
                {battleResult.isVictory ? (
                  <span className="text-emerald-400 flex items-center gap-1.5">
                    <Award className="w-5 h-5 text-emerald-400" />
                    پیروزی قاطع برای مهاجم ({attackerCountry})!
                  </span>
                ) : (
                  <span className="text-rose-400 flex items-center gap-1.5">
                    <ShieldAlert className="w-5 h-5 text-rose-400" />
                    شکست حمله! مدافع ({defenderCountry}) پیروز شد!
                  </span>
                )}
              </div>

              <div className="text-slate-400 text-xs">
                ضریب شانس رندوم: <span className="font-mono text-white">{battleResult.luckMultiplier}x</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-500 block">نسبت برتری رزمی:</span>
                <span className="font-bold text-white text-sm font-mono">{battleResult.combatRatio}٪</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-500 block">تلفات نیروهای مهاجم:</span>
                <span className="font-bold text-rose-400 text-sm font-mono">
                  {battleResult.attackerLossPercent}٪ تلفات
                </span>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-500 block">غنیمت جنگی تسخیر شده:</span>
                <span className="font-bold text-amber-300 text-sm font-mono">
                  {battleResult.spoilsOfWarMoney.toLocaleString()} ریال
                </span>
              </div>
            </div>

            <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 space-y-1 text-slate-300 font-mono text-[11px]">
              {battleResult.log.map((line: string, i: number) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-amber-400">›</span>
                  <span>{line}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
