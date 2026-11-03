import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

dotenv.config();
process.env.DISABLE_HMR = 'true';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isProd = process.env.NODE_ENV === 'production';
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

const WW_DIR = path.resolve(__dirname, 'worldwar-game');
const WW_ENV_PATH = path.resolve(WW_DIR, '.env');
const BOT_LOG_PATH = '/tmp/bot.log';

async function getBotPid(): Promise<number | null> {
  try {
    const { stdout } = await execAsync("pgrep -f 'run_all.py'");
    const pids = stdout.trim().split('\n').map(p => parseInt(p, 10)).filter(p => Boolean(p) && p !== process.pid);
    return pids.length > 0 ? pids[0] : null;
  } catch (_) {
    return null;
  }
}

async function stopBotProcess() {
  try {
    await execAsync("pkill -9 -f 'run_all.py' || true");
    await execAsync("pkill -9 -f 'run_game.py' || true");
  } catch (_) {}
}

function startBotProcess(): number | null {
  try {
    const envVars = parseEnvFile(WW_ENV_PATH);
    const logFd = fs.openSync(BOT_LOG_PATH, 'a');
    const child = spawn('python3', ['-u', 'run_all.py'], {
      cwd: WW_DIR,
      env: { ...process.env, ...envVars, PYTHONPATH: '.' },
      detached: true,
      stdio: ['ignore', logFd, logFd],
    });
    child.unref();
    return child.pid || null;
  } catch (err) {
    console.error('Failed to spawn bot:', err);
    return null;
  }
}

function parseEnvFile(filePath: string): Record<string, string> {
  const result: Record<string, string> = {};
  if (!fs.existsSync(filePath)) return result;
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    for (const line of content.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
      const idx = trimmed.indexOf('=');
      const key = trimmed.slice(0, idx).trim();
      const val = trimmed.slice(idx + 1).trim();
      result[key] = val;
    }
  } catch (err) {
    console.error('Error reading env file:', err);
  }
  return result;
}

function writeEnvFile(filePath: string, data: Record<string, string>) {
  const lines: string[] = [
    '# ─── تنظیمات بازی جنگ جهانی ───',
    '# این فایل توسط سامانه وب یا دستی به‌روزرسانی شده است',
    '',
  ];
  lines.push('# توکن ربات اصلی بازی (از @BotFather)');
  lines.push(`GAME_BOT_TOKEN=${data.GAME_BOT_TOKEN || ''}`);
  lines.push('');
  lines.push('# توکن ربات ادمین (ربات جداگانه از @BotFather)');
  lines.push(`ADMIN_BOT_TOKEN=${data.ADMIN_BOT_TOKEN || ''}`);
  lines.push('');
  lines.push('# آیدی عددی ادمین اصلی (سوپرادمین) — برای گرفتن آیدی خود به @userinfobot پیام بدهید');
  lines.push(`SUPER_ADMIN_ID=${data.SUPER_ADMIN_ID || ''}`);
  lines.push('');
  if (data.DB_PATH) {
    lines.push(`DB_PATH=${data.DB_PATH}`);
  }
  if (data.FIREBASE_DB_URL) {
    lines.push(`FIREBASE_DB_URL=${data.FIREBASE_DB_URL}`);
  }
  if (data.FIREBASE_AUTH) {
    lines.push(`FIREBASE_AUTH=${data.FIREBASE_AUTH}`);
  }
  fs.writeFileSync(filePath, lines.join('\n') + '\n', 'utf-8');
}

// Telegram token test cache
const tokenCheckCache: Record<string, { timestamp: number; result: any }> = {};

async function checkTelegramToken(token: string) {
  if (!token || !token.includes(':')) {
    return { ok: false, error: 'فرمت توکن نامعتبر است (باید شامل شناسه و رشته توکن با کاراکتر دو نقطه باشد)' };
  }
  const now = Date.now();
  if (tokenCheckCache[token] && now - tokenCheckCache[token].timestamp < 30000) {
    return tokenCheckCache[token].result;
  }
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    const json = await res.json();
    tokenCheckCache[token] = { timestamp: now, result: json };
    return json;
  } catch (err: any) {
    return { ok: false, error: err.message || 'خطا در برقراری ارتباط با سرور تلگرام' };
  }
}

async function startServer() {
  const app = express();
  app.use(express.json());

  // API Routes
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // Get current secrets & live status
  app.get('/api/secrets', async (req, res) => {
    const envVars = parseEnvFile(WW_ENV_PATH);
    const gameToken = envVars.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '';
    const adminToken = envVars.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '';
    const superAdminId = envVars.SUPER_ADMIN_ID || process.env.SUPER_ADMIN_ID || '';
    const dbPath = envVars.DB_PATH || process.env.DB_PATH || 'wwgame.db';
    const fbUrl = envVars.FIREBASE_DB_URL || process.env.FIREBASE_DB_URL || '';
    const fbAuth = envVars.FIREBASE_AUTH || process.env.FIREBASE_AUTH || '';

    const [gameBotCheck, adminBotCheck, botPid] = await Promise.all([
      gameToken ? checkTelegramToken(gameToken) : Promise.resolve(null),
      adminToken ? checkTelegramToken(adminToken) : Promise.resolve(null),
      getBotPid(),
    ]);

    res.json({
      configured: {
        GAME_BOT_TOKEN: gameToken ? `${gameToken.slice(0, 10)}...${gameToken.slice(-5)}` : '',
        ADMIN_BOT_TOKEN: adminToken ? `${adminToken.slice(0, 10)}...${adminToken.slice(-5)}` : '',
        SUPER_ADMIN_ID: superAdminId,
        DB_PATH: dbPath,
        FIREBASE_DB_URL: fbUrl,
        FIREBASE_AUTH: fbAuth ? '••••••••' : '',
        hasFullGameToken: Boolean(gameToken),
        hasFullAdminToken: Boolean(adminToken),
        rawGameToken: gameToken,
        rawAdminToken: adminToken,
      },
      checks: {
        gameBot: gameBotCheck,
        adminBot: adminBotCheck,
      },
      process: {
        isRunning: Boolean(botPid),
        pid: botPid,
      },
      files: {
        hasEnv: fs.existsSync(WW_ENV_PATH),
        hasDb: fs.existsSync(path.resolve(WW_DIR, 'wwgame.db')),
        hasSource: fs.existsSync(WW_DIR),
      },
    });
  });

    // Users Management API powered by db_bridge.py
    const DB_BRIDGE_PATH = path.resolve(WW_DIR, 'db_bridge.py');

    const runBridge = async (cmd: string, args: string[] = []): Promise<any> => {
      const sanitizedArgs = args.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(' ');
      const fullCmd = `python3 ${DB_BRIDGE_PATH} ${cmd} ${sanitizedArgs}`;
      const { stdout } = await execAsync(fullCmd, { cwd: WW_DIR });
      return JSON.parse(stdout.trim());
    };

    app.get('/api/users', async (req, res) => {
      try {
        const users = await runBridge('get_users');
        res.json(users);
      } catch (err: any) {
        console.error('Error fetching users:', err);
        res.status(500).json({ error: err.message || 'خطا در بارگذاری کاربران' });
      }
    });

    app.get('/api/users/:id', async (req, res) => {
      try {
        const user = await runBridge('get_user', [req.params.id]);
        if (!user) return res.status(404).json({ error: 'کاربر یافت نشد' });
        res.json(user);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.put('/api/users/:id', async (req, res) => {
      try {
        const payload = JSON.stringify(req.body);
        const result = await runBridge('update_user', [req.params.id, payload]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users', async (req, res) => {
      try {
        const payload = JSON.stringify(req.body);
        const result = await runBridge('add_user', [payload]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/:id/ban', async (req, res) => {
      try {
        const result = await runBridge('toggle_ban', [req.params.id]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/:id/adjust', async (req, res) => {
      try {
        const moneyDelta = String(req.body.moneyDelta || 0);
        const coinsDelta = String(req.body.coinsDelta || 0);
        const result = await runBridge('adjust_balance', [req.params.id, moneyDelta, coinsDelta]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/:id/admin', async (req, res) => {
      try {
        const name = req.body.name || '';
        const isSuper = req.body.isSuper ? '1' : '0';
        const result = await runBridge('toggle_admin', [req.params.id, name, isSuper]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.delete('/api/users/:id', async (req, res) => {
      try {
        const result = await runBridge('delete_user', [req.params.id]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/sync', async (req, res) => {
      try {
        const result = await runBridge('sync_firebase');
        const users = await runBridge('get_users');
        res.json({ ...result, users });
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/reset-all-players', async (req, res) => {
      try {
        const result = await runBridge('reset_all_players');
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/users/reset-all-wealth', async (req, res) => {
      try {
        const mode = req.body.mode || 'both_default';
        const result = await runBridge('reset_all_wealth', [mode]);
        res.json(result);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.get('/api/countries', async (req, res) => {
      try {
        const countries = await runBridge('get_countries');
        res.json(countries);
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    // Bot process control endpoints
    app.get('/api/bot-process/status', async (req, res) => {
      const pid = await getBotPid();
      res.json({ isRunning: Boolean(pid), pid });
    });

    app.get('/api/bot-process/logs', (req, res) => {
      try {
        if (!fs.existsSync(BOT_LOG_PATH)) {
          return res.json({ logs: ['درحال راه‌اندازی ربات‌ها...'] });
        }
        const content = fs.readFileSync(BOT_LOG_PATH, 'utf-8');
        const lines = content.trim().split('\n').slice(-60);
        res.json({ logs: lines });
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/bot-process/restart', async (req, res) => {
      await stopBotProcess();
      await new Promise(r => setTimeout(r, 600));
      const pid = startBotProcess();
      res.json({ success: true, message: 'ربات‌ها با موفقیت ری‌استارت شدند', pid });
    });

    app.post('/api/bot-process/start', async (req, res) => {
      let pid = await getBotPid();
      if (!pid) {
        pid = startBotProcess();
      }
      res.json({ success: true, message: 'ربات‌ها فعال شدند', pid });
    });

    app.post('/api/bot-process/stop', async (req, res) => {
      await stopBotProcess();
      res.json({ success: true, message: 'ربات‌ها متوقف شدند' });
    });

  // Save/Update secrets
  app.post('/api/secrets', async (req, res) => {
    try {
      const { GAME_BOT_TOKEN, ADMIN_BOT_TOKEN, SUPER_ADMIN_ID, FIREBASE_DB_URL, FIREBASE_AUTH, DB_PATH } = req.body;
      const current = parseEnvFile(WW_ENV_PATH);
      if (GAME_BOT_TOKEN !== undefined) current.GAME_BOT_TOKEN = GAME_BOT_TOKEN.trim();
      if (ADMIN_BOT_TOKEN !== undefined) current.ADMIN_BOT_TOKEN = ADMIN_BOT_TOKEN.trim();
      if (SUPER_ADMIN_ID !== undefined) current.SUPER_ADMIN_ID = SUPER_ADMIN_ID.trim();
      if (FIREBASE_DB_URL !== undefined) current.FIREBASE_DB_URL = FIREBASE_DB_URL.trim();
      if (FIREBASE_AUTH !== undefined) current.FIREBASE_AUTH = FIREBASE_AUTH.trim();
      if (DB_PATH !== undefined) current.DB_PATH = DB_PATH.trim();

      writeEnvFile(WW_ENV_PATH, current);
      if (current.GAME_BOT_TOKEN) process.env.GAME_BOT_TOKEN = current.GAME_BOT_TOKEN;
      if (current.ADMIN_BOT_TOKEN) process.env.ADMIN_BOT_TOKEN = current.ADMIN_BOT_TOKEN;
      if (current.SUPER_ADMIN_ID) process.env.SUPER_ADMIN_ID = current.SUPER_ADMIN_ID;

      // Invalidate cache
      if (current.GAME_BOT_TOKEN) delete tokenCheckCache[current.GAME_BOT_TOKEN];
      if (current.ADMIN_BOT_TOKEN) delete tokenCheckCache[current.ADMIN_BOT_TOKEN];

      // Verify immediately
      const [gameBotCheck, adminBotCheck] = await Promise.all([
        current.GAME_BOT_TOKEN ? checkTelegramToken(current.GAME_BOT_TOKEN) : Promise.resolve(null),
        current.ADMIN_BOT_TOKEN ? checkTelegramToken(current.ADMIN_BOT_TOKEN) : Promise.resolve(null),
      ]);

      // Automatically restart bot process with the new tokens
      await stopBotProcess();
      await new Promise(r => setTimeout(r, 800));
      const newPid = startBotProcess();

      res.json({
        success: true,
        message: 'تنظیمات با موفقیت در .env ذخیره و ربات‌ها بازراه‌اندازی شدند.',
        pid: newPid,
        checks: {
          gameBot: gameBotCheck,
          adminBot: adminBotCheck,
        },
      });
    } catch (err: any) {
      res.status(500).json({ success: false, error: err.message });
    }
  });

  // Live test single token
  app.post('/api/test-token', async (req, res) => {
    const { token } = req.body;
    if (!token) {
      return res.status(400).json({ ok: false, error: 'توکن ارسال نشده است.' });
    }
    const result = await checkTelegramToken(token.trim());
    res.json(result);
  });

  // Live test Firebase RTDB connection
  app.post('/api/test-firebase', async (req, res) => {
    try {
      const { firebaseUrl, firebaseAuth } = req.body;
      if (!firebaseUrl) {
        return res.status(400).json({ ok: false, error: 'آدرس فایربیس (FIREBASE_DB_URL) وارد نشده است.' });
      }

      const cleanUrl = firebaseUrl.trim().replace(/\/$/, '');
      if (!cleanUrl.startsWith('https://')) {
        return res.status(400).json({ ok: false, error: 'آدرس فایربیس باید با https:// شروع شود.' });
      }

      let testUrl = `${cleanUrl}/status.json`;
      if (firebaseAuth && firebaseAuth.trim()) {
        testUrl += `?auth=${encodeURIComponent(firebaseAuth.trim())}`;
      }

      const t0 = Date.now();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);

      const getResp = await fetch(testUrl, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const latencyMs = Date.now() - t0;

      if (getResp.status === 401 || getResp.status === 403) {
        return res.json({
          ok: false,
          statusCode: getResp.status,
          latencyMs,
          error: 'خطای عدم دسترسی (Permission Denied 401). قوانین Realtime Database نیاز به مجوز خواندن/نوشتن دارند یا باید Database Secret در فیلد FIREBASE_AUTH قرار گیرد.',
        });
      }

      if (getResp.status === 404) {
        return res.json({
          ok: false,
          statusCode: 404,
          latencyMs,
          error: 'مسیر دیتابیس یافت نشد (404 Not Found). بررسی کنید که در کنسول فایربیس سرویس Realtime Database فعال شده باشد نه Cloud Firestore.',
        });
      }

      if (getResp.status >= 200 && getResp.status < 300) {
        let bodyData = null;
        try {
          bodyData = await getResp.json();
        } catch (_) {}

        return res.json({
          ok: true,
          statusCode: getResp.status,
          latencyMs,
          url: cleanUrl,
          message: 'اتصال به Firebase Realtime Database با موفقیت برقرار شد!',
          data: bodyData,
        });
      }

      const errorText = await getResp.text();
      return res.json({
        ok: false,
        statusCode: getResp.status,
        latencyMs,
        error: `پاسخ سرور فایربیس (HTTP ${getResp.status}): ${errorText.slice(0, 100)}`,
      });
    } catch (err: any) {
      return res.json({
        ok: false,
        error: err.name === 'AbortError' ? 'مهلت زمانی اتصال تمام شد (Timeout)' : err.message || 'خطا در برقراری ارتباط با فایربیس',
      });
    }
  });

  // Comprehensive Game Metadata (loaded from project definitions)
  app.get('/api/game/metadata', (req, res) => {
    // Return rich structured data for countries, straits, military, treaties, buildings, religions, governments
    res.json({
      stats: {
        totalCountries: 45,
        freeCountries: 15,
        specialCountries: 30,
        equipmentCount: 24,
        straitCount: 8,
        buildingCount: 38,
        treatyCount: 5,
        dailyMissionCount: 7,
        dbTableCount: 48,
      },
      botArchitecture: {
        gameBot: {
          file: 'run_game.py',
          description: 'ربات تعاملی بازیکنان با کیبوردهای اینلاین، مدیریت امپراطوری، جنگ و تجارت',
          defaultTokenEnv: 'GAME_BOT_TOKEN',
          menus: [
            { key: 'empire', title: '🏰 امپراطوری من', desc: 'مدیریت مردم، پروژه‌های ملی، ارتش، دین و حکومت، درآمد ۳۰ دقیقه‌ای' },
            { key: 'daily', title: '🎯 ماموریت روزانه', desc: 'ماموریت‌های ۷گانه همراه با جوایز سکه شاهی و پول پایه' },
            { key: 'royal_coins', title: '🪙 سکه شاهی', desc: 'خرید پکیج، ارسال عکس فیش کارت‌به‌کارت و تبدیل به پول پایه' },
            { key: 'war_room', title: '⚔️ اتاق جنگ', desc: 'اعلان جنگ رسمی یا غافلگیرانه، حملات هوایی/دریایی/زمینی/سایبری/فضایی' },
            { key: 'un', title: '🇺🇳 سازمان ملل', desc: 'شورای امنیت، بیانیه رسمی، رأی‌گیری تحریم، خلع سلاح و وتو قدرتها' },
            { key: 'trade', title: '🤝 تجارت و تنگه‌ها', desc: 'مذاکره مخفیانه، ۵ پیمان بین‌المللی، معاوضه مستقیم و عوارض ۸ تنگه جهانی' },
            { key: 'rescue', title: '🛟 سازمان نجات', desc: 'کمپین‌های بشردوستانه جنگ، اهدای انرژی و ذخایر اضطراری' },
            { key: 'oil', title: '🛢️ صنعت نفت', desc: 'مخازن زیرزمینی، حفاری دکل، استخراج خودکار و فروش به بازار جهانی' },
          ],
        },
        adminBot: {
          file: 'run_admin.py',
          description: 'پنل مدیریت جامع با ۱۶ سطح دسترسی تفکیک‌شده و مرور مستقیم ۴۸ جدول دیتابیس',
          defaultTokenEnv: 'ADMIN_BOT_TOKEN',
          permissions: [
            'کاربران (جستجو، ویرایش دارایی، بن، ریست)',
            'اقتصاد (قیمت سکه شاهی، شماره کارت، نرخ تبدیل)',
            'فیش‌ها (تأیید/رد واریزی‌های بازیکنان با ارسال خودکار سکه)',
            'کشورها (تغییر جمعیت، پرچم، وضعیت ویژه/رایگان)',
            'نظامی (تغییر قدرت حمله/دفاع، سرعت و قیمت تجهیزات)',
            'پروژه‌ها و ساختمان‌ها (تعریف ساختمان، ویرایش هزینه و اثرات)',
            'سازمان ملل و جنگ‌ها (مدیریت منازعات، لغو جنگ، بیانیه‌ها)',
            'ماموریت‌ها (ساخت ماموریت روزانه جدید و تعیین پاداش)',
            'پشتیبانی (پاسخ دوطرفه به تیکت‌های بازیکنان)',
            'تنظیمات عمومی (کانال اجباری، کانال اعلانات، متن استارت)',
            'پیام همگانی (ارسال برودکست به کل بازیکنان با توکن بات اصلی)',
            'سیزن‌ها (تغییر مود بازی: جنگ جهانی، صلیبی، دوران باستان)',
            'تنگه‌ها (روشن/خاموش کردن کنترل عوارض و نبردهای دریایی)',
            'کتابخانه تصاویر (آپلود و نگهداری آیدی عکس‌های رویدادها)',
            'افزودن انبوه تجهیزات (ایجاد ۵ دسته با یک دستور متنی)',
            'دیتابیس خام (مشاهده و ادیت مستقیم تمامی جداول SQLite)',
          ],
        },
      },
    });
  });

  // Read worldwar-game code files
  app.get('/api/files/read', (req, res) => {
    const relPath = (req.query.path as string) || '';
    if (!relPath) return res.status(400).json({ error: 'path is required' });
    // Sanitize path to stay within WW_DIR
    const safePath = path.resolve(WW_DIR, relPath);
    if (!safePath.startsWith(WW_DIR)) {
      return res.status(403).json({ error: 'Access denied outside worldwar-game directory' });
    }
    if (!fs.existsSync(safePath)) {
      return res.status(404).json({ error: 'File not found' });
    }
    try {
      const stat = fs.statSync(safePath);
      if (stat.isDirectory()) {
        const files = fs.readdirSync(safePath).map((f) => {
          const fStat = fs.statSync(path.resolve(safePath, f));
          return { name: f, isDir: fStat.isDirectory(), size: fStat.size };
        });
        return res.json({ type: 'directory', files });
      }
      const content = fs.readFileSync(safePath, 'utf-8');
      res.json({ type: 'file', content, size: stat.size });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // Interactive Battle Simulation engine matching core/economy.py and war logic
  app.post('/api/simulate/battle', (req, res) => {
    const { attacker, defender } = req.body;
    // Calculate combat outcome
    const atkTotal = Math.max(10, attacker.attackPower || 100);
    const defTotal = Math.max(10, defender.defensePower || 100);
    const cyberAdvantage = (attacker.cyberPower || 0) - (defender.cyberPower || 0);

    // Roll random battle luck factor 0.85 to 1.15
    const luck = 0.85 + Math.random() * 0.3;
    const effectiveAtk = atkTotal * luck * (cyberAdvantage > 0 ? 1.1 : 0.95);
    const ratio = effectiveAtk / (effectiveAtk + defTotal);

    const isVictory = ratio > 0.52;
    const attackerLossRatio = isVictory ? Math.max(0.05, (1 - ratio) * 0.4) : 0.35 + (1 - ratio) * 0.3;
    const defenderLossRatio = isVictory ? 0.4 + ratio * 0.3 : Math.max(0.08, ratio * 0.3);

    const spoilsOfWar = isVictory ? Math.floor((defender.treasury || 50000000) * 0.15) : 0;

    res.json({
      isVictory,
      combatRatio: Number((ratio * 100).toFixed(1)),
      luckMultiplier: Number(luck.toFixed(2)),
      attackerLossPercent: Number((attackerLossRatio * 100).toFixed(1)),
      defenderLossPercent: Number((defenderLossRatio * 100).toFixed(1)),
      spoilsOfWarMoney: spoilsOfWar,
      log: [
        `قدرت تهاجمی موثر مهاجم: ${Math.floor(effectiveAtk).toLocaleString()}`,
        `قدرت تدافعی مدافع: ${Math.floor(defTotal).toLocaleString()}`,
        `برتری سایبری: ${cyberAdvantage >= 0 ? '+' : ''}${cyberAdvantage.toLocaleString()}`,
        isVictory
          ? `پیروزی قاطع نیروهای مهاجم! ۱۵٪ از خزانه کشور مدافع غنیمت گرفته شد.`
          : `شکست حمله! مدافعان خطوط دفاعی خود را حفظ کردند و تلفات سنگینی به مهاجم وارد شد.`,
      ],
    });
  });

  // Setup Vite in Dev or static in Prod
  if (!isProd) {
    const vite = await createViteServer({
      plugins: [
        {
          name: 'strip-vite-client-for-no-hmr',
          enforce: 'post',
          transformIndexHtml(html) {
            return html.replace(/<script\s+type="module"\s+src="\/@vite\/client"><\/script>/gi, '');
          },
        },
      ],
      server: {
        middlewareMode: true,
        hmr: false,
      },
      appType: 'spa',
    });
    app.use(vite.middlewares);
    app.use('*', async (req, res, next) => {
      const url = req.originalUrl;
      try {
        let template = fs.readFileSync(path.resolve(__dirname, 'index.html'), 'utf-8');
        template = await vite.transformIndexHtml(url, template);
        template = template.replace(/<script\s+type="module"\s+src="\/@vite\/client"><\/script>/gi, '');
        res.status(200).set({ 'Content-Type': 'text/html' }).end(template);
      } catch (e) {
        vite.ssrFixStacktrace(e as Error);
        next(e);
      }
    });
  } else {
    const distPath = path.resolve(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.resolve(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', async () => {
    console.log(`World War Game Command Center running at http://0.0.0.0:${PORT}`);
    const pid = await getBotPid();
    if (!pid) {
      console.log('Starting World War Telegram Bots (run_all.py)...');
      startBotProcess();
    } else {
      console.log(`World War Telegram Bots running with PID ${pid}`);
    }
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
