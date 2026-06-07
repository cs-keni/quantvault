export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  default_portfolio_id: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
