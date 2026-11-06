import React, { useState, useEffect, useMemo } from 'react';
import {
  Users,
  Search,
  Filter,
  Plus,
  RefreshCw,
  Shield,
  Coins,
  Wallet,
  UserCheck,
  UserX,
  Edit3,
  Trash2,
  Copy,
  Check,
  ExternalLink,
  Flame,
  AlertCircle,
  TrendingUp,
  Cpu,
  Smile,
  Globe,
  SlidersHorizontal,
  ChevronDown,
  X,
  LayoutGrid,
  List,
  Sparkles,
  ArrowUpRight,
  ArrowDownLeft,
  CheckCircle2
} from 'lucide-react';

interface User {
  id: number;
  username: string;
  full_name: string;
  joined_at: string;
  royal_coins: number;
  money: number;
  country_id: number | null;
  country_name?: string;
  country_flag?: string;
  country_iso?: string;
  country_flag_url?: string;
  country_taken_at?: string;
  banned: number;
  satisfaction?: number;
  cyber_power?: number;
  currency_name?: string;
  is_super_admin?: number;
  is_admin?: number;
  admin_perms?: string;
}

interface Country {
  id: number;
  name: string;
  flag: string;
  iso_code?: string;
  flag_url?: string;
  is_special: number;
  population: number;
  has_sea: number;
  region: string;
}

export const UsersManager: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCountry, setSelectedCountry] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all'); // all, active, banned, admins
  const [sortBy, setSortBy] = useState<string>('recent'); // recent, money, coins, satisfaction
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  // Copy status
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [quickAdjustUser, setQuickAdjustUser] = useState<User | null>(null);
  const [detailsUser, setDetailsUser] = useState<any | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Reset modals state
  const [isResetWealthModalOpen, setIsResetWealthModalOpen] = useState<boolean>(false);
  const [resetWealthMode, setResetWealthMode] = useState<string>('both_default');
  const [isResettingWealth, setIsResettingWealth] = useState<boolean>(false);
  const [isResetPlayersModalOpen, setIsResetPlayersModalOpen] = useState<boolean>(false);
  const [isResettingPlayers, setIsResettingPlayers] = useState<boolean>(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);

  // Form states for Add User
  const [newUserId, setNewUserId] = useState<string>('');
  const [newUsername, setNewUsername] = useState<string>('');
  const [newFullName, setNewFullName] = useState<string>('');
  const [newCountryId, setNewCountryId] = useState<string>('1');
  const [newMoney, setNewMoney] = useState<string>('200000000');
  const [newCoins, setNewCoins] = useState<string>('10');
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Form states for Quick Adjust
  const [adjustMoneyDelta, setAdjustMoneyDelta] = useState<number>(0);
  const [adjustCoinsDelta, setAdjustCoinsDelta] = useState<number>(0);

  // Load data
  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [usersRes, countriesRes] = await Promise.all([
        fetch('/api/users'),
        fetch('/api/countries')
      ]);
      const usersData = await usersRes.json();
      const countriesData = await countriesRes.json();
      if (Array.isArray(usersData)) setUsers(usersData);
      if (Array.isArray(countriesData)) setCountries(countriesData);
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCopy = (id: number) => {
    navigator.clipboard.writeText(String(id));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSyncFirebase = async () => {
    setIsSyncing(true);
    setSyncFeedback(null);
    try {
      const res = await fetch('/api/users/sync', { method: 'POST' });
      const data = await res.json();
      if (data.users && Array.isArray(data.users)) {
        setUsers(data.users);
      } else {
        await fetchData();
      }
      setSyncFeedback('همگام‌سازی دوطرفه با فایربیس با موفقیت انجام شد!');
    } catch (err: any) {
      setSyncFeedback('خطا در ارتباط با فایربیس');
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncFeedback(null), 4000);
    }
  };

  const handleToggleBan = async (user: User) => {
    try {
      const res = await fetch(`/api/users/${user.id}/ban`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setUsers(prev => prev.map(u => u.id === user.id ? { ...u, banned: data.banned } : u));
      }
    } catch (err) {
      console.error('Failed to toggle ban:', err);
    }
  };

  const handleToggleAdmin = async (user: User) => {
    try {
      const res = await fetch(`/api/users/${user.id}/admin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: user.full_name, isSuper: false })
      });
      const data = await res.json();
      if (data.success) {
        setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_admin: data.is_admin ? 1 : 0 } : u));
      }
    } catch (err) {
      console.error('Failed to toggle admin:', err);
    }
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserId || isNaN(Number(newUserId))) {
      setFormError('شناسه تلگرام باید یک مقدار عددی باشد.');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: Number(newUserId),
          username: newUsername,
          full_name: newFullName,
          country_id: Number(newCountryId),
          money: Number(newMoney),
          royal_coins: Number(newCoins),
        })
      });
      const data = await res.json();
      if (data.success) {
        setIsAddModalOpen(false);
        setNewUserId('');
        setNewUsername('');
        setNewFullName('');
        await fetchData();
      } else {
        setFormError(data.error || 'خطا در ثبت کاربر');
      }
    } catch (err: any) {
      setFormError(err.message || 'خطا در ارتباط با سرور');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveEditUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`/api/users/${editingUser.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: editingUser.username,
          full_name: editingUser.full_name,
          country_id: editingUser.country_id,
          money: Number(editingUser.money),
          royal_coins: Number(editingUser.royal_coins),
          satisfaction: Number(editingUser.satisfaction || 50),
          cyber_power: Number(editingUser.cyber_power || 10000),
          banned: editingUser.banned
        })
      });
      const data = await res.json();
      if (data.success) {
        setEditingUser(null);
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to update user:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickAdjust = async () => {
    if (!quickAdjustUser) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`/api/users/${quickAdjustUser.id}/adjust`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          moneyDelta: adjustMoneyDelta,
          coinsDelta: adjustCoinsDelta
        })
      });
      const data = await res.json();
      if (data.success) {
        setQuickAdjustUser(null);
        setAdjustMoneyDelta(0);
        setAdjustCoinsDelta(0);
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to adjust balance:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`/api/users/${userToDelete.id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        setUserToDelete(null);
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to delete user:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetWealth = async () => {
    setIsResettingWealth(true);
    setFormError(null);
    try {
      const res = await fetch('/api/users/reset-all-wealth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: resetWealthMode })
      });
      const data = await res.json();
      if (data.success) {
        setIsResetWealthModalOpen(false);
        setResetSuccessMessage(data.message || 'ریست دارایی با موفقیت اعمال شد');
        await fetchData();
        setTimeout(() => setResetSuccessMessage(null), 5000);
      } else {
        setFormError(data.error || 'خطا در ریست دارایی');
      }
    } catch (err: any) {
      setFormError(err.message || 'خطا در برقراری ارتباط');
    } finally {
      setIsResettingWealth(false);
    }
  };

  const handleResetAllPlayers = async () => {
    setIsResettingPlayers(true);
    setFormError(null);
    try {
      const res = await fetch('/api/users/reset-all-players', {
        method: 'POST'
      });
      const data = await res.json();
      if (data.success) {
        setIsResetPlayersModalOpen(false);
        setResetSuccessMessage(data.message || 'تمام بازیکنان و کشورها با موفقیت ریست شدند');
        await fetchData();
        setTimeout(() => setResetSuccessMessage(null), 5000);
      } else {
        setFormError(data.error || 'خطا در ریست بازیکنان');
      }
    } catch (err: any) {
      setFormError(err.message || 'خطا در برقراری ارتباط');
    } finally {
      setIsResettingPlayers(false);
    }
  };

  const handleViewDetails = async (userId: number) => {
    try {
      const res = await fetch(`/api/users/${userId}`);
      const data = await res.json();
      setDetailsUser(data);
    } catch (err) {
      console.error('Failed to fetch details:', err);
    }
  };

  // Filtered and Sorted Users
  const filteredUsers = useMemo(() => {
    return users
      .filter(u => {
        // Search
        const q = searchQuery.toLowerCase().trim();
        if (q) {
          const matchId = String(u.id).includes(q);
          const matchUsername = (u.username || '').toLowerCase().includes(q);
          const matchName = (u.full_name || '').toLowerCase().includes(q);
          if (!matchId && !matchUsername && !matchName) return false;
        }

        // Country
        if (selectedCountry !== 'all') {
          if (String(u.country_id) !== selectedCountry) return false;
        }

        // Status
        if (selectedStatus === 'active' && u.banned === 1) return false;
        if (selectedStatus === 'banned' && u.banned !== 1) return false;
        if (selectedStatus === 'admins' && !u.is_admin && !u.is_super_admin) return false;

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'recent') {
          return new Date(b.joined_at || 0).getTime() - new Date(a.joined_at || 0).getTime();
        }
        if (sortBy === 'money') return (b.money || 0) - (a.money || 0);
        if (sortBy === 'coins') return (b.royal_coins || 0) - (a.royal_coins || 0);
        if (sortBy === 'satisfaction') return (b.satisfaction || 0) - (a.satisfaction || 0);
        return 0;
      });
  }, [users, searchQuery, selectedCountry, selectedStatus, sortBy]);

  // Global aggregate stats
  const totalMoney = useMemo(() => users.reduce((acc, u) => acc + (u.money || 0), 0), [users]);
  const totalCoins = useMemo(() => users.reduce((acc, u) => acc + (u.royal_coins || 0), 0), [users]);
  const activeCount = useMemo(() => users.filter(u => u.banned !== 1).length, [users]);
  const bannedCount = useMemo(() => users.filter(u => u.banned === 1).length, [users]);
  const adminCount = useMemo(() => users.filter(u => u.is_admin === 1 || u.is_super_admin === 1).length, [users]);

  return (
    <div className="space-y-6 animate-fadeIn pb-16">
      {/* Top Banner / Explanation */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
              <Users className="w-3.5 h-3.5 text-indigo-400" />
              مدیریت و کنترل بازیکنان (Users & Players Management)
            </div>
            <h2 className="text-2xl font-black text-white tracking-wide flex items-center gap-2">
              سامانه مدیریت بازیکنان و حساب‌های کاربری
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
              مشاهده، ویرایش خزانه و سکه‌های شاهی، تعیین کشور، کنترل وضعیت بن/فعال، و ارتقای سطح دسترسی به مدیریت. 
              اطلاعات مستقیماً با دیتابیس بازی و Realtime Database فایربیس همگام می‌گردد.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => { setFormError(null); setIsResetWealthModalOpen(true); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-semibold shadow-sm transition-all cursor-pointer"
              title="ریست پول و سکه شاهی همه کاربران"
            >
              <Coins className="w-4 h-4 text-amber-400" />
              <span>ریست پول و سکه همه</span>
            </button>

            <button
              onClick={() => { setFormError(null); setIsResetPlayersModalOpen(true); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-semibold shadow-sm transition-all cursor-pointer"
              title="ریست همگانی تمام بازیکنان و کشورها"
            >
              <AlertCircle className="w-4 h-4 text-rose-400" />
              <span>ریست همه بازیکنان</span>
            </button>

            <button
              onClick={handleSyncFirebase}
              disabled={isSyncing}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold shadow-md transition-all cursor-pointer"
              title="همگام‌سازی زنده با فایربیس"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${isSyncing ? 'animate-spin' : ''}`} />
              <span>{isSyncing ? 'همگام‌سازی...' : 'همگام‌سازی'}</span>
            </button>

            <button
              onClick={() => setIsAddModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs font-bold shadow-lg shadow-amber-500/20 transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>افزودن بازیکن</span>
            </button>
          </div>
        </div>

        {resetSuccessMessage && (
          <div className="mt-4 p-3 bg-emerald-500/15 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs flex items-center gap-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{resetSuccessMessage}</span>
          </div>
        )}

        {syncFeedback && (
          <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs flex items-center gap-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{syncFeedback}</span>
          </div>
        )}
      </div>

      {/* Aggregate Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>کل بازیکنان</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-xl font-black text-white font-mono">{users.length}</div>
          <span className="text-[10px] text-slate-500 mt-1">حساب‌های ثبت‌شده</span>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>بازیکنان فعال</span>
            <UserCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-black text-emerald-400 font-mono">{activeCount}</div>
          <span className="text-[10px] text-slate-500 mt-1">بدون مسدودیت</span>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>مسدود شده‌ها</span>
            <UserX className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-xl font-black text-rose-400 font-mono">{bannedCount}</div>
          <span className="text-[10px] text-slate-500 mt-1">دسترسی قطع‌شده</span>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>مدیران سیستم</span>
            <Shield className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-black text-indigo-400 font-mono">{adminCount}</div>
          <span className="text-[10px] text-slate-500 mt-1">ادمین و سوپرادمین</span>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>مجموع سکه شاهی</span>
            <Coins className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-black text-amber-400 font-mono">{totalCoins.toLocaleString()}</div>
          <span className="text-[10px] text-slate-500 mt-1">کل موجودی در بازی</span>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span>خزانه کل پول پایه</span>
            <Wallet className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-lg font-black text-cyan-400 font-mono truncate" title={totalMoney.toLocaleString()}>
            {totalMoney.toLocaleString()}
          </div>
          <span className="text-[10px] text-slate-500 mt-1">ریال / ارز پایه</span>
        </div>
      </div>

      {/* Search, Filter & Actions Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو با شناسه تلگرام، نام کاربری (@TAHAFD_IR) یا نام..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pr-9 pl-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Filters & View switcher */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Country filter */}
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500 cursor-pointer"
            >
              <option value="all">همه کشورها (۴۵)</option>
              {countries.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.flag} {c.name}
                </option>
              ))}
            </select>

            {/* Status filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500 cursor-pointer"
            >
              <option value="all">همه وضعیت‌ها</option>
              <option value="active">🟢 فقط فعال</option>
              <option value="banned">🚫 فقط مسدود</option>
              <option value="admins">👑 فقط مدیران</option>
            </select>

            {/* Sort filter */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500 cursor-pointer"
            >
              <option value="recent">جدیدترین عضویت</option>
              <option value="money">بیشترین خزانه پول</option>
              <option value="coins">بیشترین سکه شاهی</option>
              <option value="satisfaction">بیشترین رضایت مردمی</option>
            </select>

            {/* View Mode Toggle */}
            <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                  viewMode === 'grid' ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-white'
                }`}
                title="نمایش کارتی"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                  viewMode === 'table' ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-white'
                }`}
                title="نمایش جدولی"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Status text */}
        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
          <span>نمایش {filteredUsers.length} کاربر از مجموع {users.length}</span>
          {searchQuery && (
            <button
              onClick={() => { setSearchQuery(''); setSelectedCountry('all'); setSelectedStatus('all'); }}
              className="text-amber-400 hover:underline cursor-pointer"
            >
              پاک‌سازی فیلترها
            </button>
          )}
        </div>
      </div>

      {/* Users Display (Grid or Table) */}
      {isLoading ? (
        <div className="h-64 flex flex-col items-center justify-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-slate-400">در حال دریافت لیست بازیکنان...</span>
        </div>
      ) : filteredUsers.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">کاربری با این مشخصات یافت نشد</h3>
            <p className="text-xs text-slate-400 mt-1">می‌توانید فیلترهای جستجو را تغییر دهید یا کاربر جدیدی اضافه کنید.</p>
          </div>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-bold hover:bg-amber-400 transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>ثبت بازیکن جدید</span>
          </button>
        </div>
      ) : viewMode === 'grid' ? (
        /* GRID VIEW */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredUsers.map((user) => {
            const isSuper = user.is_super_admin === 1;
            const isAdmin = user.is_admin === 1 || isSuper;
            const isBanned = user.banned === 1;

            return (
              <div
                key={user.id}
                className={`bg-slate-900/90 border rounded-2xl p-5 shadow-lg relative flex flex-col justify-between transition-all hover:border-slate-700 ${
                  isSuper
                    ? 'border-indigo-500/50 shadow-indigo-950/20 ring-1 ring-indigo-500/30'
                    : isBanned
                    ? 'border-rose-800/40 opacity-75'
                    : 'border-slate-800'
                }`}
              >
                {/* Header of Card */}
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-slate-800 to-slate-700 border border-slate-600 flex items-center justify-center text-xl shadow-inner relative overflow-hidden">
                        {user.country_iso ? (
                          <img
                            src={user.country_flag_url || `https://flagcdn.com/w160/${user.country_iso}.png`}
                            alt={user.country_name || ''}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          user.country_flag || '🌍'
                        )}
                        {isSuper && (
                          <span className="absolute -top-1 -right-1 text-xs" title="سوپرادمین">
                            👑
                          </span>
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h4 className="text-sm font-bold text-white truncate max-w-[150px]">
                            {user.full_name || user.username || `کاربر ${user.id}`}
                          </h4>
                          {isSuper ? (
                            <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-semibold">
                              سوپرادمین
                            </span>
                          ) : isAdmin ? (
                            <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-semibold">
                              ادمین
                            </span>
                          ) : null}
                          {isBanned && (
                            <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-semibold">
                              مسدود
                            </span>
                          )}
                        </div>
                        {user.username ? (
                          <a
                            href={`https://t.me/${user.username}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-amber-400 hover:underline flex items-center gap-0.5 font-mono"
                          >
                            @{user.username}
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        ) : (
                          <span className="text-[11px] text-slate-500">بدون نام کاربری</span>
                        )}
                      </div>
                    </div>

                    {/* Copy ID Button */}
                    <button
                      onClick={() => handleCopy(user.id)}
                      className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-all text-[11px] flex items-center gap-1 font-mono cursor-pointer"
                      title="کپی شناسه عددی تلگرام"
                    >
                      {copiedId === user.id ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                      <span>{user.id}</span>
                    </button>
                  </div>

                  {/* Country & Assets Info */}
                  <div className="grid grid-cols-2 gap-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 mb-4 text-xs">
                    <div>
                      <span className="text-slate-400 text-[10px] block">کشور انتخابی:</span>
                      <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                        {user.country_iso && (
                          <img
                            src={user.country_flag_url || `https://flagcdn.com/w80/${user.country_iso}.png`}
                            alt={user.country_name || ''}
                            className="w-5 h-3.5 rounded object-cover shadow-sm inline-block"
                            loading="lazy"
                          />
                        )}
                        <span>{user.country_name || 'انتخاب‌نشده'}</span>
                        <span className="text-xs">{user.country_flag}</span>
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] block">تاریخ عضویت:</span>
                      <span className="text-slate-300 font-mono text-[11px] truncate block">
                        {user.joined_at ? user.joined_at.split(' ')[0] : 'نامشخص'}
                      </span>
                    </div>
                  </div>

                  {/* Financial & Empire stats */}
                  <div className="space-y-2 mb-4 text-xs">
                    <div className="flex items-center justify-between bg-slate-950/40 px-3 py-1.5 rounded-lg border border-slate-800/40">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Wallet className="w-3.5 h-3.5 text-cyan-400" />
                        خزانه کشور:
                      </span>
                      <span className="font-mono font-bold text-cyan-300">
                        {user.money?.toLocaleString()} {user.currency_name || 'ریال'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between bg-slate-950/40 px-3 py-1.5 rounded-lg border border-slate-800/40">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Coins className="w-3.5 h-3.5 text-amber-400" />
                        سکه شاهی:
                      </span>
                      <span className="font-mono font-bold text-amber-400">
                        {user.royal_coins?.toLocaleString()} سکه
                      </span>
                    </div>

                    {/* Satisfaction progress */}
                    <div>
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="text-slate-400 flex items-center gap-1">
                          <Smile className="w-3 h-3 text-emerald-400" />
                          رضایت مردمی:
                        </span>
                        <span className="font-mono font-semibold text-emerald-400">
                          {user.satisfaction || 50}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-emerald-500 h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, user.satisfaction || 50))}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Action Buttons Row */}
                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-1 text-xs">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        setQuickAdjustUser(user);
                        setAdjustMoneyDelta(0);
                        setAdjustCoinsDelta(0);
                      }}
                      className="px-2 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/20 transition-all font-medium flex items-center gap-1 cursor-pointer"
                      title="تغییر سریع موجودی و سکه"
                    >
                      <Coins className="w-3.5 h-3.5" />
                      <span>شارژ/کسر</span>
                    </button>

                    <button
                      onClick={() => setEditingUser(user)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
                      title="ویرایش کامل مشخصات"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => handleViewDetails(user.id)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
                      title="مشاهده جزئیات و دارایی‌ها"
                    >
                      <Cpu className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleToggleBan(user)}
                      className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                        isBanned
                          ? 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      }`}
                      title={isBanned ? 'رفع مسدودیت بازیکن' : 'مسدود کردن بازیکن'}
                    >
                      {isBanned ? <UserCheck className="w-3.5 h-3.5" /> : <UserX className="w-3.5 h-3.5" />}
                    </button>

                    <button
                      onClick={() => handleToggleAdmin(user)}
                      className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                        isAdmin
                          ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-indigo-400'
                      }`}
                      title={isAdmin ? 'عزل از مدیریت' : 'ارتقا به ادمین'}
                    >
                      <Shield className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => setUserToDelete(user)}
                      className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-rose-900/40 text-slate-500 hover:text-rose-400 transition-all cursor-pointer"
                      title="حذف کاربر"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* TABLE VIEW */
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="p-3">شناسه تلگرام</th>
                  <th className="p-3">کاربر</th>
                  <th className="p-3">کشور</th>
                  <th className="p-3">خزانه پول</th>
                  <th className="p-3">سکه شاهی</th>
                  <th className="p-3">رضایت</th>
                  <th className="p-3">نقش</th>
                  <th className="p-3">وضعیت</th>
                  <th className="p-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredUsers.map((user) => {
                  const isSuper = user.is_super_admin === 1;
                  const isAdmin = user.is_admin === 1 || isSuper;
                  const isBanned = user.banned === 1;

                  return (
                    <tr key={user.id} className="hover:bg-slate-850/50 transition-colors">
                      <td className="p-3 font-mono">
                        <button
                          onClick={() => handleCopy(user.id)}
                          className="flex items-center gap-1 text-slate-300 hover:text-white cursor-pointer"
                        >
                          {copiedId === user.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-500" />}
                          <span>{user.id}</span>
                        </button>
                      </td>
                      <td className="p-3">
                        <div className="font-bold text-white">{user.full_name || 'بدون نام'}</div>
                        {user.username && (
                          <a
                            href={`https://t.me/${user.username}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-amber-400 hover:underline font-mono"
                          >
                            @{user.username}
                          </a>
                        )}
                      </td>
                      <td className="p-3">
                        <span className="flex items-center gap-1.5 font-semibold text-slate-200">
                          {user.country_iso && (
                            <img
                              src={user.country_flag_url || `https://flagcdn.com/w80/${user.country_iso}.png`}
                              alt={user.country_name || ''}
                              className="w-5 h-3.5 rounded object-cover shadow-sm inline-block"
                              loading="lazy"
                            />
                          )}
                          <span>{user.country_name || '—'}</span>
                          <span className="text-xs">{user.country_flag}</span>
                        </span>
                      </td>
                      <td className="p-3 font-mono font-bold text-cyan-300">
                        {user.money?.toLocaleString()}
                      </td>
                      <td className="p-3 font-mono font-bold text-amber-400">
                        {user.royal_coins?.toLocaleString()}
                      </td>
                      <td className="p-3 font-mono text-emerald-400">
                        {user.satisfaction || 50}%
                      </td>
                      <td className="p-3">
                        {isSuper ? (
                          <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px]">
                            👑 سوپرادمین
                          </span>
                        ) : isAdmin ? (
                          <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px]">
                            🛡️ ادمین
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[11px]">👤 بازیکن</span>
                        )}
                      </td>
                      <td className="p-3">
                        {isBanned ? (
                          <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px]">
                            🚫 مسدود
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px]">
                            ✅ فعال
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => {
                              setQuickAdjustUser(user);
                              setAdjustMoneyDelta(0);
                              setAdjustCoinsDelta(0);
                            }}
                            className="p-1.5 rounded-lg bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 cursor-pointer"
                            title="شارژ موجودی"
                          >
                            <Coins className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setEditingUser(user)}
                            className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 cursor-pointer"
                            title="ویرایش"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleToggleBan(user)}
                            className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 cursor-pointer"
                            title={isBanned ? 'رفع مسدودیت' : 'مسدود کردن'}
                          >
                            {isBanned ? <UserCheck className="w-3.5 h-3.5 text-emerald-400" /> : <UserX className="w-3.5 h-3.5 text-rose-400" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── MODAL: ADD USER ─── */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-amber-400" />
                ثبت بازیکن / کاربر جدید
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddUser} className="space-y-4 mt-4 text-xs">
              {formError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-slate-400 mb-1">شناسه عددی تلگرام (User ID) *</label>
                <input
                  type="number"
                  required
                  placeholder="مثال: 8666501866"
                  value={newUserId}
                  onChange={(e) => setNewUserId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white font-mono focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">نام کاربری تلگرام (بدون @)</label>
                  <input
                    type="text"
                    placeholder="مثال: TAHAFD_IR"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">نام و نام خانوادگی</label>
                  <input
                    type="text"
                    placeholder="مثال: رضا محمدی"
                    value={newFullName}
                    onChange={(e) => setNewFullName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">کشور انتخابی بازیکن</label>
                <select
                  value={newCountryId}
                  onChange={(e) => setNewCountryId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-amber-500 focus:outline-none cursor-pointer"
                >
                  {countries.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.flag} {c.name} {c.is_special ? '(ویژه)' : '(رایگان)'}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">خزانه اولیه (ریال)</label>
                  <input
                    type="number"
                    value={newMoney}
                    onChange={(e) => setNewMoney(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-cyan-300 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">سکه شاهی اولیه</label>
                  <input
                    type="number"
                    value={newCoins}
                    onChange={(e) => setNewCoins(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-amber-400 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all cursor-pointer shadow-lg shadow-amber-500/20"
                >
                  {isSubmitting ? 'در حال ثبت...' : 'ثبت بازیکن'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: EDIT USER ─── */}
      {editingUser && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-amber-400" />
                ویرایش حساب کاربر: {editingUser.id}
              </h3>
              <button
                onClick={() => setEditingUser(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEditUser} className="space-y-4 mt-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">نام کاربری</label>
                  <input
                    type="text"
                    value={editingUser.username || ''}
                    onChange={(e) => setEditingUser({ ...editingUser, username: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">نام و نام خانوادگی</label>
                  <input
                    type="text"
                    value={editingUser.full_name || ''}
                    onChange={(e) => setEditingUser({ ...editingUser, full_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">کشور</label>
                <select
                  value={String(editingUser.country_id || '')}
                  onChange={(e) => setEditingUser({ ...editingUser, country_id: Number(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-amber-500 focus:outline-none cursor-pointer"
                >
                  <option value="">بدون کشور</option>
                  {countries.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.flag} {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">خزانه پول (ریال)</label>
                  <input
                    type="number"
                    value={editingUser.money}
                    onChange={(e) => setEditingUser({ ...editingUser, money: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-cyan-300 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">سکه شاهی</label>
                  <input
                    type="number"
                    value={editingUser.royal_coins}
                    onChange={(e) => setEditingUser({ ...editingUser, royal_coins: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-amber-400 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">رضایت مردمی (درصد: ۰ تا ۱۰۰)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={editingUser.satisfaction ?? 50}
                    onChange={(e) => setEditingUser({ ...editingUser, satisfaction: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-emerald-400 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">قدرت سایبری</label>
                  <input
                    type="number"
                    value={editingUser.cyber_power ?? 10000}
                    onChange={(e) => setEditingUser({ ...editingUser, cyber_power: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-indigo-400 font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="bannedCheckbox"
                  checked={editingUser.banned === 1}
                  onChange={(e) => setEditingUser({ ...editingUser, banned: e.target.checked ? 1 : 0 })}
                  className="rounded border-slate-700 text-rose-500 focus:ring-rose-500 w-4 h-4 cursor-pointer"
                />
                <label htmlFor="bannedCheckbox" className="text-slate-300 cursor-pointer">
                  کاربر مسدود باشد (قطع دسترسی به بازی)
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all cursor-pointer shadow-lg shadow-amber-500/20"
                >
                  {isSubmitting ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: QUICK BALANCE ADJUST ─── */}
      {quickAdjustUser && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Coins className="w-4 h-4 text-amber-400" />
                شارژ / کسر موجودی کاربر
              </h3>
              <button
                onClick={() => setQuickAdjustUser(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 mt-4 text-xs">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <div className="text-slate-400 text-[11px]">کاربر: {quickAdjustUser.full_name || quickAdjustUser.username} ({quickAdjustUser.id})</div>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/60 font-mono">
                  <span>خزانه فعلی: <strong className="text-cyan-300">{quickAdjustUser.money?.toLocaleString()}</strong></span>
                  <span>سکه شاهی: <strong className="text-amber-400">{quickAdjustUser.royal_coins?.toLocaleString()}</strong></span>
                </div>
              </div>

              {/* Money Presets */}
              <div>
                <label className="block text-slate-400 mb-1.5 font-semibold">تغییر خزانه پول (ریال):</label>
                <div className="grid grid-cols-3 gap-1.5 mb-2">
                  <button
                    onClick={() => setAdjustMoneyDelta(prev => prev + 1000000)}
                    className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono cursor-pointer"
                  >
                    + ۱,۰۰۰,۰۰۰
                  </button>
                  <button
                    onClick={() => setAdjustMoneyDelta(prev => prev + 5000000)}
                    className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono cursor-pointer"
                  >
                    + ۵,۰۰۰,۰۰۰
                  </button>
                  <button
                    onClick={() => setAdjustMoneyDelta(prev => prev + 10000000)}
                    className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono cursor-pointer"
                  >
                    + ۱۰,۰۰۰,۰۰۰
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-1.5 mb-2">
                  <button
                    onClick={() => setAdjustMoneyDelta(prev => prev - 1000000)}
                    className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 font-mono cursor-pointer"
                  >
                    - ۱,۰۰۰,۰۰۰ (کسر)
                  </button>
                  <button
                    onClick={() => setAdjustMoneyDelta(0)}
                    className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white cursor-pointer"
                  >
                    صفر کردن تغییرات
                  </button>
                </div>
                <input
                  type="number"
                  value={adjustMoneyDelta}
                  onChange={(e) => setAdjustMoneyDelta(Number(e.target.value))}
                  placeholder="مقدار دستی دلتا..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-cyan-300 font-mono focus:border-amber-500 focus:outline-none"
                />
              </div>

              {/* Coins Presets */}
              <div>
                <label className="block text-slate-400 mb-1.5 font-semibold">تغییر سکه شاهی:</label>
                <div className="grid grid-cols-3 gap-1.5 mb-2">
                  <button
                    onClick={() => setAdjustCoinsDelta(prev => prev + 5)}
                    className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono cursor-pointer"
                  >
                    + ۵ سکه
                  </button>
                  <button
                    onClick={() => setAdjustCoinsDelta(prev => prev + 20)}
                    className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono cursor-pointer"
                  >
                    + ۲۰ سکه
                  </button>
                  <button
                    onClick={() => setAdjustCoinsDelta(prev => prev + 100)}
                    className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono cursor-pointer"
                  >
                    + ۱۰۰ سکه
                  </button>
                </div>
                <input
                  type="number"
                  value={adjustCoinsDelta}
                  onChange={(e) => setAdjustCoinsDelta(Number(e.target.value))}
                  placeholder="مقدار دستی دلتا سکه..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-amber-400 font-mono focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setQuickAdjustUser(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="button"
                  onClick={handleQuickAdjust}
                  disabled={isSubmitting || (adjustMoneyDelta === 0 && adjustCoinsDelta === 0)}
                  className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all cursor-pointer shadow-lg shadow-amber-500/20 disabled:opacity-50"
                >
                  {isSubmitting ? 'در حال اعمال...' : 'اعمال تراکنش'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: USER DETAILS & ASSETS ─── */}
      {detailsUser && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" />
                پروفایل کامل و تجهیزات نظامی: {detailsUser.full_name || detailsUser.id}
              </h3>
              <button
                onClick={() => setDetailsUser(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 mt-4 text-xs">
              {/* User Overview */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">شناسه:</span>
                  <span className="font-mono text-white font-bold">{detailsUser.id}</span>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">کشور:</span>
                  <span className="font-semibold text-slate-200 flex items-center gap-1.5 mt-0.5">
                    {detailsUser.country_iso && (
                      <img
                        src={detailsUser.country_flag_url || `https://flagcdn.com/w80/${detailsUser.country_iso}.png`}
                        alt={detailsUser.country_name || ''}
                        className="w-5 h-3.5 rounded object-cover shadow-sm inline-block"
                        loading="lazy"
                      />
                    )}
                    <span>{detailsUser.country_name || 'بدون کشور'}</span>
                    <span className="text-xs">{detailsUser.country_flag}</span>
                  </span>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">رضایت مردمی:</span>
                  <span className="font-mono text-emerald-400 font-bold">{detailsUser.satisfaction || 50}%</span>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">قدرت سایبری:</span>
                  <span className="font-mono text-indigo-400 font-bold">{detailsUser.cyber_power?.toLocaleString() || 10000}</span>
                </div>
              </div>

              {/* Military Assets List */}
              <div>
                <h4 className="font-bold text-slate-200 mb-2 flex items-center gap-1.5">
                  <Shield className="w-4 h-4 text-amber-400" />
                  تجهیزات نظامی و ارتش بازیکن:
                </h4>
                {detailsUser.assets && detailsUser.assets.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {detailsUser.assets.map((asset: any) => (
                      <div key={asset.id} className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-base">{asset.equip_emoji || '⚔️'}</span>
                          <div>
                            <span className="font-semibold text-white block">{asset.equip_name || asset.item_type}</span>
                            <span className="text-[10px] text-slate-400">قدرت حمله: {asset.attack_power || 0} | دفاع: {asset.defense_power || 0}</span>
                          </div>
                        </div>
                        <div className="font-mono font-bold text-amber-400 text-sm">
                          ×{asset.quantity}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 bg-slate-950 rounded-xl border border-slate-800/80 text-center text-slate-400 text-xs">
                    تجهیزات ثبت‌شده‌ای برای این کاربر در دیتابیس یافت نشد.
                  </div>
                )}
              </div>

              {/* Tickets or Receipts if any */}
              {detailsUser.receipts && detailsUser.receipts.length > 0 && (
                <div>
                  <h4 className="font-bold text-slate-200 mb-2 flex items-center gap-1.5">
                    <Coins className="w-4 h-4 text-amber-400" />
                    آخرین فیش‌های واریزی سکه شاهی:
                  </h4>
                  <div className="space-y-1.5">
                    {detailsUser.receipts.map((r: any) => (
                      <div key={r.id} className="bg-slate-950 p-2 rounded-lg border border-slate-800 flex items-center justify-between text-[11px]">
                        <span>فیش شماره #{r.id} - وضعیت: {r.status}</span>
                        <span className="font-mono text-amber-400">{r.amount_toman?.toLocaleString()} تومان</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-800 mt-6">
              <button
                onClick={() => setDetailsUser(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 cursor-pointer text-xs"
              >
                بستن پنجره
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: DELETE CONFIRMATION ─── */}
      {userToDelete && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-rose-800/50 rounded-2xl w-full max-w-sm p-6 shadow-2xl relative text-xs">
            <div className="flex items-center gap-2 text-rose-400 font-bold text-sm mb-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>تأیید حذف کاربر</span>
            </div>
            <p className="text-slate-300 leading-relaxed mb-4">
              آیا از حذف کامل بازیکن <strong className="text-white">{userToDelete.full_name || userToDelete.id}</strong> مطمئن هستید؟
              تمامی دارایی‌ها، امپراطوری و رکوردها از دیتابیس و فایربیس حذف خواهند شد.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setUserToDelete(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
              >
                انصراف
              </button>
              <button
                onClick={handleDeleteUser}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold cursor-pointer transition-all shadow-lg shadow-rose-900/30"
              >
                {isSubmitting ? 'در حال حذف...' : 'بله، حذف کن'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: RESET WEALTH CONFIRMATION ─── */}
      {isResetWealthModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-amber-500/40 rounded-2xl w-full max-w-md p-6 shadow-2xl relative text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                <Coins className="w-5 h-5" />
                <span>ریست پول و سکه شاهی همه کاربران</span>
              </div>
              <button
                onClick={() => setIsResetWealthModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-slate-300 leading-relaxed">
              این عملیات موجودی پول یا سکه شاهی تمام <strong>{users.length}</strong> کاربر ثبت‌شده را تغییر می‌دهد. لطفاً حالت مورد نظر را انتخاب کنید:
            </p>

            <div className="space-y-2">
              <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/50 cursor-pointer transition-colors">
                <input
                  type="radio"
                  name="reset_mode"
                  value="both_default"
                  checked={resetWealthMode === 'both_default'}
                  onChange={() => setResetWealthMode('both_default')}
                  className="mt-0.5 accent-amber-500"
                />
                <div>
                  <div className="font-bold text-white text-xs">ریست کامل هر دو (پیش‌فرض پیشنهادی)</div>
                  <div className="text-[11px] text-slate-400">سکه شاهی همه ۰ و پول همه ۵۰٬۰۰۰٬۰۰۰ تنظیم می‌شود.</div>
                </div>
              </label>

              <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/50 cursor-pointer transition-colors">
                <input
                  type="radio"
                  name="reset_mode"
                  value="coins_zero"
                  checked={resetWealthMode === 'coins_zero'}
                  onChange={() => setResetWealthMode('coins_zero')}
                  className="mt-0.5 accent-amber-500"
                />
                <div>
                  <div className="font-bold text-white text-xs">فقط صفر کردن سکه شاهی همه</div>
                  <div className="text-[11px] text-slate-400">سکه شاهی تمام کاربران صفر شده، اما پول پایه دست‌نخورده می‌ماند.</div>
                </div>
              </label>

              <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/50 cursor-pointer transition-colors">
                <input
                  type="radio"
                  name="reset_mode"
                  value="money_default"
                  checked={resetWealthMode === 'money_default'}
                  onChange={() => setResetWealthMode('money_default')}
                  className="mt-0.5 accent-amber-500"
                />
                <div>
                  <div className="font-bold text-white text-xs">فقط تنظیم پول همه به بودجه اولیهٔ بازی</div>
                  <div className="text-[11px] text-slate-400">موجودی پول همه ۵۰٬۰۰۰٬۰۰۰ شده، سکه‌ها حفظ می‌شوند.</div>
                </div>
              </label>

              <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/50 cursor-pointer transition-colors">
                <input
                  type="radio"
                  name="reset_mode"
                  value="money_zero"
                  checked={resetWealthMode === 'money_zero'}
                  onChange={() => setResetWealthMode('money_zero')}
                  className="mt-0.5 accent-amber-500"
                />
                <div>
                  <div className="font-bold text-white text-xs">فقط صفر کردن کل پول پایه همه (۰)</div>
                  <div className="text-[11px] text-slate-400">خزانه پولی تمام کاربران کاملاً تخلیه و صفر می‌شود.</div>
                </div>
              </label>
            </div>

            {formError && (
              <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-[11px]">
                {formError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setIsResetWealthModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
              >
                انصراف
              </button>
              <button
                onClick={handleResetWealth}
                disabled={isResettingWealth}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold cursor-pointer transition-all shadow-lg shadow-amber-500/20"
              >
                {isResettingWealth ? 'در حال اعمال ریست...' : 'بله، ریست دارایی‌ها'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: RESET PLAYERS CONFIRMATION ─── */}
      {isResetPlayersModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-rose-500/50 rounded-2xl w-full max-w-md p-6 shadow-2xl relative text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>ریست همگانی تمام بازیکنان بازی</span>
              </div>
              <button
                onClick={() => setIsResetPlayersModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs leading-relaxed space-y-1">
              <div className="font-bold">⚠️ توجه بسیار مهم:</div>
              <div>این عملیات برای آغاز سیزن جدید یا ریست کامل نقشه جهان استفاده می‌شود.</div>
            </div>

            <ul className="space-y-1.5 text-slate-300 text-[11px] list-disc list-inside">
              <li>مالکیت تمام کشورهای اشغال‌شده لغو و همه کشورها آزاد خواهند شد.</li>
              <li>تمام تجهیزات نظامی، ارتش، سربازان و ساختمان‌های کاربران حذف می‌شوند.</li>
              <li>پروژه‌ها، پژوهش‌ها، آموزش‌ها و شرکت‌های بازیکنان پاکسازی می‌گردند.</li>
              <li>پول پایه همه بازیکنان به ۵۰٬۰۰۰٬۰۰۰ ریست شده و سکه شاهی ۰ می‌شود.</li>
              <li>حکم اخراج (بن) تمامی کاربران لغو می‌گردد.</li>
              <li>حساب‌های تلگرام پاک نمی‌شوند و بازیکنان می‌توانند دوباره از منوی بازی کشور بگیرند.</li>
            </ul>

            {formError && (
              <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-[11px]">
                {formError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setIsResetPlayersModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
              >
                انصراف و لغو
              </button>
              <button
                onClick={handleResetAllPlayers}
                disabled={isResettingPlayers}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold cursor-pointer transition-all shadow-lg shadow-rose-900/30"
              >
                {isResettingPlayers ? 'در حال ریست همگانی...' : 'بله، ریست کامل همه بازیکنان'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
