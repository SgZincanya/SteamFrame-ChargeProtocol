(() => {
  const id = 'frame-charge-protocol';
  const loader = window.Framey;
  const marker = document.createElement('span');
  marker.setAttribute('data-fy', '');
  marker.hidden = true;
  document.documentElement.append(marker);

  const dialogs = new Map([
    ['充电器速度较慢', { length: 96, fingerprint: 0xa9f77bd8, close: '关闭' }],
    ['Slow Charger', { length: 194, fingerprint: 0x808b62ab, close: 'Close' }],
  ]);
  const buttonSelector = 'button, [role="button"], .DialogButton';
  const dismissed = new WeakSet();
  const normalize = (text) => text.replace(/[\s\u200b]+/g, '').replaceAll('’', "'");
  function fingerprint(text) {
    let hash = 2166136261;
    for (let index = 0; index < text.length; index++) hash = Math.imul(hash ^ text.charCodeAt(index), 16777619);
    return hash >>> 0;
  }
  const active = () => marker.isConnected && window.Framey === loader;
  const hookKey = 'ShowConnectedSlowDetails';
  let preferences;
  let locales;
  let logo;
  let headphoneProviders = ['bluez'];
  let hook;
  let modalAudio;
  let menu;
  let historyLimits = [10, 25, 50, 100];
  let saving = false;
  const positions = ['top-left', 'top', 'top-right', 'left', 'center', 'right', 'bottom-left', 'bottom', 'bottom-right'];
  const languageNames = { 'zh-Hans': '简体中文', 'zh-Hant': '繁體中文', en: 'English', ja: '日本語', ko: '한국어' };
  const language = () => preferences?.language === 'auto' ? preferences.steam_locale : preferences?.language;
  const translate = (key) => locales?.[language()]?.[key] ?? locales?.en?.[key] ?? key;
  function localizeTab() {
    plugin.name = translate('title');
    plugin.short = language() === 'en' ? 'Charging' : plugin.name;
  }

  function patchModalAudio(owner) {
    if (modalAudio?.owner === owner) return modalAudio;
    try {
      let runtime;
      owner.webpackChunksteamui?.push([[`frame-charge-${Date.now()}`], {}, (require) => { runtime = require; }]);
      if (!runtime) return;
      const { eZ: nav, PN: sounds } = runtime(67758);
      const prototype = runtime(93394).SZ.prototype;
      const show = prototype.ShowModalInternal;
      const remove = prototype.RemoveModal;
      if (typeof nav.PlayNavSound !== 'function' || !Number.isInteger(sounds.ShowModal) || !Number.isInteger(sounds.HideModal)
        || !String(show).includes('OnModalCountChanged') || !String(remove).includes('ModalClosedCallback')) return;

      const tracked = new WeakSet();
      function withoutSound(sound, fn) {
        const original = nav.PlayNavSound;
        const hadOwn = Object.hasOwn(nav, 'PlayNavSound');
        const filter = function (id, ...args) {
          if (id !== sound) return Reflect.apply(original, this, [id, ...args]);
        };
        nav.PlayNavSound = filter;
        try {
          return fn();
        } finally {
          if (nav.PlayNavSound === filter) {
            if (hadOwn) nav.PlayNavSound = original;
            else delete nav.PlayNavSound;
          }
        }
      }

      const showWrapper = function (element, ...args) {
        const type = element?.type;
        const slowCharger = typeof type === 'function'
          && Function.prototype.toString.call(type).includes('QuickAccess_Tab_Perf_ConnectedSlowDetailsTitle');
        if (!active() || !slowCharger) return Reflect.apply(show, this, [element, ...args]);
        const invoke = () => Reflect.apply(show, this, [element, ...args]);
        const result = preferences?.mute_slow_sound ? withoutSound(sounds.ShowModal, invoke) : invoke();
        if (this.active_modal) tracked.add(this.active_modal);
        return result;
      };
      const removeWrapper = function (modal, ...args) {
        const invoke = () => Reflect.apply(remove, this, [modal, ...args]);
        if (active() && preferences?.mute_slow_sound && tracked.has(modal)) return withoutSound(sounds.HideModal, invoke);
        return invoke();
      };
      prototype.ShowModalInternal = showWrapper;
      prototype.RemoveModal = removeWrapper;
      modalAudio = {
        owner,
        play: () => nav.PlayNavSound(sounds.ShowModal),
        restore() {
          if (prototype.ShowModalInternal === showWrapper) prototype.ShowModalInternal = show;
          if (prototype.RemoveModal === removeWrapper) prototype.RemoveModal = remove;
        },
      };
      return modalAudio;
    } catch {
      return undefined;
    }
  }

  function restoreHook() {
    if (hook && hook.store[hookKey] === hook.wrapper) {
      if (hook.descriptor) Object.defineProperty(hook.store, hookKey, hook.descriptor);
      else delete hook.store[hookKey];
    }
    hook = undefined;
    modalAudio?.restore();
    modalAudio = undefined;
  }

  function installHook() {
    let store;
    let owner;
    try {
      owner = window.opener?.SystemPowerStore ? window.opener : window;
      store = owner.SystemPowerStore;
    } catch {
      return false;
    }
    if (hook && hook.store === store && store[hookKey] === hook.wrapper) {
      patchModalAudio(owner);
      return true;
    }
    restoreHook();
    const original = store?.[hookKey];
    if (typeof original !== 'function' || !Function.prototype.toString.call(original).includes('m_bShowingConnectedSlowDetails')) {
      return false;
    }
    const descriptor = Object.getOwnPropertyDescriptor(store, hookKey);
    const wrapper = function (...args) {
      if (active() && preferences?.hide_slow_popup) {
        if (!preferences.mute_slow_sound) patchModalAudio(owner)?.play();
        return;
      }
      return Reflect.apply(original, this, args);
    };
    try {
      Object.defineProperty(store, hookKey, { value: wrapper, configurable: true, writable: true });
      hook = { store, descriptor, wrapper };
      patchModalAudio(owner);
      return true;
    } catch {
      return false;
    }
  }

  function dismissIfMatched(heading) {
    if (!preferences?.hide_slow_popup) return;
    const target = dialogs.get(heading.textContent.trim());
    if (!target) return;

    let container = heading.parentElement;
    for (let level = 0; container && level < 8; level++, container = container.parentElement) {
      if (container === document.body) return;
      const buttons = [...container.querySelectorAll(buttonSelector)].filter(
        (button) => !button.parentElement?.closest(buttonSelector),
      );
      if (buttons.length > 1) return;
      if (buttons.length === 0) continue;

      const button = buttons[0];
      if (dismissed.has(button) || button.disabled || button.getAttribute('aria-disabled') === 'true') return;
      if (button.textContent.trim() !== target.close) return;
      // Check the entire single-button dialog, including the product name.
      const text = normalize(container.textContent);
      if (text.length !== target.length || fingerprint(text) !== target.fingerprint) continue;

      dismissed.add(button);
      const visibility = container.style.getPropertyValue('visibility');
      const priority = container.style.getPropertyPriority('visibility');
      container.style.setProperty('visibility', 'hidden', 'important');
      // If Steam declines the click, put its dialog back so it can be closed normally.
      const dialog = container;
      setTimeout(() => {
        if (dialog.isConnected) dialog.style.setProperty('visibility', visibility, priority);
      }, 300);
      button.click();
      return;
    }
  }

  function scanText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (dialogs.has(node.textContent.trim()) && node.parentElement) dismissIfMatched(node.parentElement);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    for (let text = walker.nextNode(); text; text = walker.nextNode()) {
      if (dialogs.has(text.textContent.trim()) && text.parentElement) dismissIfMatched(text.parentElement);
    }
  }

  function scanDialogs(records) {
    if (!active()) {
      observer.disconnect();
      restoreHook();
      return;
    }
    const headingSelector = '.DialogHeader, [role="heading"], h1, h2, h3';
    for (const heading of document.querySelectorAll(headingSelector)) dismissIfMatched(heading);
    for (const record of records) {
      if (record.type === 'characterData') scanText(record.target);
      for (const node of record.addedNodes) scanText(node);
    }
  }

  const observer = new MutationObserver(scanDialogs);
  observer.observe(document.documentElement, { childList: true, characterData: true, subtree: true });

  const refreshHook = setInterval(() => {
    if (!active()) {
      clearInterval(refreshHook);
      restoreHook();
    } else if (preferences) {
      installHook();
    }
  }, 2000);
  window.addEventListener('pagehide', restoreHook, { once: true });

  async function steamLanguage() {
    const fromTag = (tag) => {
      const code = String(tag ?? '').toLowerCase();
      if (code === 'tchinese' || /^zh-(tw|hk|mo|hant)/.test(code)) return 'zh-Hant';
      if (code === 'schinese' || code.startsWith('zh')) return 'zh-Hans';
      if (code === 'japanese' || /^ja(?:-|$)/.test(code)) return 'ja';
      if (code === 'koreana' || code === 'korean' || /^ko(?:-|$)/.test(code)) return 'ko';
      return 'en';
    };
    try {
      const settings = window.opener?.SteamClient?.Settings ?? window.SteamClient?.Settings;
      if (settings?.GetCurrentLanguage && settings?.GetAvailableLanguages) {
        const [current, available] = await Promise.all([settings.GetCurrentLanguage(), settings.GetAvailableLanguages()]);
        const code = available?.find((entry) => entry.language === current)?.strShortName
          ?? (typeof current === 'string' ? current : null);
        if (code) return fromTag(code);
      }
    } catch {
      // Browser locale is sufficient when the Steam settings interface is absent.
    }
    return fromTag(document.documentElement.lang || navigator.language);
  }

  async function startWorker() {
    if (!active()) return;
    try {
      const reply = await loader.call(id, 'start', null);
      if (reply?.ok && active()) {
        preferences = reply.settings;
        locales = reply.locales;
        logo = reply.logo;
        headphoneProviders = reply.headphone_providers ?? ['bluez'];
        historyLimits = reply.history_limits ?? [10, 25, 50, 100];
        localizeTab();
        installHook();
        scanText(document.documentElement);
        if (menu) renderMenu(menu.box);
        void steamLanguage().then((locale) => { if (active()) void changeSetting('steam_locale', locale, false); });
        return;
      }
    } catch (error) {
      console.warn('[frame-charge-protocol]', error);
    }
    if (active()) setTimeout(startWorker, 3000);
  }

  async function changeSetting(key, value, announce = true) {
    if (saving || !preferences || preferences[key] === value) return;
    saving = true;
    try {
      const reply = await loader.call(id, 'save', { key, value });
      if (!reply?.settings) throw new Error('Settings unavailable');
      const previousLanguage = language();
      preferences = reply.settings;
      if (key === 'hide_slow_popup' && value) scanText(document.documentElement);
      if (previousLanguage !== language()) {
        localizeTab();
        if (menu) renderMenu(menu.box, true);
      }
      if (key === 'headphone_provider') menu?.refreshHeadphones?.();
      if (key === 'history_limit') menu?.refreshHistory?.();
      if (menu && announce) menu.status.textContent = translate('saved');
    } catch {
      if (menu && announce) menu.status.textContent = translate('error');
    } finally {
      saving = false;
      menu?.update();
    }
  }

  const style = document.createElement('style');
  style.setAttribute('data-fy', '');
  style.textContent = `
    .fc-settings { --fc-card:#22262e; --fc-line:#393f49; --fc-text:#f5f7fa; --fc-detail:#bac2cf; --fc-on:#83d1fa;
      box-sizing:border-box; width:100%; max-width:38rem; margin-inline:auto; padding:.25rem .5rem 1rem; color:var(--fc-text); font:1rem/1.45 system-ui,sans-serif; }
    .fc-settings * { box-sizing:border-box; }
    .fc-settings [hidden] { display:none; }
    .fc-settings h2 { font-size:1.38rem; line-height:1.2; margin:0 0 1rem; font-weight:650; }
    .fc-heading { display:flex; align-items:center; gap:.65rem; }
    .fc-heading img { width:2.35rem; height:2.35rem; flex:none; }
    .fc-settings h3 { font-size:.85rem; margin:.95rem .75rem .35rem; color:var(--fc-detail); font-weight:600; }
    .fc-group { border-radius:.85rem; border:1px solid var(--fc-line); background:var(--fc-card); }
    .fc-row { display:flex; flex-wrap:wrap; gap:.5rem .8rem; align-items:center; justify-content:space-between;
      padding:.55rem .8rem; min-height:3rem; width:100%; text-align:start; color:inherit; font:inherit; }
    .fc-row + .fc-row { border-top:1px solid var(--fc-line); }
    .fc-settings button { cursor:pointer; }
    .fc-settings button:disabled { cursor:default; opacity:.52; }
    .fc-toggle { background:none; border:0; border-radius:.5rem; }
    .fc-toggle:hover:not(:disabled) { background:#303641; }
    .fc-settings button:focus-visible { outline:2px solid var(--fc-on); outline-offset:-2px; }
    .fc-copy { flex:1 1 10rem; }
    .fc-detail { display:block; margin-top:.15rem; color:var(--fc-detail); font-size:.8rem; }
    .fc-reading { text-align:end; font-variant-numeric:tabular-nums; font-weight:650; }
    .fc-headphones { border-top:1px solid var(--fc-line); }
    .fc-headphones .fc-device-name { font-weight:650; }
    .fc-track { display:flex; align-items:center; padding:3px; width:2.65rem; height:1.5rem; border-radius:2rem;
      border:1px solid #77818f; background:#353d49; }
    .fc-track::after { content:''; width:.98rem; height:.98rem; border-radius:50%; background:#e5e9ef; }
    [aria-checked="true"] .fc-track { background:var(--fc-on); border-color:var(--fc-on); justify-content:flex-end; }
    [aria-checked="true"] .fc-track::after { background:#162533; }
    .fc-options { display:flex; flex-wrap:wrap; gap:.25rem; }
    .fc-options button { min-height:3.125rem; min-width:3.25rem; padding:.25rem .55rem; border-radius:.55rem;
      border:1px solid #687483; background:#2c3440; color:var(--fc-text); font:inherit; }
    .fc-options button:hover:not(:disabled) { background:#414e5f; }
    .fc-options button[aria-pressed="true"] { color:#162533; background:var(--fc-on); border-color:var(--fc-on); font-weight:700; }
    .fc-position { display:grid; grid-template-columns:repeat(3, 3.15rem); gap:.25rem; }
    .fc-position button { min-width:0; min-height:3.15rem; font-size:1.25rem; }
    .fc-language { width:100%; }
    .fc-language button { flex:1 1 auto; }
    .fc-history-entry { align-items:baseline; font-variant-numeric:tabular-nums; }
    .fc-history-entry time { display:block; }
    .fc-history-entry time + time { color:var(--fc-detail); }
    .fc-status { color:var(--fc-detail); margin:.45rem .8rem 0; min-height:1.4em; font-size:.8rem; }
    @media (prefers-contrast: more) { .fc-settings { --fc-line:#818b99; --fc-detail:#eff3f8; } }
  `;
  document.head.append(style);

  function renderMenu(box, focusLanguage = false) {
    const el = (tag, classes, text) => {
      const element = document.createElement(tag);
      element.className = classes;
      if (text) element.textContent = text;
      return element;
    };
    const root = el('section', 'fc-settings');
    root.lang = language() ?? 'zh-Hans';
    const status = el('p', 'fc-status', preferences ? '' : '…');
    status.setAttribute('role', 'status');
    const rows = [];
    if (!preferences || !locales) {
      root.append(status);
      box.replaceChildren(root);
      menu = { box, status, update() {} };
      return;
    }

    const settingsPage = el('div', '');
    const historyPage = el('div', '');
    historyPage.hidden = true;

    function group(title, page = settingsPage) {
      const card = el('div', 'fc-group');
      page.append(el('h3', '', title), card);
      return card;
    }

    function toggle(card, key) {
      const label = translate(key);
      const button = el('button', 'fc-row fc-toggle');
      const copy = el('span', 'fc-copy', label);
      const track = el('span', 'fc-track');
      track.setAttribute('aria-hidden', 'true');
      button.append(copy, track);
      button.type = 'button';
      button.setAttribute('role', 'switch');
      button.setAttribute('aria-label', label);
      button.addEventListener('click', () => void changeSetting(key, !preferences?.[key]));
      rows.push(() => {
        button.setAttribute('aria-checked', String(Boolean(preferences?.[key])));
      });
      card.append(button);
    }

    const heading = el('h2', 'fc-heading');
    if (logo) {
      const image = el('img', '');
      image.alt = '';
      image.src = logo;
      heading.append(image);
    }
    heading.append(document.createTextNode(translate('title')));
    settingsPage.append(heading);
    const details = group(translate('details'));
    const readings = {};
    for (const key of ['protocol', 'contract_power', 'battery_power']) {
      const row = el('div', 'fc-row');
      const label = el('span', 'fc-copy', translate(key));
      const value = el('span', 'fc-reading', '—');
      row.append(label, value);
      details.append(row);
      readings[key] = { label, value };
    }
    const electrical = el('span', 'fc-detail');
    readings.contract_power.label.append(electrical);
    const numbers = new Intl.NumberFormat(language(), { maximumFractionDigits: 2 });
    const batteryNumbers = new Intl.NumberFormat(language(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const reading = (number, unit, formatter = numbers) => Number.isFinite(number)
      ? `${formatter.format(number)} ${unit}` : '—';
    async function refreshDetails() {
      if (!active() || !root.isConnected || !root.getClientRects().length) return;
      try {
        const data = await loader.call(id, 'details', null);
        if (!root.isConnected) return;
        readings.protocol.value.textContent = data?.protocol ?? (data?.connected === false ? translate('disconnected') : '—');
        readings.contract_power.value.textContent = reading(data?.contract_watts, 'W');
        electrical.textContent = Number.isFinite(data?.voltage_mv) && Number.isFinite(data?.current_ma)
          ? `${reading(data.voltage_mv / 1000, 'V')} × ${reading(data.current_ma / 1000, 'A')}` : '';
        const watts = Number.isFinite(data?.battery_watts) && Math.abs(data.battery_watts) < 0.05 ? 0 : data?.battery_watts;
        readings.battery_power.value.textContent = reading(watts, 'W', batteryNumbers);
      } catch {
        for (const { value } of Object.values(readings)) value.textContent = '—';
        electrical.textContent = '';
      }
      if (active() && root.isConnected) setTimeout(refreshDetails, 1000);
    }

    const headphones = el('div', 'fc-headphones');
    headphones.hidden = true;
    details.append(headphones);
    const percentages = new Intl.NumberFormat(language(), { style: 'percent' });
    const relativeTime = new Intl.RelativeTimeFormat(language(), { numeric: 'always' });
    let headphonesRequest = 0;
    let headphonesTimer;
    let ageTimer;
    let previousDevices;

    function showHeadphones(devices) {
      const snapshot = JSON.stringify(devices);
      if (snapshot === previousDevices) return;
      previousDevices = snapshot;
      clearTimeout(ageTimer);
      headphones.hidden = devices.length === 0;
      headphones.replaceChildren();
      const ageLabels = [];
      const receivedAt = performance.now();
      for (const device of devices) {
        const header = el('div', 'fc-row fc-device-name');
        header.append(el('span', 'fc-copy', device.name));
        if (Number.isInteger(device.percent)) header.append(el('span', 'fc-reading', percentages.format(device.percent / 100)));
        if (device.connected === false) header.append(el('span', 'fc-detail', translate('earbud_disconnected')));
        headphones.append(header);
        for (const part of ['left', 'right', 'case']) {
          if (!Object.hasOwn(device, part)) continue;
          const row = el('div', 'fc-row');
          const label = el('span', 'fc-copy', translate(`earbud_${part}`));
          if (device.stale?.includes(part)) {
            const status = el('span', 'fc-detail', translate('earbud_stale'));
            const age = device.age_seconds?.[part];
            if (Number.isFinite(age) && age >= 0) ageLabels.push({ status, age });
            label.append(status);
          }
          const value = Number.isInteger(device[part]) ? percentages.format(device[part] / 100) : '—';
          row.append(label, el('span', 'fc-reading', value));
          headphones.append(row);
        }
      }
      if (!ageLabels.length) return;

      function updateAges() {
        if (!active() || !root.isConnected || !root.getClientRects().length) return;
        const elapsed = (performance.now() - receivedAt) / 1000;
        for (const { status, age } of ageLabels) {
          const time = relativeTime.format(-Math.floor(age + elapsed), 'second');
          status.textContent = translate('earbud_read_at').replace('{time}', time);
        }
        ageTimer = setTimeout(updateAges, 1000);
      }
      updateAges();
    }

    async function refreshHeadphones() {
      clearTimeout(headphonesTimer);
      const request = ++headphonesRequest;
      if (!active() || !root.isConnected || !root.getClientRects().length) return;
      try {
        const reply = await loader.call(id, 'headphones', null);
        if (root.isConnected && request === headphonesRequest) showHeadphones(reply?.devices ?? []);
      } catch {
        if (request === headphonesRequest) showHeadphones([]);
      }
      if (active() && root.isConnected && request === headphonesRequest) {
        headphonesTimer = setTimeout(refreshHeadphones, 8000);
      }
    }

    const source = group(translate('headphone_source'));
    const sourceRow = el('div', 'fc-row');
    const sourceOptions = el('div', 'fc-options');
    sourceOptions.setAttribute('role', 'group');
    sourceOptions.setAttribute('aria-label', translate('headphone_source'));
    for (const id of headphoneProviders) {
      const key = `headphone_${id}`;
      const label = translate(key);
      const button = el('button', '', label === key ? id : label);
      button.type = 'button';
      button.addEventListener('click', () => void changeSetting('headphone_provider', id));
      rows.push(() => {
        const selected = headphoneProviders.includes(preferences.headphone_provider) ? preferences.headphone_provider : 'bluez';
        button.setAttribute('aria-pressed', String(selected === id));
      });
      sourceOptions.append(button);
    }
    sourceRow.append(sourceOptions);
    source.append(sourceRow);
    const system = group(translate('system'));
    toggle(system, 'hide_slow_popup');
    toggle(system, 'mute_slow_sound');
    const stopped = group(translate('stopped'));
    toggle(stopped, 'stop_popup');
    toggle(stopped, 'stop_sound');
    const display = group(translate('overlay'));
    toggle(display, 'show');
    toggle(display, 'full_name');
    toggle(display, 'show_watts');

    const duration = el('div', 'fc-row');
    const options = el('div', 'fc-options');
    options.setAttribute('role', 'group');
    options.setAttribute('aria-label', translate('duration'));
    duration.append(el('span', 'fc-copy', translate('duration')), options);
    for (const seconds of [3, 5, 8]) {
      const button = el('button', '', translate('seconds').replace('{n}', String(seconds)));
      button.type = 'button';
      button.addEventListener('click', () => void changeSetting('seconds', seconds));
      rows.push(() => {
        button.setAttribute('aria-pressed', String(preferences?.seconds === seconds));
      });
      options.append(button);
    }
    display.append(duration);
    toggle(display, 'fade');
    const placement = el('div', 'fc-row');
    const location = el('span', 'fc-copy', translate('position'));
    const selectedLocation = el('span', 'fc-detail');
    location.append(selectedLocation);
    const grid = el('div', 'fc-options fc-position');
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', translate('position'));
    positions.forEach((position, index) => {
      const name = translate('positions')[index];
      const button = el('button', '', '·');
      button.type = 'button';
      button.setAttribute('aria-label', name);
      button.title = name;
      button.addEventListener('click', () => void changeSetting('position', position));
      rows.push(() => {
        const selected = preferences.position === position;
        button.setAttribute('aria-pressed', String(selected));
        button.textContent = selected ? '●' : '·';
        if (selected) selectedLocation.textContent = name;
      });
      grid.append(button);
    });
    placement.append(location, grid);
    display.append(placement);

    const languageGroup = group(translate('language'));
    const languageRow = el('div', 'fc-row');
    const languageOptions = el('div', 'fc-options fc-language');
    languageOptions.setAttribute('role', 'group');
    languageOptions.setAttribute('aria-label', translate('language'));
    for (const [key, name] of Object.entries({ auto: translate('auto'), ...languageNames })) {
      const button = el('button', '', name);
      button.type = 'button';
      button.addEventListener('click', () => void changeSetting('language', key));
      rows.push(() => button.setAttribute('aria-pressed', String(preferences.language === key)));
      languageOptions.append(button);
    }
    languageRow.append(languageOptions);
    languageGroup.append(languageRow);

    function action(key, handler) {
      const button = el('button', '', translate(key));
      button.type = 'button';
      button.addEventListener('click', handler);
      return button;
    }

    const historyGroup = group(translate('history_title'));
    toggle(historyGroup, 'record_history');
    const historyLink = el('div', 'fc-row fc-options');
    const openHistory = action('history_open', () => showHistory(true));
    historyLink.append(openHistory);
    historyGroup.append(historyLink);
    rows.push(() => { historyLink.hidden = !preferences.record_history; });

    const nav = el('div', 'fc-row fc-options');
    const back = action('history_back', () => showHistory(false));
    nav.append(back);
    historyPage.append(nav, el('h2', '', translate('history_title')));
    const controls = el('div', 'fc-group');
    const limits = el('div', 'fc-row fc-options');
    limits.setAttribute('role', 'group');
    limits.setAttribute('aria-label', translate('history_limit'));
    limits.append(el('span', 'fc-copy', translate('history_limit')));
    for (const count of historyLimits) {
      const button = el('button', '', numbers.format(count));
      button.type = 'button';
      button.addEventListener('click', () => void changeSetting('history_limit', count));
      rows.push(() => button.setAttribute('aria-pressed', String(preferences.history_limit === count)));
      limits.append(button);
    }
    const clearRow = el('div', 'fc-row fc-options');
    const clearButton = action('history_clear', () => {
      confirmRow.hidden = false;
      cancelClear.focus();
    });
    clearRow.append(clearButton);
    const confirmRow = el('div', 'fc-row fc-options');
    confirmRow.hidden = true;
    const cancelClear = action('history_cancel', () => {
      confirmRow.hidden = true;
      clearButton.focus();
    });
    const confirmClear = action('history_clear', () => void refreshHistory('clear_history'));
    confirmRow.append(el('span', 'fc-copy', translate('history_confirm')), cancelClear, confirmClear);
    controls.append(limits, clearRow, confirmRow);
    historyPage.append(controls);
    const records = group(translate('history_records'), historyPage);
    const dates = new Intl.DateTimeFormat(language(), {
      calendar: 'gregory', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    });
    const units = ['day', 'hour', 'minute', 'second'].map((unit, index) => [
      [86400, 3600, 60, 1][index],
      new Intl.NumberFormat(language(), { style: 'unit', unit, unitDisplay: 'short' }),
    ]);
    let historyTimer;
    let historyRequest = 0;
    let clearing = false;
    let previousHistory;

    function showHistory(open) {
      settingsPage.hidden = open;
      historyPage.hidden = !open;
      confirmRow.hidden = true;
      status.textContent = '';
      if (open) {
        back.focus();
        void refreshHistory();
      } else {
        clearTimeout(historyTimer);
        historyRequest++;
        openHistory.focus();
      }
    }

    function showRecords(sessions) {
      const snapshot = JSON.stringify(sessions);
      if (snapshot === previousHistory) return;
      previousHistory = snapshot;
      records.replaceChildren();
      if (!sessions.length) records.append(el('div', 'fc-row', translate('history_empty')));
      for (const { started, ended, seconds } of sessions) {
        const row = el('div', 'fc-row fc-history-entry');
        const interval = el('div', 'fc-copy');
        for (const [label, timestamp] of [['history_start', started], ['history_end', ended]]) {
          const date = new Date(timestamp * 1000);
          const time = el('time', '', translate(label).replace('{time}', dates.format(date)));
          time.dateTime = date.toISOString();
          interval.append(time);
        }
        let remainder = seconds;
        const parts = [];
        for (const [divisor, format] of units) {
          const count = Math.floor(remainder / divisor);
          if (count || (divisor === 1 && !parts.length)) parts.push(format.format(count));
          remainder %= divisor;
        }
        row.append(interval, el('span', 'fc-reading', parts.join(' ')));
        records.append(row);
      }
    }

    async function refreshHistory(method = 'history') {
      if (clearing || !active() || !root.isConnected || historyPage.hidden) return;
      clearTimeout(historyTimer);
      const request = ++historyRequest;
      clearing = method === 'clear_history';
      confirmClear.disabled = clearing;
      back.disabled = clearing;
      try {
        const reply = await loader.call(id, method, null);
        if (!Array.isArray(reply?.sessions)) throw new Error('History unavailable');
        if (request === historyRequest) {
          showRecords(reply.sessions);
          if (clearing) {
            confirmRow.hidden = true;
            clearButton.focus();
            status.textContent = translate('history_cleared');
          }
        }
      } catch {
        if (request === historyRequest) status.textContent = translate('history_error');
      } finally {
        clearing = false;
        confirmClear.disabled = false;
        back.disabled = false;
        if (active() && root.isConnected && !historyPage.hidden && request === historyRequest) {
          historyTimer = setTimeout(refreshHistory, 3000);
        }
      }
    }

    root.append(settingsPage, historyPage, status);
    box.replaceChildren(root);
    menu = {
      box,
      status,
      refreshHeadphones,
      refreshHistory,
      update() {
        for (const row of rows) row();
      },
    };
    menu.update();
    void refreshDetails();
    void refreshHeadphones();
    if (focusLanguage) languageOptions.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true });
  }

  const plugin = { render: renderMenu };
  loader.register(plugin);
  void startWorker();
})();
