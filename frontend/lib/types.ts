export type ProfileStatus = "new" | "ready" | "running" | "suspended" | "error";

export interface Profile {
  id: string;
  name: string;
  notes: string | null;
  tags: string[];
  color: string | null;
  created_at: number;
  updated_at: number;
  last_opened_at: number | null;
  open_count: number;
  status: ProfileStatus;
  fingerprint: any;
  proxy_id: string | null;
  user_data_dir: string;
  total_sessions: number;
  total_duration_sec: number;
}

export type ProxyType = "http" | "https" | "socks5";

export interface Proxy {
  id: string;
  label: string;
  type: ProxyType;
  host: string;
  port: number;
  username: string | null;
  password: string | null;
  tags: string[];
  notes: string | null;
  created_at: number;
  updated_at: number;
  last_checked_at: number | null;
  last_check_ok: boolean;
  last_ip: string | null;
  last_country: string | null;
  last_city: string | null;
  last_timezone: string | null;
  last_latency_ms: number | null;
}

export interface HealthCheckResult {
  ok: boolean;
  ip: string | null;
  country: string | null;
  city: string | null;
  timezone: string | null;
  latency_ms: number | null;
  error: string | null;
}
