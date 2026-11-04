export interface Country {
  id: number;
  name: string;
  flag: string;
  isoCode: string;
  flagUrl: string;
  isSpecial: boolean;
  coinPrice: number;
  population: number;
  hasSea: boolean;
  region: string;
  currency: string;
  oilReserve: number;
  oilRichness: number;
}

export interface Equipment {
  id: number;
  category: 'air' | 'land' | 'sea' | 'cyber' | 'space';
  subcategory?: string;
  name: string;
  emoji: string;
  atk: number;
  def: number;
  cyber: number;
  speed: number;
  priceMoney: number;
  priceCoins: number;
  requiresText: string;
}

export interface Strait {
  key: string;
  name: string;
  emoji: string;
  minSeaPower: number;
  tollPercent: number;
  desc: string;
}

export interface Treaty {
  id: string;
  name: string;
  emoji: string;
  summary: string;
  effect: string;
  riskOrRules: string;
}

export const COUNTRIES_DATA: Country[] = [
  { id: 1, name: "ایران", flag: "🇮🇷", isoCode: "ir", flagUrl: "https://flagcdn.com/w640/ir.png", isSpecial: false, coinPrice: 0, population: 86_000_000, hasSea: true, region: "خاورمیانه", currency: "ریال", oilReserve: 208_000_000_000, oilRichness: 65 },
  { id: 2, name: "عراق", flag: "🇮🇶", isoCode: "iq", flagUrl: "https://flagcdn.com/w640/iq.png", isSpecial: false, coinPrice: 0, population: 44_000_000, hasSea: true, region: "خاورمیانه", currency: "دینار عراق", oilReserve: 145_000_000_000, oilRichness: 55 },
  { id: 3, name: "سوریه", flag: "🇸🇾", isoCode: "sy", flagUrl: "https://flagcdn.com/w640/sy.png", isSpecial: false, coinPrice: 0, population: 23_000_000, hasSea: true, region: "خاورمیانه", currency: "لیره سوریه", oilReserve: 2_500_000_000, oilRichness: 25 },
  { id: 4, name: "افغانستان", flag: "🇦🇫", isoCode: "af", flagUrl: "https://flagcdn.com/w640/af.png", isSpecial: false, coinPrice: 0, population: 40_000_000, hasSea: false, region: "آسیا", currency: "افغانی", oilReserve: 1_800_000_000, oilRichness: 15 },
  { id: 5, name: "پاکستان", flag: "🇵🇰", isoCode: "pk", flagUrl: "https://flagcdn.com/w640/pk.png", isSpecial: false, coinPrice: 0, population: 240_000_000, hasSea: true, region: "آسیا", currency: "روپیه پاکستان", oilReserve: 1_200_000_000, oilRichness: 20 },
  { id: 6, name: "مصر", flag: "🇪🇬", isoCode: "eg", flagUrl: "https://flagcdn.com/w640/eg.png", isSpecial: false, coinPrice: 0, population: 105_000_000, hasSea: true, region: "آفریقا", currency: "پوند مصر", oilReserve: 3_600_000_000, oilRichness: 30 },
  { id: 7, name: "قزاقستان", flag: "🇰🇿", isoCode: "kz", flagUrl: "https://flagcdn.com/w640/kz.png", isSpecial: false, coinPrice: 0, population: 19_000_000, hasSea: false, region: "آسیا", currency: "تنگه", oilReserve: 30_000_000_000, oilRichness: 50 },
  { id: 8, name: "ازبکستان", flag: "🇺🇿", isoCode: "uz", flagUrl: "https://flagcdn.com/w640/uz.png", isSpecial: false, coinPrice: 0, population: 35_000_000, hasSea: false, region: "آسیا", currency: "سوم", oilReserve: 600_000_000, oilRichness: 10 },
  { id: 9, name: "ویتنام", flag: "🇻🇳", isoCode: "vn", flagUrl: "https://flagcdn.com/w640/vn.png", isSpecial: false, coinPrice: 0, population: 98_000_000, hasSea: true, region: "آسیا", currency: "دونگ", oilReserve: 4_400_000_000, oilRichness: 30 },
  { id: 10, name: "تایلند", flag: "🇹🇭", isoCode: "th", flagUrl: "https://flagcdn.com/w640/th.png", isSpecial: false, coinPrice: 0, population: 71_000_000, hasSea: true, region: "آسیا", currency: "بات", oilReserve: 500_000_000, oilRichness: 15 },
  { id: 11, name: "نیجریه", flag: "🇳🇬", isoCode: "ng", flagUrl: "https://flagcdn.com/w640/ng.png", isSpecial: false, coinPrice: 0, population: 223_000_000, hasSea: true, region: "آفریقا", currency: "نایرا", oilReserve: 37_000_000_000, oilRichness: 55 },
  { id: 12, name: "آفریقای جنوبی", flag: "🇿🇦", isoCode: "za", flagUrl: "https://flagcdn.com/w640/za.png", isSpecial: false, coinPrice: 0, population: 60_000_000, hasSea: true, region: "آفریقا", currency: "راند", oilReserve: 15_000_000_000, oilRichness: 35 },
  { id: 13, name: "آرژانتین", flag: "🇦🇷", isoCode: "ar", flagUrl: "https://flagcdn.com/w640/ar.png", isSpecial: false, coinPrice: 0, population: 46_000_000, hasSea: true, region: "آمریکای جنوبی", currency: "پزو آرژانتین", oilReserve: 2_400_000_000, oilRichness: 25 },
  { id: 14, name: "ونزوئلا", flag: "🇻🇪", isoCode: "ve", flagUrl: "https://flagcdn.com/w640/ve.png", isSpecial: false, coinPrice: 0, population: 28_000_000, hasSea: true, region: "آمریکای جنوبی", currency: "بولیوار", oilReserve: 303_000_000_000, oilRichness: 70 },
  { id: 15, name: "مراکش", flag: "🇲🇦", isoCode: "ma", flagUrl: "https://flagcdn.com/w640/ma.png", isSpecial: false, coinPrice: 0, population: 37_000_000, hasSea: true, region: "آفریقا", currency: "درهم مراکش", oilReserve: 700_000_000, oilRichness: 15 },
  { id: 16, name: "آمریکا", flag: "🇺🇸", isoCode: "us", flagUrl: "https://flagcdn.com/w640/us.png", isSpecial: true, coinPrice: 2000, population: 335_000_000, hasSea: true, region: "آمریکای شمالی", currency: "دلار", oilReserve: 68_000_000_000, oilRichness: 60 },
  { id: 17, name: "روسیه", flag: "🇷🇺", isoCode: "ru", flagUrl: "https://flagcdn.com/w640/ru.png", isSpecial: true, coinPrice: 1800, population: 144_000_000, hasSea: true, region: "آسیا", currency: "روبل", oilReserve: 108_000_000_000, oilRichness: 65 },
  { id: 18, name: "چین", flag: "🇨🇳", isoCode: "cn", flagUrl: "https://flagcdn.com/w640/cn.png", isSpecial: true, coinPrice: 1800, population: 1_412_000_000, hasSea: true, region: "آسیا", currency: "یوان", oilReserve: 26_000_000_000, oilRichness: 45 },
  { id: 19, name: "هند", flag: "🇮🇳", isoCode: "in", flagUrl: "https://flagcdn.com/w640/in.png", isSpecial: true, coinPrice: 900, population: 1_430_000_000, hasSea: true, region: "آسیا", currency: "روپیه هند", oilReserve: 4_600_000_000, oilRichness: 30 },
  { id: 20, name: "انگلیس", flag: "🇬🇧", isoCode: "gb", flagUrl: "https://flagcdn.com/w640/gb.png", isSpecial: true, coinPrice: 900, population: 67_000_000, hasSea: true, region: "اروپا", currency: "پوند", oilReserve: 2_600_000_000, oilRichness: 30 },
  { id: 21, name: "ژاپن", flag: "🇯🇵", isoCode: "jp", flagUrl: "https://flagcdn.com/w640/jp.png", isSpecial: true, coinPrice: 850, population: 124_000_000, hasSea: true, region: "آسیا", currency: "ین", oilReserve: 400_000_000, oilRichness: 10 },
  { id: 22, name: "آلمان", flag: "🇩🇪", isoCode: "de", flagUrl: "https://flagcdn.com/w640/de.png", isSpecial: true, coinPrice: 800, population: 84_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 130_000_000, oilRichness: 8 },
  { id: 23, name: "فرانسه", flag: "🇫🇷", isoCode: "fr", flagUrl: "https://flagcdn.com/w640/fr.png", isSpecial: true, coinPrice: 800, population: 65_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 120_000_000, oilRichness: 8 },
  { id: 24, name: "اسرائیل", flag: "🇮🇱", isoCode: "il", flagUrl: "https://flagcdn.com/w640/il.png", isSpecial: true, coinPrice: 700, population: 9_500_000, hasSea: true, region: "خاورمیانه", currency: "شکل", oilReserve: 15_000_000, oilRichness: 5 },
  { id: 25, name: "ترکیه", flag: "🇹🇷", isoCode: "tr", flagUrl: "https://flagcdn.com/w640/tr.png", isSpecial: true, coinPrice: 600, population: 85_000_000, hasSea: true, region: "خاورمیانه", currency: "لیر ترکیه", oilReserve: 5_200_000_000, oilRichness: 25 },
  { id: 26, name: "عربستان", flag: "🇸🇦", isoCode: "sa", flagUrl: "https://flagcdn.com/w640/sa.png", isSpecial: true, coinPrice: 600, population: 36_000_000, hasSea: true, region: "خاورمیانه", currency: "ریال سعودی", oilReserve: 267_000_000_000, oilRichness: 75 },
  { id: 27, name: "کره شمالی", flag: "🇰🇵", isoCode: "kp", flagUrl: "https://flagcdn.com/w640/kp.png", isSpecial: true, coinPrice: 550, population: 26_000_000, hasSea: true, region: "آسیا", currency: "وون کره شمالی", oilReserve: 500_000_000, oilRichness: 15 },
  { id: 28, name: "برزیل", flag: "🇧🇷", isoCode: "br", flagUrl: "https://flagcdn.com/w640/br.png", isSpecial: true, coinPrice: 550, population: 216_000_000, hasSea: true, region: "آمریکای جنوبی", currency: "رئال", oilReserve: 12_900_000_000, oilRichness: 40 },
  { id: 29, name: "کره جنوبی", flag: "🇰🇷", isoCode: "kr", flagUrl: "https://flagcdn.com/w640/kr.png", isSpecial: true, coinPrice: 500, population: 52_000_000, hasSea: true, region: "آسیا", currency: "وون کره جنوبی", oilReserve: 200_000_000, oilRichness: 8 },
  { id: 30, name: "امارات", flag: "🇦🇪", isoCode: "ae", flagUrl: "https://flagcdn.com/w640/ae.png", isSpecial: true, coinPrice: 500, population: 9_500_000, hasSea: true, region: "خاورمیانه", currency: "درهم امارات", oilReserve: 97_800_000_000, oilRichness: 65 },
  { id: 31, name: "کانادا", flag: "🇨🇦", isoCode: "ca", flagUrl: "https://flagcdn.com/w640/ca.png", isSpecial: true, coinPrice: 500, population: 39_000_000, hasSea: true, region: "آمریکای شمالی", currency: "دلار کانادا", oilReserve: 163_000_000_000, oilRichness: 60 },
  { id: 32, name: "استرالیا", flag: "🇦🇺", isoCode: "au", flagUrl: "https://flagcdn.com/w640/au.png", isSpecial: true, coinPrice: 450, population: 26_000_000, hasSea: true, region: "اقیانوسیه", currency: "دلار استرالیا", oilReserve: 1_900_000_000, oilRichness: 18 },
  { id: 33, name: "اندونزی", flag: "🇮🇩", isoCode: "id", flagUrl: "https://flagcdn.com/w640/id.png", isSpecial: true, coinPrice: 400, population: 275_000_000, hasSea: true, region: "آسیا", currency: "روپیه اندونزی", oilReserve: 3_700_000_000, oilRichness: 28 },
  { id: 34, name: "اسپانیا", flag: "🇪🇸", isoCode: "es", flagUrl: "https://flagcdn.com/w640/es.png", isSpecial: true, coinPrice: 400, population: 48_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 200_000_000, oilRichness: 8 },
  { id: 35, name: "قطر", flag: "🇶🇦", isoCode: "qa", flagUrl: "https://flagcdn.com/w640/qa.png", isSpecial: true, coinPrice: 350, population: 3_000_000, hasSea: true, region: "خاورمیانه", currency: "ریال قطر", oilReserve: 25_000_000_000, oilRichness: 60 },
  { id: 36, name: "سوییس", flag: "🇨🇭", isoCode: "ch", flagUrl: "https://flagcdn.com/w640/ch.png", isSpecial: true, coinPrice: 350, population: 9_000_000, hasSea: false, region: "اروپا", currency: "فرانک سوییس", oilReserve: 0, oilRichness: 0 },
  { id: 37, name: "اوکراین", flag: "🇺🇦", isoCode: "ua", flagUrl: "https://flagcdn.com/w640/ua.png", isSpecial: true, coinPrice: 300, population: 38_000_000, hasSea: true, region: "اروپا", currency: "هریونیا", oilReserve: 400_000_000, oilRichness: 12 },
  { id: 38, name: "هلند", flag: "🇳🇱", isoCode: "nl", flagUrl: "https://flagcdn.com/w640/nl.png", isSpecial: true, coinPrice: 300, population: 17_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 300_000_000, oilRichness: 8 },
  { id: 39, name: "سنگاپور", flag: "🇸🇬", isoCode: "sg", flagUrl: "https://flagcdn.com/w640/sg.png", isSpecial: true, coinPrice: 300, population: 5_900_000, hasSea: true, region: "آسیا", currency: "دلار سنگاپور", oilReserve: 90_000_000, oilRichness: 5 },
  { id: 40, name: "ایتالیا", flag: "🇮🇹", isoCode: "it", flagUrl: "https://flagcdn.com/w640/it.png", isSpecial: true, coinPrice: 500, population: 59_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 600_000_000, oilRichness: 10 },
  { id: 41, name: "مکزیک", flag: "🇲🇽", isoCode: "mx", flagUrl: "https://flagcdn.com/w640/mx.png", isSpecial: true, coinPrice: 300, population: 128_000_000, hasSea: true, region: "آمریکای شمالی", currency: "پزو مکزیک", oilReserve: 9_800_000_000, oilRichness: 35 },
  { id: 42, name: "لهستان", flag: "🇵🇱", isoCode: "pl", flagUrl: "https://flagcdn.com/w640/pl.png", isSpecial: true, coinPrice: 250, population: 38_000_000, hasSea: true, region: "اروپا", currency: "زلوتی", oilReserve: 100_000_000, oilRichness: 6 },
  { id: 43, name: "سوئد", flag: "🇸🇪", isoCode: "se", flagUrl: "https://flagcdn.com/w640/se.png", isSpecial: true, coinPrice: 250, population: 10_500_000, hasSea: true, region: "اروپا", currency: "کرون سوئد", oilReserve: 0, oilRichness: 0 },
  { id: 44, name: "مالزی", flag: "🇲🇾", isoCode: "my", flagUrl: "https://flagcdn.com/w640/my.png", isSpecial: true, coinPrice: 200, population: 34_000_000, hasSea: true, region: "آسیا", currency: "رینگیت", oilReserve: 3_000_000_000, oilRichness: 25 },
  { id: 45, name: "یونان", flag: "🇬🇷", isoCode: "gr", flagUrl: "https://flagcdn.com/w640/gr.png", isSpecial: true, coinPrice: 150, population: 10_000_000, hasSea: true, region: "اروپا", currency: "یورو", oilReserve: 10_000_000, oilRichness: 2 },
];

export const EQUIPMENT_DATA: Equipment[] = [
  // ── هوایی ──
  { id: 1, category: "air", subcategory: "drone", name: "پهپاد شناسایی ابابیل (پایه)", emoji: "🛸", atk: 150, def: 80, cyber: 0, speed: 4, priceMoney: 3_000_000, priceCoins: 0, requiresText: "" },
  { id: 2, category: "air", subcategory: "drone", name: "پهپاد انتحاری شاهد ۱۳۶", emoji: "🎯", atk: 450, def: 120, cyber: 0, speed: 5, priceMoney: 8_000_000, priceCoins: 0, requiresText: "" },
  { id: 3, category: "air", subcategory: "drone", name: "پهپاد تهاجمی MQ-9", emoji: "🛩️", atk: 750, def: 300, cyber: 0, speed: 4, priceMoney: 18_000_000, priceCoins: 0, requiresText: "" },
  { id: 4, category: "air", subcategory: "fighter", name: "جنگنده رهگیر F-5 (پایه)", emoji: "✈️", atk: 500, def: 400, cyber: 0, speed: 3, priceMoney: 15_000_000, priceCoins: 0, requiresText: "" },
  { id: 5, category: "air", subcategory: "fighter", name: "جنگنده چندمنظوره سوخو ۳۵", emoji: "🛩️", atk: 1200, def: 800, cyber: 0, speed: 4, priceMoney: 55_000_000, priceCoins: 0, requiresText: "" },
  { id: 6, category: "air", subcategory: "fighter", name: "جنگنده نسل ۵ اف ۳۵ لایتنینگ", emoji: "⚡", atk: 2200, def: 1400, cyber: 0, speed: 5, priceMoney: 120_000_000, priceCoins: 0, requiresText: "" },
  { id: 7, category: "air", subcategory: "bomber", name: "بمب‌افکن تاکتیکی سوخو ۲۴ (پایه)", emoji: "🛫", atk: 900, def: 300, cyber: 0, speed: 3, priceMoney: 35_000_000, priceCoins: 0, requiresText: "" },
  { id: 8, category: "air", subcategory: "bomber", name: "بمب‌افکن استراتژیک B-2 اسپیریت", emoji: "🦇", atk: 2500, def: 600, cyber: 0, speed: 4, priceMoney: 160_000_000, priceCoins: 0, requiresText: "" },
  { id: 9, category: "air", subcategory: "air_defense", name: "سامانه پدافند کوتاه برد تور ام۱ (پایه)", emoji: "🛡️", atk: 100, def: 700, cyber: 0, speed: 2, priceMoney: 20_000_000, priceCoins: 0, requiresText: "" },
  { id: 10, category: "air", subcategory: "air_defense", name: "سامانه موشکی پاتریوت", emoji: "🚀", atk: 200, def: 1500, cyber: 0, speed: 2, priceMoney: 60_000_000, priceCoins: 0, requiresText: "" },
  { id: 11, category: "air", subcategory: "air_defense", name: "سامانه برد بلند اس ۴۰۰ پیروزی", emoji: "🏰", atk: 300, def: 2600, cyber: 0, speed: 2, priceMoney: 110_000_000, priceCoins: 0, requiresText: "" },
  { id: 12, category: "air", subcategory: "transport", name: "هواپیمای ترابری C-130 (پایه)", emoji: "🛬", atk: 50, def: 250, cyber: 0, speed: 3, priceMoney: 10_000_000, priceCoins: 0, requiresText: "" },

  // ── زمینی ──
  { id: 13, category: "land", subcategory: "tank", name: "تانک ذوالفقار ۳ (پایه)", emoji: "💥", atk: 400, def: 450, cyber: 0, speed: 2, priceMoney: 12_000_000, priceCoins: 0, requiresText: "" },
  { id: 14, category: "land", subcategory: "tank", name: "تانک تی ۹۰ ام روسی", emoji: "🛡️", atk: 900, def: 850, cyber: 0, speed: 2, priceMoney: 45_000_000, priceCoins: 0, requiresText: "" },
  { id: 15, category: "land", subcategory: "tank", name: "تانک آبرامز M1A2", emoji: "🚜", atk: 1400, def: 1300, cyber: 0, speed: 2, priceMoney: 80_000_000, priceCoins: 0, requiresText: "" },
  { id: 16, category: "land", subcategory: "apc", name: "نفربر خشایار (پایه)", emoji: "🚐", atk: 80, def: 200, cyber: 0, speed: 3, priceMoney: 5_000_000, priceCoins: 0, requiresText: "" },
  { id: 17, category: "land", subcategory: "apc", name: "نفربر زرهی BTR-82A", emoji: "🚛", atk: 220, def: 500, cyber: 0, speed: 3, priceMoney: 18_000_000, priceCoins: 0, requiresText: "" },
  { id: 18, category: "land", subcategory: "apc", name: "زره‌پوش رزمی بردلی M2", emoji: "🛡️", atk: 450, def: 800, cyber: 0, speed: 3, priceMoney: 35_000_000, priceCoins: 0, requiresText: "" },
  { id: 19, category: "land", subcategory: "artillery", name: "توپخانه خودکششی رعد ۲ (پایه)", emoji: "💥", atk: 350, def: 150, cyber: 0, speed: 2, priceMoney: 9_000_000, priceCoins: 0, requiresText: "" },
  { id: 20, category: "land", subcategory: "artillery", name: "راکت‌انداز چندگانه گراد BM-21", emoji: "🚀", atk: 700, def: 200, cyber: 0, speed: 2, priceMoney: 25_000_000, priceCoins: 0, requiresText: "" },
  { id: 21, category: "land", subcategory: "artillery", name: "سامانه موشکی هایمارس M142", emoji: "🎯", atk: 1500, def: 400, cyber: 0, speed: 3, priceMoney: 75_000_000, priceCoins: 0, requiresText: "" },

  // ── دریایی ──
  { id: 22, category: "sea", subcategory: "speedboat", name: "قایق تندرو موشک‌انداز ذوالفقار (پایه)", emoji: "🚤", atk: 250, def: 180, cyber: 0, speed: 5, priceMoney: 8_000_000, priceCoins: 0, requiresText: "" },
  { id: 23, category: "sea", subcategory: "speedboat", name: "قایق تندر کاتاماران شهید سلیمانی", emoji: "⚡", atk: 600, def: 400, cyber: 0, speed: 5, priceMoney: 22_000_000, priceCoins: 0, requiresText: "" },
  { id: 24, category: "sea", subcategory: "frigate", name: "ناوچه جماران (پایه)", emoji: "🚢", atk: 800, def: 700, cyber: 0, speed: 3, priceMoney: 40_000_000, priceCoins: 0, requiresText: "" },
  { id: 25, category: "sea", subcategory: "frigate", name: "ناوشکن سنگین دنا", emoji: "🛳️", atk: 1600, def: 1300, cyber: 0, speed: 2, priceMoney: 110_000_000, priceCoins: 0, requiresText: "" },
  { id: 26, category: "sea", subcategory: "submarine", name: "زیردریایی سبک کلاس غدیر (پایه)", emoji: "🦈", atk: 500, def: 300, cyber: 0, speed: 3, priceMoney: 25_000_000, priceCoins: 0, requiresText: "" },
  { id: 27, category: "sea", subcategory: "submarine", name: "زیردریایی کلاس فاتح", emoji: "🐋", atk: 1200, def: 800, cyber: 0, speed: 3, priceMoney: 70_000_000, priceCoins: 0, requiresText: "" },
  { id: 28, category: "sea", subcategory: "submarine", name: "زیردریایی هسته‌ای تهاجمی تایفون", emoji: "☢️", atk: 2200, def: 1100, cyber: 0, speed: 3, priceMoney: 220_000_000, priceCoins: 0, requiresText: "نیازمند پروژه غنی‌سازی اورانیوم ۲۰٪" },
  { id: 29, category: "sea", subcategory: "carrier", name: "ناو هواپیمابر کلاس نیمیتز", emoji: "⛴️", atk: 3000, def: 2200, cyber: 0, speed: 1, priceMoney: 350_000_000, priceCoins: 0, requiresText: "" },

  // ── سایبری ──
  { id: 30, category: "cyber", subcategory: "malware", name: "کرم نفوذگر دیداس (پایه)", emoji: "👾", atk: 0, def: 0, cyber: 25_000, speed: 0, priceMoney: 10_000_000, priceCoins: 0, requiresText: "" },
  { id: 31, category: "cyber", subcategory: "malware", name: "بدافزار تخریب صنعتی استاکس‌نت", emoji: "💻", atk: 0, def: 0, cyber: 70_000, speed: 0, priceMoney: 35_000_000, priceCoins: 0, requiresText: "" },
  { id: 32, category: "cyber", subcategory: "firewall", name: "سپر فایروال سایبری ملی (پایه)", emoji: "🛡️", atk: 0, def: 0, cyber: 30_000, speed: 0, priceMoney: 12_000_000, priceCoins: 0, requiresText: "" },
  { id: 33, category: "cyber", subcategory: "firewall", name: "مرکز امنیت ابری و داده‌های ملی", emoji: "🗄️", atk: 0, def: 0, cyber: 85_000, speed: 0, priceMoney: 48_000_000, priceCoins: 0, requiresText: "" },
  { id: 34, category: "cyber", subcategory: "ew", name: "سامانه اخلال راداری و ارتباطی (پایه)", emoji: "📡", atk: 0, def: 0, cyber: 40_000, speed: 0, priceMoney: 18_000_000, priceCoins: 0, requiresText: "" },
  { id: 35, category: "cyber", subcategory: "ew", name: "واحد جنگ الکترونیک پیشرفته کراسوخا", emoji: "⚡", atk: 0, def: 0, cyber: 130_000, speed: 0, priceMoney: 85_000_000, priceCoins: 0, requiresText: "" },

  // ── فضایی ──
  { id: 36, category: "space", subcategory: "space_weapon", name: "ماهواره شناسایی و هدایت نور", emoji: "🛰️", atk: 2500, def: 0, cyber: 20_000, speed: 5, priceMoney: 0, priceCoins: 150, requiresText: "" },
  { id: 37, category: "space", subcategory: "space_weapon", name: "سلاح لیزر فضایی مداری", emoji: "🔆", atk: 5000, def: 0, cyber: 0, speed: 5, priceMoney: 0, priceCoins: 300, requiresText: "" },
  { id: 38, category: "space", subcategory: "space_weapon", name: "موشک بالستیک مداری از ماه", emoji: "🌙", atk: 8500, def: 0, cyber: 0, speed: 5, priceMoney: 0, priceCoins: 500, requiresText: "نیازمند شهر فضایی" },
  { id: 39, category: "space", subcategory: "space_weapon", name: "سامانه شهاب‌سنگ هدایت‌شده", emoji: "☄️", atk: 7000, def: 0, cyber: 0, speed: 4, priceMoney: 0, priceCoins: 450, requiresText: "" },
];

export const STRAITS_DATA: Strait[] = [
  { key: "hormuz", name: "تنگه هرمز", emoji: "⚓", minSeaPower: 500, tollPercent: 1.5, desc: "شاهرگ انتقال نفت خلیج فارس؛ مالک ۱.۵٪ از درآمد غیرمالیاتی حوزه را دریافت می‌کند و می‌تواند کشور هدف را محاصره و ۱۰٪ از درآمدش را مسدود نماید." },
  { key: "suez", name: "کانال سوئز", emoji: "🚢", minSeaPower: 500, tollPercent: 1.5, desc: "کوتاه‌ترین مسیر دریایی آسیا به اروپا؛ تردد تجاری عظیم و امکان انسداد برای کاهش ۱۰٪ درآمد هدف." },
  { key: "malacca", name: "تنگه مالاکا", emoji: "🌊", minSeaPower: 500, tollPercent: 1.5, desc: "مسیر اصلی تجارت نفت و کالا در شرق آسیا؛ اهرم ژئوپلیتیک با قابلیت تحریم و محاصره تجاری." },
  { key: "gibraltar", name: "تنگه جبل‌الطارق", emoji: "⚓", minSeaPower: 500, tollPercent: 1.5, desc: "ورودی استراتژیک مدیترانه به اطلس؛ کنترل کشتیرانی و امکان مسدودسازی درآمد طرف‌های متخاصم." },
  { key: "bab_el_mandeb", name: "تنگه باب‌المندب", emoji: "🌊", minSeaPower: 500, tollPercent: 1.5, desc: "پیونددهنده دریای سرخ به اقیانوس هند؛ گلوگاه امنیتی با قابلیت انسداد تردد و جریمه ۱۰٪ درآمد." },
  { key: "bosporus", name: "تنگه بسفر و داردانل", emoji: "⚓", minSeaPower: 500, tollPercent: 1.5, desc: "دسترسی انحصاری دریای سیاه به مدیترانه؛ بازدارندگی راهبردی و محاصره اقتصادی." },
  { key: "panama", name: "کانال پاناما", emoji: "🚢", minSeaPower: 500, tollPercent: 1.5, desc: "پل آبی حیاتی میان اقیانوس اطلس و آرام؛ کنترل شاهراه ترانزیت جهانی." },
  { key: "bering", name: "تنگه برینگ", emoji: "❄️", minSeaPower: 500, tollPercent: 1.5, desc: "گذرگاه قطبی راهبردی میان قاره آسیا و آمریکای شمالی." },
];

export const TREATIES_DATA: Treaty[] = [
  {
    id: "military",
    name: "پیمان اتحاد نظامی",
    emoji: "🛡️",
    summary: "دفاع مشترک ۳۰ درصدی در برابر هرگونه تهاجم خارجی",
    effect: "در صورت حمله دشمن به یکی از طرفین، ۳۰٪ از قدرت دفاعی کشور متحد به طور خودکار به کمک مدافع می‌آید.",
    riskOrRules: "اعلام رسمی در کانال با مهر دیپلماتیک؛ در صورت لغو یک‌طرفه، امتیاز دیپلماسی کاهش می‌یابد.",
  },
  {
    id: "trade_partners",
    name: "پیمان رفیقای تجاری",
    emoji: "🤝",
    summary: "دریافت درصدی از ارزش کل فروش‌های تجاری طرف مقابل",
    effect: "درصدی توافقی از معاملات صادراتی طرفین به حساب دیگری واریز می‌شود.",
    riskOrRules: "مکانیسم خیانت (خیانت در امانت): امکان شکستن پیمان و غارت خزانه وجود دارد اما به عنوان خائن در کانال بازی رسوا می‌شود!",
  },
  {
    id: "peace",
    name: "پیمان صلح جامع",
    emoji: "🕊️",
    summary: "پایان دادن فوری به جنگ‌های فعال بین دو کشور",
    effect: "تمامی نبردهای مستقیم بلافاصله آتش‌بس اعلام شده و تحریم‌های دوجانبه لغو می‌گردد.",
    riskOrRules: "تا مدت زمان مشخصی امکان اعلان مجدد جنگ بین طرفین وجود ندارد.",
  },
  {
    id: "trust",
    name: "پیمان اعتماد (Trust Pact)",
    emoji: "👁️",
    summary: "دیدن آنی و بدون سانسور اطلاعات کامل و زنده کشور مقابل",
    effect: "دکمه «اعتماد (x)» فعال شده و موجودی خزانه، تعداد تسلیحات، وضعیت برق/آب و دکل‌ها نمایش داده می‌شود.",
    riskOrRules: "نیازمند حضور کشور سوم به عنوان شاهد در سازمان ملل متحد برای ثبت رسمی قرارداد.",
  },
  {
    id: "blood_brothers",
    name: "پیمان برادران تنی",
    emoji: "👑",
    summary: "بالاترین سطح پیوند سیاسی و نظامی؛ ترکیب کلیه پیمان‌ها",
    effect: "اتحاد نظامی کامل + اشتراک تجاری + صلح ابدی + نظارت متقابل با امضای سوپرادمین بازی.",
    riskOrRules: "با ارسال عکس رسمی و اعلام در کانال سراسری ثبت می‌شود و لغو آن جریمه هنگفت سکه شاهی دارد.",
  },
];

export const SECRETS_EXPLANATION = [
  {
    key: "GAME_BOT_TOKEN",
    title: "توکن ربات اصلی بازی (Game Bot Token)",
    type: "الزامی (Required)",
    purpose: "ارتباط با سرور تلگرام برای ربات بازیکنان (عضویت، منوی امپراطوری، حملات، تجارت، سکه شاهی)",
    howToGet: "در تلگرام به @BotFather پیام دهید، دستور /newbot را بفرستید، نام و یوزرنیم ربات را انتخاب کنید و توکن را کپی کنید.",
    example: "9206049189:AAFASCZxwPS2vIcwP-oP0AubtYcfm9gHakU",
    activeStatus: "فعال و ثبت شده در .env",
  },
  {
    key: "ADMIN_BOT_TOKEN",
    title: "توکن ربات ادمین (Admin Bot Token)",
    type: "الزامی (Required)",
    purpose: "ربات مجزا و مستقل برای پنل مدیریت ادمین‌ها با ۱۶ سطح دسترسی، تأیید فیش‌ها، ویرایش اقتصاد و پیام همگانی",
    howToGet: "مجدداً در @BotFather با /newbot یک ربات دیگر برای مدیریت بسازید تا محیط ادمینی کاملاً از بات بازیکنان جدا باشد.",
    example: "8623221084:AAH2AhCKveQyE9xRc6qT3IEztZm4F-xsoEQ",
    activeStatus: "فعال و ثبت شده در .env",
  },
  {
    key: "SUPER_ADMIN_ID",
    title: "آیدی عددی سوپرادمین (Super Admin ID)",
    type: "الزامی (Required)",
    purpose: "شناسایی مالک اصلی در ربات ادمین و اعطای اختیارات تام بدون نیاز به لاگین یا احراز هویت دستی",
    howToGet: "در تلگرام به بات @userinfobot پیام بدهید تا آیدی عددی شما (مثلاً 8358901937) را نشان دهد.",
    example: "8358901937",
    activeStatus: "فعال و ثبت شده در .env",
  },
  {
    key: "FIREBASE_DB_URL",
    title: "آدرس پایگاه داده فایربیس (Firebase Realtime DB URL)",
    type: "اختیاری (Optional)",
    purpose: "پشتیبان‌گیری ابری زنده، صف همگام‌سازی، هارت‌بیت سرور و اسنپ‌شات دوره‌ای جداول. در صورت خالی بودن، بازی در حالت محلی کار می‌کند.",
    howToGet: "در کنسول Firebase یک Realtime Database بسازید و آدرس آن را بردارید (https://your-app-default-rtdb.firebaseio.com).",
    example: "https://wwgame-project-default-rtdb.firebaseio.com",
    activeStatus: "اختیاری (در صورت پر نشدن، به صورت اتوماتیک در حالت محلی JSON ذخیره می‌شود)",
  },
  {
    key: "FIREBASE_AUTH",
    title: "کلید محرمانه فایربیس (Firebase Auth Secret)",
    type: "اختیاری (Optional)",
    purpose: "مجوز دسترسی REST برای خواندن و نوشتن مستقیم روی Firebase Realtime Database بدون واسطه کلاینت",
    howToGet: "در Project Settings فایربیس در تب Service Accounts گزینه Database Secrets را کپی کنید.",
    example: "AIzaSy... یا database secret token",
    activeStatus: "اختیاری",
  },
  {
    key: "DB_PATH",
    title: "مسیر فایل دیتابیس (Database File Path)",
    type: "اختیاری (Optional)",
    purpose: "مسیر فایل SQLite دیتابیس بازی. در صورت تعیین نشدن، به طور پیش‌فرض در کنار پروژه با نام wwgame.db ساخته می‌شود.",
    howToGet: "نیازی به تغییر ندارد؛ پیش‌فرض: ./wwgame.db",
    example: "/var/data/wwgame.db",
    activeStatus: "پیش‌فرض: wwgame.db",
  },
];
