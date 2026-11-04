import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import { WebSocketServer } from 'ws';

const execAsync = promisify(exec);

dotenv.config();
process.env.DISABLE_HMR = 'true';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isProd = process.env.NODE_ENV === 'production';
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

const WW_DIR = path.resolve(__dirname, 'worldwar-game');

// ─── پینگ بیدارباش (Keep-alive) ───
// هر KEEPALIVE_MINUTES دقیقه یک درخواست فیک به آدرس Web App زده می‌شود تا سرویس خواب نرود.
const KEEPALIVE_INTERVAL_MINUTES = Math.max(1, parseInt(process.env.KEEPALIVE_MINUTES || '10', 10) || 10);
const KEEPALIVE_DISABLED = ['0', 'false', 'no', 'off'].includes(String(process.env.KEEPALIVE ?? '1').toLowerCase());
const EXTERNAL_WEBAPP_URL = (process.env.WEBAPP_URL || process.env.PUBLIC_URL || process.env.SELF_URL || '')
  .trim()
  .replace(/\/+$/, '');
let learnedBaseUrl = '';

interface SelfPingState {
  enabled: boolean;
  intervalMinutes: number;
  target: string;
  count: number;
  lastPingAt: string | null;
  lastStatus: number | null;
  lastError: string;
  lastTrigger: string;
}
const selfPingState: SelfPingState = {
  enabled: !KEEPALIVE_DISABLED,
  intervalMinutes: KEEPALIVE_INTERVAL_MINUTES,
  target: EXTERNAL_WEBAPP_URL,
  count: 0,
  lastPingAt: null,
  lastStatus: null,
  lastError: '',
  lastTrigger: '',
};
let keepaliveTimer: NodeJS.Timeout | null = null;

// ─── وضعیت وبهوک ───
const WEBHOOK_PORT = parseInt(process.env.WEBHOOK_PORT || '8080', 10);
const WEBHOOK_PY_URL = `http://127.0.0.1:${WEBHOOK_PORT}`;
const WEBHOOK_MODES = ['1', 'true', 'yes'];
let BOT_WEBHOOK_MODE = WEBHOOK_MODES.includes(String(process.env.WEBHOOK_MODE ?? process.env.WEBHOOK_ENABLED ?? '0').toLowerCase());
interface WebhookStat { hits: number; relayed: number; lastHitAt: string | null; lastStatus: number | null; lastError: string }
const webhookStats: Record<'game' | 'admin', WebhookStat> = {
  game: { hits: 0, relayed: 0, lastHitAt: null, lastStatus: null, lastError: '' },
  admin: { hits: 0, relayed: 0, lastHitAt: null, lastStatus: null, lastError: '' },
};

function resolveSelfUrl(): string {
  const explicit = EXTERNAL_WEBAPP_URL || learnedBaseUrl;
  if (explicit) return explicit;
  return `http://127.0.0.1:${PORT}`;
}

async function selfPing(trigger: string = 'interval'): Promise<SelfPingState> {
  const target = `${resolveSelfUrl()}/health`;
  selfPingState.target = resolveSelfUrl();
  selfPingState.lastTrigger = trigger;
  selfPingState.count += 1;
  selfPingState.lastPingAt = new Date().toISOString();
  try {
    const res = await fetch(target, {
      method: 'GET',
      headers: { 'x-keepalive': '1', 'user-agent': 'wwgame-keepalive/1.0' },
      signal: AbortSignal.timeout ? AbortSignal.timeout(15000) : undefined,
    });
    selfPingState.lastStatus = res.status;
    selfPingState.lastError = res.ok ? '' : `HTTP ${res.status}`;
    if (trigger !== 'interval') console.log(`[KeepAlive] ping ${target} → ${res.status}`);
  } catch (err: any) {
    selfPingState.lastStatus = 0;
    selfPingState.lastError = err?.message || 'network error';
    console.warn(`[KeepAlive] ping failed (${target}): ${selfPingState.lastError}`);
  }
  return selfPingState;
}

function startKeepAlive(): void {
  if (keepaliveTimer) clearInterval(keepaliveTimer);
  if (!selfPingState.enabled) {
    console.log('[KeepAlive] disabled (KEEPALIVE=0)');
    return;
  }
  const everyMs = selfPingState.intervalMinutes * 60 * 1000;
  keepaliveTimer = setInterval(() => { void selfPing('interval'); }, everyMs);
  if ((keepaliveTimer as any).unref) (keepaliveTimer as any).unref();
  // اولین پینگ ۱۵ ثانیه بعد از بالا آمدن، تا سرور کامل آماده شود
  setTimeout(() => { void selfPing('startup'); }, 15000);
  console.log(`[KeepAlive] هر ${selfPingState.intervalMinutes} دقیقه ${resolveSelfUrl()}/health پینگ می‌شود`);
}

let botPidCache: { pid: number | null; at: number } = { pid: null, at: 0 };

async function healthPayload() {
  const now = Date.now();
  if (now - botPidCache.at > 5000) {
    botPidCache = { pid: await getBotPid(), at: now };
  }
  const pid = botPidCache.pid;
  return {
    status: 'ok',
    service: 'worldwar-command-center',
    mode: BOT_WEBHOOK_MODE ? 'webhook' : 'polling',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    botRunning: Boolean(pid),
    botPid: pid,
    watchdog: !isIntentionalStop,
    keepalive: { ...selfPingState, target: selfPingState.target || resolveSelfUrl(), resolvedTarget: resolveSelfUrl() },
    webhook: {
      enabled: BOT_WEBHOOK_MODE,
      pythonService: WEBHOOK_PY_URL,
      paths: { game: '/webhook/game', admin: '/webhook/admin' },
      stats: webhookStats,
    },
  };
}

async function relayWebhook(kind: 'game' | 'admin', req: any, res: any) {
  const stat = webhookStats[kind];
  stat.hits += 1;
  stat.lastHitAt = new Date().toISOString();
  const secret = req.headers['x-telegram-bot-api-secret-token'];
  try {
    const upstream = await fetch(`${WEBHOOK_PY_URL}/webhook/${kind}`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...(secret ? { 'X-Telegram-Bot-Api-Secret-Token': String(secret) } : {}),
      },
      body: JSON.stringify(req.body ?? {}),
      signal: AbortSignal.timeout ? AbortSignal.timeout(12000) : undefined,
    });
    stat.relayed += 1;
    stat.lastStatus = upstream.status;
    stat.lastError = '';
    // همیشه ۲۰۰ برمی‌گردانیم تا تلگرام آپدیت را دوباره نفرستد
    res.status(200).json({ ok: true, relayed: true, upstreamStatus: upstream.status });
  } catch (err: any) {
    stat.lastStatus = 0;
    stat.lastError = err?.message || 'python webhook service unreachable';
    console.warn(`[Webhook] ${kind} relay failed: ${stat.lastError}`);
    res.status(200).json({
      ok: true,
      relayed: false,
      warning: 'سرویس وبهوک پایتون در دسترس نیست — ربات‌ها در حالت polling کار می‌کنند',
      error: stat.lastError,
    });
  }
}

async function telegramApi(token: string, method: string, payload: any = {}) {
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout ? AbortSignal.timeout(15000) : undefined,
    });
    return await res.json();
  } catch (err: any) {
    return { ok: false, description: err?.message || 'network error' };
  }
}

async function webhookStatusPayload() {
  const envVars = parseEnvFile(WW_ENV_PATH);
  const tokens = {
    game: envVars.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '',
    admin: envVars.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '',
  };
  const info: Record<string, any> = {};
  for (const kind of ['game', 'admin'] as const) {
    if (!tokens[kind]) { info[kind] = { configured: false }; continue; }
    const tg = await telegramApi(tokens[kind], 'getWebhookInfo');
    info[kind] = {
      configured: true,
      ok: Boolean(tg.ok),
      url: tg.result?.url || '',
      pendingUpdates: tg.result?.pending_update_count ?? null,
      lastError: tg.result?.last_error_message || null,
      lastErrorAt: tg.result?.last_error_date ? new Date(tg.result.last_error_date * 1000).toISOString() : null,
    };
  }
  let pythonService = false;
  try {
    const r = await fetch(`${WEBHOOK_PY_URL}/health`, { signal: AbortSignal.timeout ? AbortSignal.timeout(3000) : undefined });
    pythonService = r.ok;
  } catch { pythonService = false; }
  return {
    mode: BOT_WEBHOOK_MODE ? 'webhook' : 'polling',
    baseUrl: EXTERNAL_WEBAPP_URL || learnedBaseUrl || null,
    relay: { pythonService, target: WEBHOOK_PY_URL, paths: { game: '/webhook/game', admin: '/webhook/admin' }, stats: webhookStats },
    telegram: info,
    keepalive: { ...selfPingState },
  };
}

const WW_ENV_PATH = path.resolve(WW_DIR, '.env');
const BOT_LOG_PATH = '/tmp/bot.log';

let isIntentionalStop = false;
let watchdogTimer: NodeJS.Timeout | null = null;

function startWatchdog() {
  if (watchdogTimer) clearInterval(watchdogTimer);
  watchdogTimer = setInterval(async () => {
    if (isIntentionalStop) return;
    try {
      const pid = await getBotPid();
      if (!pid) {
        console.log('[Watchdog] Bot process not running! Automatically reviving run_all.py...');
        const newPid = startBotProcess();
        console.log(`[Watchdog] Bot revived with PID ${newPid}`);
      }
    } catch (err) {
      console.error('[Watchdog] Error checking bot PID:', err);
    }
  }, 20000); // Check every 20 seconds
}

async function getBotPid(): Promise<number | null> {
  try {
    const { stdout } = await execAsync("pgrep -f 'run_(all|webhook)\\.py'");
    const pids = stdout.trim().split('\n').map(p => parseInt(p, 10)).filter(p => Boolean(p) && p !== process.pid);
    return pids.length > 0 ? pids[0] : null;
  } catch (_) {
    return null;
  }
}

async function stopBotProcess() {
  try {
    await execAsync("pkill -15 -f 'run_all.py' || true");
    await execAsync("pkill -15 -f 'run_game.py' || true");
    await new Promise((r) => setTimeout(r, 1200));
    await execAsync("pkill -9 -f 'run_all.py' || true");
    await execAsync("pkill -9 -f 'run_game.py' || true");
  } catch (_) {}
}

function startBotProcess(): number | null {
  try {
    const envVars = parseEnvFile(WW_ENV_PATH);
    const logFd = fs.openSync(BOT_LOG_PATH, 'a');
    const script = BOT_WEBHOOK_MODE ? 'run_webhook.py' : 'run_all.py';
    const child = spawn('python3', ['-u', script], {
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
  const canonicalDbPath = path.resolve(WW_DIR, 'wwgame.db');
  lines.push(`DB_PATH=${canonicalDbPath}`);
  if (data.FIREBASE_DB_URL) {
    lines.push(`FIREBASE_DB_URL=${data.FIREBASE_DB_URL}`);
  }
  if (data.FIREBASE_AUTH) {
    lines.push(`FIREBASE_AUTH=${data.FIREBASE_AUTH}`);
  }
  lines.push('');
  lines.push('# ─── وبهوک تلگرام و پینگ بیدارباش ───');
  lines.push(`WEBHOOK_MODE=${data.WEBHOOK_MODE || '0'}`);
  lines.push(`WEBHOOK_BASE_URL=${data.WEBHOOK_BASE_URL || ''}`);
  lines.push(`WEBHOOK_PORT=${data.WEBHOOK_PORT || '8080'}`);
  lines.push(`WEBHOOK_SECRET=${data.WEBHOOK_SECRET || ''}`);
  lines.push(`KEEPALIVE_MINUTES=${data.KEEPALIVE_MINUTES || '10'}`);
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
  // آدرس عمومی سرویس را از درخواست‌های ورودی یاد می‌گیریم تا پینگ بیدارباش به همان Web App برود
  app.use((req, _res, next) => {
    if (!learnedBaseUrl) {
      const host = (req.headers['x-forwarded-host'] as string) || req.headers.host;
      const proto = (req.headers['x-forwarded-proto'] as string) || (req as any).protocol || 'http';
      if (host) learnedBaseUrl = `${String(proto).split(',')[0]}://${String(host).split(',')[0]}`;
    }
    next();
  });

  // API Routes
  app.get('/api/health', async (req, res) => {
    try {
      res.json(await healthPayload());
    } catch (err: any) {
      res.status(500).json({ status: 'error', error: err.message });
    }
  });

  // Get current secrets & live status
  app.get('/api/secrets', async (req, res) => {
    const envVars = parseEnvFile(WW_ENV_PATH);
    const gameToken = envVars.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '';
    const adminToken = envVars.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '';
    const superAdminId = envVars.SUPER_ADMIN_ID || process.env.SUPER_ADMIN_ID || '';
    const dbPath = path.resolve(WW_DIR, 'wwgame.db');
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

    // Health & Uptime Ping endpoints — برای مانیتورینگ و پینگ بیدارباش
    app.get('/health', async (req, res) => {
      try {
        res.json(await healthPayload());
      } catch (err: any) {
        res.status(500).json({ status: 'error', error: err.message });
      }
    });

    app.head('/health', async (req, res) => {
      try {
        res.status(200).json(await healthPayload());
      } catch {
        res.status(500).end();
      }
    });

    app.get('/api/health', async (req, res) => {
      try {
        res.json(await healthPayload());
      } catch (err: any) {
        res.status(500).json({ status: 'error', error: err.message });
      }
    });

    // ─── پینگ بیدارباش: وضعیت، اجرای دستی و تغییر بازه ───
    app.get('/api/keepalive', (req, res) => {
      res.json({ ...selfPingState, target: resolveSelfUrl(), external: Boolean(EXTERNAL_WEBAPP_URL) });
    });

    app.post('/api/keepalive/ping', async (req, res) => {
      const state = await selfPing('manual');
      res.json({ success: state.lastStatus === 200, ...state });
    });

    app.post('/api/keepalive', (req, res) => {
      const { enabled, intervalMinutes } = req.body || {};
      if (typeof enabled === 'boolean') selfPingState.enabled = enabled;
      const minutes = parseInt(String(intervalMinutes ?? selfPingState.intervalMinutes), 10);
      if (Number.isFinite(minutes) && minutes >= 1) selfPingState.intervalMinutes = minutes;
      startKeepAlive();
      res.json({ success: true, ...selfPingState, target: resolveSelfUrl() });
    });

    // ─── سیستم وبهوک تلگرام ───
    // تلگرام آپدیت‌ها را به این مسیرها POST می‌کند؛ در صورت فعال بودن سرویس پایتون،
    // به run_webhook.py (پورت WEBHOOK_PORT) پاس داده می‌شوند.
    app.post('/webhook/game', (req, res) => { void relayWebhook('game', req, res); });
    app.post('/webhook/admin', (req, res) => { void relayWebhook('admin', req, res); });

    app.get('/api/webhook/status', async (req, res) => {
      try {
        res.json(await webhookStatusPayload());
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    app.post('/api/webhook/set', async (req, res) => {
      const base = String(req.body?.baseUrl || EXTERNAL_WEBAPP_URL || learnedBaseUrl || '').replace(/\/+$/, '');
      if (!base) {
        return res.status(400).json({ success: false, error: 'آدرس عمومی مشخص نیست — baseUrl یا WEBHOOK_BASE_URL را تنظیم کنید' });
      }
      const envVars = parseEnvFile(WW_ENV_PATH);
      const tokens = {
        game: envVars.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '',
        admin: envVars.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '',
      };
      const secret = envVars.WEBHOOK_SECRET || process.env.WEBHOOK_SECRET || '';
      const results: Record<string, any> = {};
      for (const kind of ['game', 'admin'] as const) {
        if (!tokens[kind]) { results[kind] = { ok: false, error: 'توکن تنظیم نشده' }; continue; }
        const url = `${base}/webhook/${kind}`;
        const tg = await telegramApi(tokens[kind], 'setWebhook', {
          url,
          ...(secret ? { secret_token: secret } : {}),
          drop_pending_updates: false,
          allowed_updates: ['message', 'callback_query', 'inline_query', 'channel_post', 'chat_member', 'my_chat_member'],
        });
        results[kind] = { ok: Boolean(tg.ok), url, description: tg.description };
      }
      learnedBaseUrl = base;
      res.json({ success: Object.values(results).some((r: any) => r.ok), baseUrl: base, results });
    });

    // تغییر حالت اجرای ربات‌ها (polling ↔ webhook) + ری‌استارت خودکار
    app.post('/api/webhook/mode', async (req, res) => {
      const mode = String(req.body?.mode || '').toLowerCase();
      if (!['webhook', 'polling'].includes(mode)) {
        return res.status(400).json({ success: false, error: "mode باید 'webhook' یا 'polling' باشد" });
      }
      const wantWebhook = mode === 'webhook';
      const current = parseEnvFile(WW_ENV_PATH);
      current.WEBHOOK_MODE = wantWebhook ? '1' : '0';
      if (req.body?.baseUrl) current.WEBHOOK_BASE_URL = String(req.body.baseUrl).replace(/\/+$/, '');
      if (req.body?.secret) current.WEBHOOK_SECRET = String(req.body.secret);
      writeEnvFile(WW_ENV_PATH, current);
      BOT_WEBHOOK_MODE = wantWebhook;

      // ثبت یا حذف وبهوک در تلگرام
      const base = String(req.body?.baseUrl || current.WEBHOOK_BASE_URL || EXTERNAL_WEBAPP_URL || learnedBaseUrl || '').replace(/\/+$/, '');
      const tokens = {
        game: current.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '',
        admin: current.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '',
      };
      const webhookResults: Record<string, any> = {};
      for (const kind of ['game', 'admin'] as const) {
        if (!tokens[kind]) continue;
        if (wantWebhook) {
          if (!base) { webhookResults[kind] = { ok: false, error: 'baseUrl لازم است' }; continue; }
          const tg = await telegramApi(tokens[kind], 'setWebhook', {
            url: `${base}/webhook/${kind}`,
            ...(current.WEBHOOK_SECRET ? { secret_token: current.WEBHOOK_SECRET } : {}),
            drop_pending_updates: false,
            allowed_updates: ['message', 'callback_query', 'inline_query', 'channel_post', 'chat_member', 'my_chat_member'],
          });
          webhookResults[kind] = { ok: Boolean(tg.ok), url: `${base}/webhook/${kind}` };
        } else {
          const tg = await telegramApi(tokens[kind], 'deleteWebhook', { drop_pending_updates: false });
          webhookResults[kind] = { ok: Boolean(tg.ok) };
        }
      }

      // ری‌استارت ربات با اسکریپت مناسب حالت جدید
      isIntentionalStop = false;
      await stopBotProcess();
      await new Promise(r => setTimeout(r, 800));
      const pid = startBotProcess();
      res.json({ success: true, mode, pid, webhook: webhookResults });
    });

    app.post('/api/webhook/delete', async (req, res) => {
      const envVars = parseEnvFile(WW_ENV_PATH);
      const tokens = {
        game: envVars.GAME_BOT_TOKEN || process.env.GAME_BOT_TOKEN || '',
        admin: envVars.ADMIN_BOT_TOKEN || process.env.ADMIN_BOT_TOKEN || '',
      };
      const results: Record<string, any> = {};
      for (const kind of ['game', 'admin'] as const) {
        if (!tokens[kind]) { results[kind] = { ok: false, error: 'توکن تنظیم نشده' }; continue; }
        const tg = await telegramApi(tokens[kind], 'deleteWebhook', { drop_pending_updates: false });
        results[kind] = { ok: Boolean(tg.ok), description: tg.description };
      }
      res.json({ success: Object.values(results).some((r: any) => r.ok), results });
    });

    // Bot process control endpoints
    app.get('/api/bot-process/status', async (req, res) => {
      const pid = await getBotPid();
      res.json({ isRunning: Boolean(pid), pid, watchdog: !isIntentionalStop });
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
      isIntentionalStop = false;
      await stopBotProcess();
      await new Promise(r => setTimeout(r, 600));
      const pid = startBotProcess();
      res.json({ success: true, message: 'ربات‌ها با موفقیت ری‌استارت شدند', pid });
    });

    app.post('/api/bot-process/start', async (req, res) => {
      isIntentionalStop = false;
      let pid = await getBotPid();
      if (!pid) {
        pid = startBotProcess();
      }
      res.json({ success: true, message: 'ربات‌ها فعال شدند', pid });
    });

    app.post('/api/bot-process/stop', async (req, res) => {
      isIntentionalStop = true;
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

    const spoilsOfWar = isVictory ? Math.floor((defender.treasury || 200000000) * 0.15) : 0;

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
      server: {
        middlewareMode: true,
        hmr: false,
      },
      appType: 'spa',
    });

    app.get('/', async (req, res, next) => {
      try {
        let template = fs.readFileSync(path.resolve(__dirname, 'index.html'), 'utf-8');
        template = await vite.transformIndexHtml(req.originalUrl, template);
        res.status(200).set({ 'Content-Type': 'text/html' }).end(template);
      } catch (e) {
        vite.ssrFixStacktrace(e as Error);
        next(e);
      }
    });

    app.use(vite.middlewares);
    app.use('*', async (req, res, next) => {
      const url = req.originalUrl;
      try {
        let template = fs.readFileSync(path.resolve(__dirname, 'index.html'), 'utf-8');
        template = await vite.transformIndexHtml(url, template);
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

  const httpServer = app.listen(PORT, '0.0.0.0', async () => {
    console.log(`World War Game Command Center running at http://0.0.0.0:${PORT}`);
    const pid = await getBotPid();
    if (!pid) {
      console.log('Starting World War Telegram Bots (run_all.py)...');
      startBotProcess();
    } else {
      console.log(`World War Telegram Bots running with PID ${pid}`);
    }
    // Launch watchdog supervisor to auto-restart bot if it ever halts
    startWatchdog();
    // پینگ بیدارباش هر ۱۰ دقیقه به آدرس Web App تا سرویس خواب نرود
    startKeepAlive();
  });

  // Handle WebSocket upgrades gracefully so Vite HMR or ping never throws "closed without opened"
  const wss = new WebSocketServer({ noServer: true });
  wss.on('connection', (ws) => {
    ws.on('error', () => {});
    ws.on('message', () => {});
  });
  httpServer.on('upgrade', (request, socket, head) => {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
