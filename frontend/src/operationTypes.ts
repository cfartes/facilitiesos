export type OperationPage =
  "assets" | "categories" | "occurrences" | "orders" | "notifications";
export type Place = {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  unit_id: string;
  is_active: boolean;
};
export type Category = {
  id: string;
  name: string;
  is_active: boolean;
  version: number;
};
export type Asset = {
  id: string;
  unit_id: string;
  location_id: string;
  name: string;
  code: string;
  category: string;
  criticality: string;
  status: string;
  version: number;
};
export type Person = {
  id: string;
  name: string;
  roles: string[];
  all_units: boolean;
  unit_ids: string[];
};
export type Meta = {
  locations: Place[];
  categories: Category[];
  assets: Asset[];
  people: Person[];
  can_coordinate: boolean;
  can_review: boolean;
  can_report: boolean;
  viewer_id: string | null;
};
export type Occurrence = {
  id: string;
  code: string;
  title: string;
  description: string;
  unit_id: string;
  location_id: string;
  category_id: string;
  asset_id: string | null;
  requester_id: string;
  requester_name: string;
  location_name: string;
  category_name: string;
  asset_name: string | null;
  order_id: string | null;
  order_code: string | null;
  order_state: string | null;
  outcome: string;
  created_at: string;
  first_response_at: string | null;
  solution: string | null;
  evidence: string | null;
  cycle: number | null;
  version: number;
};
export type WorkOrder = {
  id: string;
  code: string;
  title: string;
  description: string;
  unit_id: string;
  location_id: string;
  category_id: string;
  asset_id: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  location_name: string;
  category_name: string;
  asset_name: string | null;
  state: string;
  impact: number;
  urgency: number;
  priority: string;
  solution: string;
  evidence: string;
  cycle: number;
  version: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
};
export type OrderDetail = {
  order: WorkOrder;
  occurrences: Occurrence[];
  messages: {
    id: string;
    actor_name: string;
    body: string;
    visibility: string;
    created_at: string;
  }[];
  events: {
    id: string;
    actor_name: string;
    action: string;
    note: string;
    cycle: number;
    created_at: string;
  }[];
  can_coordinate: boolean;
  can_execute: boolean;
  can_internal: boolean;
  can_message: boolean;
};
export type Notification = {
  id: string;
  title: string;
  order_id: string | null;
  occurrence_id: string | null;
  created_at: string;
  read_at: string | null;
};

export const states: Record<string, string> = {
  triage: "Em triagem",
  assigned: "Atribuída",
  in_progress: "Em execução",
  waiting: "Aguardando",
  resolved: "Resolvida",
  closed: "Concluída",
  cancelled: "Cancelada",
};
export const outcomes: Record<string, string> = {
  open: "Aguardando triagem",
  linked: "Em atendimento",
  confirmed: "Solução confirmada",
  contested: "Solução contestada",
  cancelled: "Cancelada",
};
export const priorities: Record<string, string> = {
  low: "Baixa",
  medium: "Média",
  high: "Alta",
  critical: "Crítica",
};
export const assetStates: Record<string, string> = {
  active: "Em operação",
  out_of_service: "Fora de serviço",
  retired: "Desativado",
};
export const actionNames: Record<string, string> = {
  "attachment.added": "Imagem adicionada",
  "attachment.removed": "Imagem removida",
  "attachment.downloaded": "Imagem consultada",
  "order.created": "Ordem criada",
  "occurrence.linked": "Relato vinculado",
  "order.assigned": "Responsável atualizado",
  "order.start": "Execução iniciada",
  "order.wait": "Espera registrada",
  "order.resolve": "Solução apresentada",
  "order.close": "Atendimento concluído",
  "order.reopen": "Atendimento reaberto",
  "order.cancel": "Atendimento cancelado",
  "occurrence.confirmed": "Solução confirmada",
  "occurrence.contested": "Solução contestada e atendimento reaberto",
};
export const dateTime = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
export function placeName(meta: Meta, id: string): string {
  const place = meta.locations.find((item) => item.id === id);
  return !place
    ? "Local indisponível"
    : place.parent_id
      ? placeName(meta, place.parent_id) + " / " + place.name
      : place.name;
}
export const availablePeople = (meta: Meta, unit: string, technician = false) =>
  meta.people.filter(
    (person) =>
      (person.all_units || person.unit_ids.includes(unit)) &&
      (!technician ||
        person.roles.some((role) =>
          ["technician", "supervisor", "company_admin"].includes(role),
        )),
  );
