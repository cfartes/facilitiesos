export type User = {
  email: string;
  role: "superadmin" | "company_user";
  name?: string;
  company_id?: string | null;
  roles?: string[];
  unit_ids?: string[];
  all_units?: boolean;
};

export type Company = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  version: number;
  created_at: string;
};
export type Location = {
  id: string;
  company_id: string;
  unit_id: string;
  parent_id: string | null;
  kind: "unit" | "building" | "floor" | "environment";
  name: string;
  criticality: string;
  timezone: string;
  is_active: boolean;
  version: number;
};
export type Member = {
  id: string;
  company_id: string;
  name: string;
  email: string;
  roles: string[];
  unit_ids: string[];
  all_units: boolean;
  is_active: boolean;
  version: number;
  invitation_pending: boolean;
};
export type Invitation = { url: string; expires_in_hours: number };
