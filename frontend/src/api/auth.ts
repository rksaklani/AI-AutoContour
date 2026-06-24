import { api } from "@/lib/apiClient";
import type { TokenPair, User } from "@/types";

export async function login(email: string, password: string): Promise<TokenPair> {
  // OAuth2 password flow expects form-encoded `username` + `password`.
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  const { data } = await api.post<TokenPair>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function register(
  email: string,
  password: string,
  full_name: string,
): Promise<User> {
  const { data } = await api.post<User>("/auth/register", { email, password, full_name });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}
