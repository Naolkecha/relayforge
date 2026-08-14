# API examples

Assume:

```bash
BASE_URL=http://localhost:8000
```

## Register

```bash
curl -sS -X POST "$BASE_URL/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "owner@example.com",
    "password": "a-long-development-password",
    "organization_name": "Example Company"
  }'
```

Save the returned `access_token` as `ACCESS_TOKEN`.

## Login

```bash
curl -sS -X POST "$BASE_URL/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "owner@example.com",
    "password": "a-long-development-password"
  }'
```

When a user eventually belongs to multiple organizations, callers may provide `organization_id` to select the
membership context.

## Refresh

```bash
curl -sS -X POST "$BASE_URL/v1/auth/refresh" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
```

## Create a transform workflow

```bash
curl -sS -X POST "$BASE_URL/v1/workflows" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Normalize order",
    "steps": [
      {
        "id": "normalize",
        "name": "Normalize order fields",
        "type": "transform",
        "mapping": {
          "order_id": "$input.order.id",
          "customer_id": "$input.order.customer_id",
          "currency": "$input.order.currency",
          "pipeline": "relayforge"
        }
      }
    ]
  }'
```

## Create a multi-step workflow

```json
{
  "name": "Eligibility and callback",
  "description": "Checks an input score and posts a callback",
  "steps": [
    {
      "id": "shape",
      "name": "Shape callback payload",
      "type": "transform",
      "mapping": {
        "account_id": "$input.account.id",
        "score": "$input.account.score"
      }
    },
    {
      "id": "eligible",
      "name": "Check threshold",
      "type": "condition",
      "depends_on": ["shape"],
      "source": "$steps.shape.score",
      "operator": "gte",
      "value": 700
    },
    {
      "id": "callback",
      "name": "Notify downstream",
      "type": "http",
      "depends_on": ["eligible"],
      "method": "POST",
      "url": "https://api.example.com/callbacks",
      "headers": {
        "X-Account-ID": "$steps.shape.account_id"
      },
      "json_body": {
        "account_id": "$steps.shape.account_id",
        "eligible": "$steps.eligible.result"
      },
      "expected_statuses": [200, 202],
      "retry": {
        "max_attempts": 3,
        "initial_delay_seconds": 0.5,
        "multiplier": 2,
        "max_delay_seconds": 5
      }
    }
  ]
}
```

The current engine uses dependencies for ordering, not conditional branching. A condition step produces
`{"result": true|false}`; later steps decide how to use that value. Conditional skip edges are a future feature.

## Execute

```bash
curl -sS -X POST "$BASE_URL/v1/workflows/$WORKFLOW_ID/execute" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-1001-normalization' \
  -d '{
    "input": {
      "order": {
        "id": 1001,
        "customer_id": 88,
        "currency": "ETB"
      }
    }
  }'
```

## Error shape

Application errors use a stable envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "workflow not found",
    "request_id": "8a7f..."
  }
}
```

The request ID is also returned in the `X-Request-ID` response header.
