# Participant Folio Formula Sheet

## Core definitions

- `total_charged_cents`: sum of all `participant_item_allocations.amount_cents` for participant.
- `total_settled_cents`: sum of all non-reversed `participant_settlements.amount_cents` for participant.
- `total_repaid_cents`: sum of all non-reversed `participant_repayments.amount_cents` for participant.
- `net_balance_cents = total_charged_cents - total_settled_cents + total_repaid_cents`.
- `overpayment_cents = max(-net_balance_cents, 0)`.

## Status mapping

- `owes_you` when `net_balance_cents > 0`.
- `settled` when `net_balance_cents = 0`.
- `you_owe_them` when `net_balance_cents < 0`.

## Event delta rules

- Charge event delta: `+amount_cents` to net balance.
- Settlement event delta: `-amount_cents` to net balance.
- Repayment event delta: `+amount_cents` to net balance.
- Event fields:
  - `previous_net_balance_cents`
  - `amount_cents`
  - `new_net_balance_cents = previous_net_balance_cents + delta`

## Worked examples (5)

1. Charged `1000`, settled `400`
   - `net = 1000 - 400 = 600`
   - `status = owes_you`
   - `overpayment = 0`

2. Charged `1000`, settled `1000`
   - `net = 0`
   - `status = settled`
   - `overpayment = 0`

3. Charged `1000`, settled `1300`
   - `net = -300`
   - `status = you_owe_them`
   - `overpayment = 300`

4. Settlement entry transition (exact paydown)
   - previous net `1000`, settlement amount `1000`
   - new net `0`
   - overpayment happened: `false`

5. Overpayment then repayment
   - previous net `200`, settlement amount `500`
   - new net `-300`
   - repayment amount `200`
   - final net `-100`
   - remaining overpayment `100`
