import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { StructuredApiError } from '../../../lib/api';

export function isAccessLoss(error: unknown) {
  return error instanceof StructuredApiError && [401, 403, 404].includes(error.status);
}

export function useClearOnAccessLoss(key: readonly unknown[], errors: unknown[]) {
  const client = useQueryClient();
  const lost = errors.some(isAccessLoss);
  useEffect(() => { if (lost) client.removeQueries({ queryKey: key }); }, [client, lost, ...key]);
  return lost;
}
