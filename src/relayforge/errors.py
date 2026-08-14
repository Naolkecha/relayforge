"""Typed application exceptions converted to stable API errors at the boundary."""

from __future__ import annotations


class RelayForgeError(Exception):
    code = "relayforge_error"
    status_code = 500


class ValidationError(RelayForgeError):
    code = "validation_error"
    status_code = 422


class AuthenticationError(RelayForgeError):
    code = "authentication_error"
    status_code = 401


class AuthorizationError(RelayForgeError):
    code = "authorization_error"
    status_code = 403


class NotFoundError(RelayForgeError):
    code = "not_found"
    status_code = 404


class ConflictError(RelayForgeError):
    code = "conflict"
    status_code = 409


class WorkflowDefinitionError(ValidationError):
    code = "invalid_workflow_definition"


class WorkflowExecutionError(RelayForgeError):
    code = "workflow_execution_failed"
    status_code = 422


class SecurityPolicyError(RelayForgeError):
    code = "security_policy_violation"
    status_code = 400


class UpstreamServiceError(RelayForgeError):
    code = "upstream_service_error"
    status_code = 502
