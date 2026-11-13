import { useEffect } from 'react';
import { useStableKey } from '../../../lib/useStableKey';
import { useQueryClient } from '@tanstack/react-query';
import { StructuredApiError } from '../../../lib/api';

export function isAccessLoss(error: unknown) {
  return error instanceof StructuredApiError && [401, 403, 404].includes(error.status);
}

export function useClearOnAccessLoss(unstableKey: readonly unknown[], errors: unknown[]) {
  const key = useStableKey(unstableKey);
  const client = useQueryClient();
  const lost = errors.some(isAccessLoss);
  useEffect(() => { if (lost) client.removeQueries({ queryKey: key }); }, [client, lost, key]);
  return lost;
}
