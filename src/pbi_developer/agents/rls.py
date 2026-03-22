"""RLS (Row-Level Security) agent — Step 8 of the pipeline.

Implements RLS rules based on natural language input and verified examples.
Generates DAX filter expressions for RLS roles and manages role assignments
via the Power BI REST API.

Workflow:
1. User describes RLS requirements in natural language
   e.g. "Managers should only see data for their department"
2. User provides verified examples:
   e.g. "User alice@company.com is in HR department, should see HR data only"
3. Agent generates DAX filter expressions for RLS roles
4. Agent validates against the examples
5. Outputs TMDL role definitions or REST API calls for assignment
"""

from __future__ import annotations

from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

RLS_SYSTEM_PROMPT = """\
You are a Power BI Row-Level Security (RLS) specialist. Given natural language
descriptions of security requirements and verified examples, you generate
correct DAX filter expressions for RLS roles.

RLS in Power BI works by applying DAX filter expressions to tables. When a
user belongs to a role, the filter expression is applied to restrict which
rows they can see.

Guidelines:
1. Use USERPRINCIPALNAME() to identify the current user
2. Use LOOKUPVALUE or RELATED to resolve user-to-entity mappings
3. Common patterns:
   - Department-based: [Department] = LOOKUPVALUE(UserMapping[Department], UserMapping[Email], USERPRINCIPALNAME())
   - Manager hierarchy: Use PATH functions for hierarchical security
   - Region-based: Filter on geography dimensions
   - Row-owner: [CreatedBy] = USERPRINCIPALNAME()
4. Always test the filter expression against the provided examples
5. Consider performance: prefer simple filters over complex ones
6. Handle edge cases: what if a user isn't in the mapping table?

Output:
- Role definitions with DAX filter expressions
- Validation results against provided examples
- Warnings about potential issues (unmapped users, performance, etc.)
"""

RLS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "roles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string"},
                    "description": {"type": "string"},
                    "table_permissions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string"},
                                "filter_expression": {"type": "string"},
                                "explanation": {"type": "string"},
                            },
                            "required": ["table", "filter_expression"],
                        },
                    },
                },
                "required": ["role_name", "table_permissions"],
            },
        },
        "validation_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "example_user": {"type": "string"},
                    "expected_access": {"type": "string"},
                    "filter_result": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "explanation": {"type": "string"},
                },
                "required": ["example_user", "expected_access", "passed"],
            },
        },
        "tmdl_output": {
            "type": "string",
            "description": "TMDL role definition that can be added to the semantic model",
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
        "member_assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string"},
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
    "required": ["roles", "validation_results"],
}


class RLSAgent(BaseAgent):
    """Generates and validates RLS rules from natural language + examples."""

    system_prompt = RLS_SYSTEM_PROMPT
    agent_name = "rls"

    def generate_rls(
        self,
        requirements: str,
        examples: list[dict[str, str]],
        model_metadata: str,
    ) -> dict[str, Any]:
        """Generate RLS roles from natural language requirements.

        Args:
            requirements: Natural language description of RLS needs.
                e.g. "Managers should only see data for employees in their department.
                      Executives should see all data."
            examples: Verified examples for validation. Each dict has:
                - user: email of the test user
                - expected: what they should see
                - should_not_see: what they should NOT see (optional)
                Example: [
                    {"user": "alice@co.com", "expected": "HR department data only"},
                    {"user": "bob@co.com", "expected": "Sales department data only"},
                    {"user": "ceo@co.com", "expected": "All departments"},
                ]
            model_metadata: Semantic model metadata as markdown.

        Returns:
            Dict with roles, DAX filters, validation results, and TMDL output.
        """
        import json

        examples_text = "\n".join(
            f"- **{ex['user']}**: should see {ex['expected']}"
            + (f" (should NOT see: {ex['should_not_see']})" if ex.get('should_not_see') else "")
            for ex in examples
        )

        prompt = (
            "Generate RLS (Row-Level Security) rules for this Power BI report.\n\n"
            f"## Requirements\n{requirements}\n\n"
            f"## Verified Examples\n{examples_text}\n\n"
            f"## Semantic Model\n{model_metadata}\n\n"
            "Generate:\n"
            "1. Role definitions with DAX filter expressions\n"
            "2. Validate each filter against the provided examples\n"
            "3. Generate TMDL role definition code\n"
            "4. List any warnings about edge cases or performance\n"
            "5. Suggest member assignments based on the examples"
        )

        logger.info(f"Generating RLS rules from {len(examples)} verified example(s)")
        result = self.call_structured(prompt, output_schema=RLS_OUTPUT_SCHEMA)

        # Log validation results
        validations = result.get("validation_results", [])
        passed = sum(1 for v in validations if v.get("passed"))
        failed = sum(1 for v in validations if not v.get("passed"))
        logger.info(f"RLS validation: {passed} passed, {failed} failed out of {len(validations)} examples")

        if failed > 0:
            logger.warning("Some RLS examples failed validation. Review the results carefully.")

        return result

    def apply_rls(
        self,
        rls_config: dict[str, Any],
        dataset_id: str,
    ) -> dict[str, Any]:
        """Apply RLS roles to a deployed dataset.

        This handles member assignment via the Power BI REST API.
        Role definitions must be applied via Tabular Editor or TMDL.

        Args:
            rls_config: Output from generate_rls().
            dataset_id: Target dataset ID in Power BI Service.

        Returns:
            Dict with assignment results.
        """
        results: list[dict[str, Any]] = []

        try:
            from pbi_developer.connectors.powerbi_rest import PowerBIClient
            client = PowerBIClient()

            for assignment in rls_config.get("member_assignments", []):
                role_name = assignment.get("role_name", "")
                for member in assignment.get("members", []):
                    try:
                        client.add_rls_member(dataset_id, role_name, member)
                        results.append({
                            "role": role_name,
                            "member": member,
                            "status": "assigned",
                        })
                    except Exception as e:
                        results.append({
                            "role": role_name,
                            "member": member,
                            "status": "failed",
                            "error": str(e),
                        })

        except Exception as e:
            logger.error(f"RLS assignment failed: {e}")
            results.append({"status": "error", "error": str(e)})

        return {"assignments": results}
