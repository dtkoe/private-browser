"use client";
import { useEffect, useState } from "react";

export type Lang = "en" | "ru";

const DICT = {
  en: {
    // Header / nav
    "brand.version": "v0.7.0",
    "nav.profiles": "Profiles",
    "nav.proxies": "Proxies",
    "nav.settings": "Settings",
    "header.import": "Import",
    "header.lock": "Lock",
    "import.password_prompt": "Import password:",
    // LoginScreen
    "login.loading": "Loading…",
    "login.title": "Genesis Browser",
    "login.create_hint":
      "Create a master password (≥12 chars). This encrypts your data; there is no recovery if lost.",
    "login.unlock_hint": "Enter your master password to unlock.",
    "login.password_placeholder": "Master password",
    "login.confirm_placeholder": "Confirm password",
    "login.working": "Working…",
    "login.create_button": "Create & unlock",
    "login.unlock_button": "Unlock",
    "login.err_min_length": "password must be at least 12 characters",
    "login.err_mismatch": "passwords don't match",
    // Sidebar
    "sidebar.profiles": "Profiles",
    "sidebar.new": "+ New",
    "sidebar.filter": "Filter…",
    "sidebar.no_profiles": "No profiles yet",
    "sidebar.no_matches": "No matches for",
    "sidebar.selected_n": "selected",
    "sidebar.delete": "Delete",
    "sidebar.clear": "Clear",
    "sidebar.bulk_delete_confirm": "Delete {n} profile(s)? Cannot be undone.",
    "sidebar.name_placeholder": "Name",
    "sidebar.create": "Create",
    "sidebar.cancel": "Cancel",
    "sidebar.random_os": "Random OS",
    "sidebar.locale_label": "Language & timezone the profile will pretend to use",
    // ProfileDetail
    "profile.empty": "Select a profile from the sidebar.",
    "profile.click_to_rename": "Click to rename",
    "profile.status_running": "running",
    "profile.notes": "Notes",
    "profile.notes_placeholder": "Anything to remember about this profile…",
    "profile.tags": "Tags (comma-separated)",
    "profile.tags_placeholder": "work, ads, dev",
    "profile.color": "Color",
    "profile.proxy": "Proxy",
    "profile.no_proxy": "No proxy (WebRTC blocked)",
    "profile.extensions": "Extensions",
    "profile.install_xpi": "+ Install .xpi",
    "profile.no_extensions": "No extensions installed.",
    "profile.remove": "Remove",
    "profile.fingerprint_raw": "Fingerprint (raw)",
    "profile.stop": "Stop",
    "profile.launch": "▶ Launch",
    "profile.regenerate": "Regenerate fp",
    "profile.clone": "Clone",
    "profile.export": "Export",
    "profile.delete": "Delete",
    "profile.export_password_prompt": "Export password (≥12 chars):",
    "profile.delete_confirm":
      'Delete profile "{name}"? This removes its browser data too.',
    // ProxyPanel
    "proxy.title": "Proxies",
    "proxy.add_one": "Add one",
    "proxy.label_optional": "Label (optional)",
    "proxy.host": "host",
    "proxy.port": "port",
    "proxy.add_button": "Add proxy",
    "proxy.batch_import": "Batch import (one per line: host:port or host:port:user:pass)",
    "proxy.import": "Import",
    "proxy.col_label": "Label",
    "proxy.col_endpoint": "Endpoint",
    "proxy.col_last_check": "Last check",
    "proxy.col_ip_geo": "IP / Geo",
    "proxy.last_check_never": "never",
    "proxy.check": "Check",
    "proxy.delete": "Delete",
    "proxy.delete_confirm": "Delete proxy?",
    "proxy.empty": "No proxies. Add some above.",
    // SettingsPanel
    "settings.title": "Settings",
    "settings.version": "Version",
    "settings.check_updates": "Check for updates",
    "settings.checking": "Checking…",
    "settings.update_available": "Update available",
    "settings.release_notes": "release notes",
    "settings.up_to_date": "You're up to date",
    "settings.no_update_server": "Could not reach update server.",
    "settings.theme": "Theme",
    "settings.theme_dark_only": "Dark (only theme in v1)",
    "settings.backend": "Backend",
    "settings.language": "Language",
  },
  ru: {
    "brand.version": "v0.7.0",
    "nav.profiles": "Профили",
    "nav.proxies": "Прокси",
    "nav.settings": "Настройки",
    "header.import": "Импорт",
    "header.lock": "Заблокировать",
    "import.password_prompt": "Пароль для импорта:",
    "login.loading": "Загрузка…",
    "login.title": "Genesis Browser",
    "login.create_hint":
      "Придумайте мастер-пароль (≥12 символов). Он шифрует все ваши данные — восстановить нельзя.",
    "login.unlock_hint": "Введите мастер-пароль для разблокировки.",
    "login.password_placeholder": "Мастер-пароль",
    "login.confirm_placeholder": "Повторите пароль",
    "login.working": "Подождите…",
    "login.create_button": "Создать и войти",
    "login.unlock_button": "Войти",
    "login.err_min_length": "пароль должен быть не короче 12 символов",
    "login.err_mismatch": "пароли не совпадают",
    "sidebar.profiles": "Профили",
    "sidebar.new": "+ Новый",
    "sidebar.filter": "Поиск…",
    "sidebar.no_profiles": "Профилей пока нет",
    "sidebar.no_matches": "Нет совпадений для",
    "sidebar.selected_n": "выбрано",
    "sidebar.delete": "Удалить",
    "sidebar.clear": "Сбросить",
    "sidebar.bulk_delete_confirm": "Удалить {n} профиль(ей)? Действие необратимо.",
    "sidebar.name_placeholder": "Название",
    "sidebar.create": "Создать",
    "sidebar.cancel": "Отмена",
    "sidebar.random_os": "Случайная ОС",
    "sidebar.locale_label": "Язык и часовой пояс, под которые маскируется профиль",
    "profile.empty": "Выберите профиль слева.",
    "profile.click_to_rename": "Нажмите чтобы переименовать",
    "profile.status_running": "запущен",
    "profile.notes": "Заметки",
    "profile.notes_placeholder": "Что-нибудь полезное про этот профиль…",
    "profile.tags": "Теги (через запятую)",
    "profile.tags_placeholder": "работа, реклама, тест",
    "profile.color": "Цвет",
    "profile.proxy": "Прокси",
    "profile.no_proxy": "Без прокси (WebRTC заблокирован)",
    "profile.extensions": "Расширения",
    "profile.install_xpi": "+ Установить .xpi",
    "profile.no_extensions": "Расширений нет.",
    "profile.remove": "Удалить",
    "profile.fingerprint_raw": "Отпечаток (raw)",
    "profile.stop": "Стоп",
    "profile.launch": "▶ Запустить",
    "profile.regenerate": "Перегенерировать",
    "profile.clone": "Клон",
    "profile.export": "Экспорт",
    "profile.delete": "Удалить",
    "profile.export_password_prompt": "Пароль для экспорта (≥12 символов):",
    "profile.delete_confirm":
      'Удалить профиль "{name}"? Вместе с ним удалятся все данные браузера.',
    "proxy.title": "Прокси",
    "proxy.add_one": "Добавить один",
    "proxy.label_optional": "Метка (необязательно)",
    "proxy.host": "хост",
    "proxy.port": "порт",
    "proxy.add_button": "Добавить прокси",
    "proxy.batch_import":
      "Пакетный импорт (одна строка = host:port или host:port:user:pass)",
    "proxy.import": "Импортировать",
    "proxy.col_label": "Метка",
    "proxy.col_endpoint": "Точка",
    "proxy.col_last_check": "Последняя проверка",
    "proxy.col_ip_geo": "IP / Гео",
    "proxy.last_check_never": "никогда",
    "proxy.check": "Проверить",
    "proxy.delete": "Удалить",
    "proxy.delete_confirm": "Удалить прокси?",
    "proxy.empty": "Прокси нет. Добавьте сверху.",
    "settings.title": "Настройки",
    "settings.version": "Версия",
    "settings.check_updates": "Проверить обновления",
    "settings.checking": "Проверка…",
    "settings.update_available": "Доступно обновление",
    "settings.release_notes": "что нового",
    "settings.up_to_date": "У вас актуальная версия",
    "settings.no_update_server": "Не удалось связаться с сервером обновлений.",
    "settings.theme": "Тема",
    "settings.theme_dark_only": "Тёмная (единственная в v1)",
    "settings.backend": "Бэкенд",
    "settings.language": "Язык",
  },
} as const;

type Key = keyof typeof DICT.en;

const LS_KEY = "pb_lang_v1";

function readLang(): Lang {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem(LS_KEY);
    if (v === "ru" || v === "en") return v;
  } catch {}
  // Fallback to browser language so first-time Russian users see Russian by default.
  const nav = typeof navigator !== "undefined" ? navigator.language : "";
  return nav.toLowerCase().startsWith("ru") ? "ru" : "en";
}

let currentLang: Lang = readLang();

export function getLang(): Lang {
  return currentLang;
}

export function setLang(l: Lang): void {
  currentLang = l;
  try {
    window.localStorage.setItem(LS_KEY, l);
  } catch {}
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("pb-lang-change"));
  }
}

export function t(key: Key, vars?: Record<string, string | number>): string {
  let s = (DICT[currentLang][key] ?? DICT.en[key] ?? key) as string;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
  }
  return s;
}

/** Hook that re-renders the component when setLang() is called. */
export function useLang(): Lang {
  const [l, setL] = useState<Lang>(currentLang);
  useEffect(() => {
    const handler = () => setL(currentLang);
    window.addEventListener("pb-lang-change", handler);
    // ensure SSR/hydration mismatch is reconciled
    setL(currentLang);
    return () => window.removeEventListener("pb-lang-change", handler);
  }, []);
  return l;
}
