import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { AddonOnlyShop } from './AddonOnlyShop';

const { quoteOrder, placeOrder, publicEvent } = vi.hoisted(() => ({
  quoteOrder: vi.fn(), placeOrder: vi.fn(), publicEvent: { approval: true },
}));
vi.mock('../../../lib/api', async original => ({
  ...(await original<typeof import('../../../lib/api')>()),
  tenantPublicRequest: vi.fn(async () => ({ registration_requires_approval: publicEvent.approval })),
}));
vi.mock('./ticketingApi', async original => ({
  ...(await original<typeof import('./ticketingApi')>()),
  fetchShop: vi.fn(async () => ({ event_id: 42, orders_enabled: true, currency: 'inr', ticket_types: [], booking_fee_fixed: '0',
    booking_fee_bps: 0, max_tickets_per_order: 10, promo_codes_enabled: false,
    policy: { text: 'Refunds by staff decision.', overridden: false, terms: null },
    addons: [{ id: 7, name: 'Event T-shirt', description: '', kind: 'merch', amount: '500.00', per_order_limit: 2, sold_out: false, variants: [] }] })),
  quoteOrder, placeOrder,
}));

function renderShop() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AddonOnlyShop makerspaceSlug="lab" makerspaceId={9} publicToken="t"
    ordersHref={id => `/member/orders/${id}`} /></QueryClientProvider>);
}

describe('add-ons for a confirmed place (G9)', () => {
  it('quotes an add-on-only order: no tickets, no seat, no attendees', async () => {
    publicEvent.approval = true;
    quoteOrder.mockResolvedValue({ quote: { currency: 'inr', lines: [], subtotal: '500.00', discount_total: '0', total: '500.00', digest: 'd' },
      promo_saving: null, seats: 0, policy: { text: '', overridden: false, terms: null } });
    renderShop();
    await screen.findByRole('heading', { name: /Add-ons for your place/ });
    fireEvent.click(screen.getByRole('button', { name: 'More Event T-shirt' }));
    fireEvent.click(screen.getByRole('button', { name: 'Review add-ons' }));
    await waitFor(() => expect(quoteOrder).toHaveBeenCalledWith(9, 42, expect.objectContaining({
      tickets: [], addons: [{ addon_id: 7, variant_id: null, quantity: 1 }], buyer_attends: false, attendees: [] })));
  });

  it('shows nothing on an event without registration review (the ordinary shop sells add-ons there)', async () => {
    publicEvent.approval = false;
    const { container } = renderShop();
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
