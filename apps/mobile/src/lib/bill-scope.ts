export interface UserBillScope {
  periferiaId: number | null;
  dimosId: number | null;
}

export interface BillScopeQuery {
  governance?: string;
  periferia_id?: number;
  dimos_id?: number;
  include_institutional: false;
}

export function scopedBillQuery(scope: UserBillScope): BillScopeQuery {
  if (scope.periferiaId !== null) {
    return {
      periferia_id: scope.periferiaId,
      ...(scope.dimosId !== null ? { dimos_id: scope.dimosId } : {}),
      include_institutional: false,
    };
  }
  return { governance: "NATIONAL", include_institutional: false };
}

export function availableGeographicFilters(scope: UserBillScope): string[] {
  const filters: string[] = [];
  if (scope.periferiaId !== null) filters.push("REGIONAL");
  if (scope.dimosId !== null) filters.push("MUNICIPAL");
  return filters;
}
