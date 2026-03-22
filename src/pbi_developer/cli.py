"""CLI entry point for pbi-dev tool."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="pbi-dev",
    help="AI-powered Power BI developer tool using Claude Sonnet.",
    no_args_is_help=True,
)
console = Console()

STAGE_LABELS: dict[str, str] = {
    "ingestion": "Ingesting requirements",
    "model_connection": "Loading semantic model",
    "wireframe": "Designing wireframe",
    "field_mapping": "Mapping fields",
    "qa": "Validating (QA)",
    "pbir_generation": "Generating PBIR",
    "publishing": "Publishing",
    "rls": "RLS configuration",
}


def _version_callback(value: bool) -> None:
    if value:
        from pbi_developer import __version__

        console.print(f"pbi-dev {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """AI-powered Power BI developer tool using Claude Sonnet."""


@app.command()
def generate(
    brief: Path = typer.Option(None, "--brief", "-b", help="Path to text brief / requirements file"),
    pptx: Path = typer.Option(None, "--pptx", "-p", help="Path to PowerPoint mockup"),
    video: Path = typer.Option(None, "--video", "-v", help="Path to screen recording"),
    image: Path = typer.Option(None, "--image", "-i", help="Path to screenshot/mockup image"),
    model_metadata: Path = typer.Option(
        None, "--model-metadata", "-m", help="Path to model_metadata.md (dry run mode)"
    ),
    style_template: Path = typer.Option(
        None, "--style", "-s", help="Path to style template (JSON, PBIR folder, or theme)"
    ),
    output_dir: Path = typer.Option("./output", "--output", "-o", help="Output directory for PBIR files"),
    report_name: str = typer.Option("Report", "--name", "-n", help="Report name"),
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Dry run (no live connections)"),
    verbose: bool = typer.Option(False, "--verbose", help="Show token usage per stage"),
) -> None:
    """Full pipeline: input -> wireframe -> PBIR report."""
    from pbi_developer.pipeline.orchestrator import run_pipeline

    console.print("[bold]Starting AI Power BI Developer pipeline[/bold]\n")

    inputs = {
        "brief": brief,
        "pptx": pptx,
        "video": video,
        "image": image,
        "model_metadata": model_metadata,
        "style_template": style_template,
    }
    # Remove None values
    inputs = {k: v for k, v in inputs.items() if v is not None}

    if not inputs:
        console.print("[red]Error: At least one input is required (--brief, --pptx, --video, --image)[/red]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting pipeline...", total=8)

        def on_progress(stage: str, status: str) -> None:
            label = STAGE_LABELS.get(stage, stage)
            if status == "running":
                progress.update(task, description=f"[cyan]{label}...[/cyan]")
            elif status == "completed":
                progress.advance(task)
                progress.update(task, description=f"[green]{label} done[/green]")

        result = run_pipeline(
            inputs=inputs,
            output_dir=output_dir,
            report_name=report_name,
            dry_run=dry_run,
            progress_callback=on_progress,
        )

    if result.success:
        console.print(f"\n[green]Report generated successfully at: {result.output_path}[/green]")
        if verbose and result.state:
            total = result.state.total_tokens
            console.print(f"[dim]Tokens: in={total['input_tokens']} out={total['output_tokens']}[/dim]")
    else:
        console.print(f"\n[red]Pipeline failed: {result.error}[/red]")
        raise typer.Exit(1)


@app.command()
def wireframe(
    brief: Path = typer.Option(None, "--brief", "-b", help="Path to text brief"),
    pptx: Path = typer.Option(None, "--pptx", "-p", help="Path to PowerPoint mockup"),
    video: Path = typer.Option(None, "--video", "-v", help="Path to screen recording"),
    image: Path = typer.Option(None, "--image", "-i", help="Path to screenshot image"),
    output: Path = typer.Option("./wireframe.json", "--output", "-o", help="Output wireframe JSON"),
) -> None:
    """Generate wireframe only from inputs."""
    from pbi_developer.pipeline.orchestrator import run_wireframe_only

    console.print("[bold]Generating wireframe...[/bold]")
    inputs = {k: v for k, v in {"brief": brief, "pptx": pptx, "video": video, "image": image}.items() if v}

    if not inputs:
        console.print("[red]Error: At least one input required[/red]")
        raise typer.Exit(1)

    result = run_wireframe_only(inputs=inputs, output_path=output)
    if result:
        console.print(f"[green]Wireframe saved to: {output}[/green]")
    else:
        console.print("[red]Wireframe generation failed[/red]")
        raise typer.Exit(1)


@app.command()
def style_extract(
    source: Path = typer.Argument(..., help="Path to PBIR folder, JSON template, or theme file"),
    output: Path = typer.Option("./style.json", "--output", "-o", help="Output style JSON"),
) -> None:
    """Extract visual style from existing dashboard/template."""
    from pbi_developer.pbir.theme import (
        extract_style_from_json,
        extract_style_from_pbir,
        extract_style_from_theme,
    )
    from pbi_developer.utils.files import write_json

    console.print(f"[bold]Extracting style from: {source}[/bold]")

    if source.is_dir():
        style = extract_style_from_pbir(source)
    elif source.suffix == ".json":
        # Try as theme first, fall back to template
        try:
            style = extract_style_from_theme(source)
        except Exception:
            style = extract_style_from_json(source)
    else:
        console.print("[red]Unsupported source format. Use PBIR folder, .json template, or theme file.[/red]")
        raise typer.Exit(1)

    write_json(output, style.model_dump())
    console.print(f"[green]Style extracted to: {output}[/green]")


@app.command()
def validate(
    report_dir: Path = typer.Argument(..., help="Path to .Report PBIR folder"),
) -> None:
    """Validate PBIR output against schemas."""
    from pbi_developer.pbir.validator import validate_pbir_folder

    console.print(f"[bold]Validating: {report_dir}[/bold]")
    result = validate_pbir_folder(report_dir)

    table = Table(title="Validation Results")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    table.add_row("Files checked", str(result.files_checked))
    table.add_row(
        "Valid" if result.valid else "INVALID",
        "[green]All checks passed[/green]" if result.valid else f"[red]{len(result.errors)} error(s)[/red]",
    )

    console.print(table)

    for err in result.errors:
        console.print(f"  [red]ERROR:[/red] {err}")
    for warn in result.warnings:
        console.print(f"  [yellow]WARN:[/yellow] {warn}")

    if not result.valid:
        raise typer.Exit(1)


@app.command()
def deploy(
    report_dir: Path = typer.Argument(..., help="Path to PBIR .Report folder"),
    workspace_id: str | None = typer.Option(None, "--workspace", "-w", help="Target workspace ID"),
    stage: str = typer.Option("dev", "--stage", help="Deployment stage (dev/test/prod)"),
) -> None:
    """Deploy report to Power BI Service."""
    from pbi_developer.deployment.deployer import deploy_report

    console.print(f"[bold]Deploying to {stage}...[/bold]")
    result = deploy_report(report_dir, workspace_id=workspace_id, stage=stage)
    if result.success:
        console.print(f"[green]Deployed successfully to {stage}[/green]")
    else:
        console.print(f"[red]Deployment failed: {result.error}[/red]")
        raise typer.Exit(1)


@app.command()
def test(
    report_dir: Path = typer.Argument(..., help="Path to PBIR .Report folder"),
    model_metadata: Path = typer.Option(None, "--model-metadata", "-m", help="Path to model_metadata.md"),
) -> None:
    """Run DAX tests and schema validation."""
    from pbi_developer.deployment.tester import run_tests

    console.print("[bold]Running tests...[/bold]")
    result = run_tests(report_dir, model_metadata_path=model_metadata)

    for test_result in result.results:
        status = "[green]PASS[/green]" if test_result.passed else "[red]FAIL[/red]"
        console.print(f"  {status} {test_result.name}: {test_result.message}")

    if not result.all_passed:
        console.print(f"\n[red]{result.failed_count} test(s) failed[/red]")
        raise typer.Exit(1)
    console.print(f"\n[green]All {result.passed_count} test(s) passed[/green]")


@app.command()
def connect(
    target: str = typer.Argument("powerbi", help="Connection target: powerbi, snowflake, or xmla"),
) -> None:
    """Test connection to Power BI, Snowflake, or XMLA endpoint."""
    from pbi_developer.connectors.auth import test_connection

    console.print(f"[bold]Testing {target} connection...[/bold]")
    success, message = test_connection(target)
    if success:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(1)


@app.command()
def rls(
    requirements: str = typer.Option(..., "--requirements", "-r", help="Natural language RLS requirements"),
    examples_file: Path = typer.Option(..., "--examples", "-e", help="JSON file with verified user examples"),
    model_metadata: Path = typer.Option(..., "--model-metadata", "-m", help="Path to model_metadata.md"),
    output: Path = typer.Option("./rls_config.json", "--output", "-o", help="Output RLS config JSON"),
    dataset_id: str | None = typer.Option(None, "--dataset-id", help="Dataset ID for live RLS assignment"),
) -> None:
    """Generate RLS rules from natural language + verified examples.

    Examples file format (JSON):
    [
        {"user": "alice@company.com", "expected": "HR department data only"},
        {"user": "bob@company.com", "expected": "Sales data only"},
        {"user": "ceo@company.com", "expected": "All departments"}
    ]
    """
    import json

    from pbi_developer.agents.rls import RLSAgent
    from pbi_developer.utils.files import write_json

    console.print("[bold]Generating RLS configuration...[/bold]")

    # Load examples
    with open(examples_file) as f:
        examples = json.load(f)

    # Load model metadata
    metadata_text = model_metadata.read_text(encoding="utf-8")

    # Generate RLS
    agent = RLSAgent()
    result = agent.generate_rls(requirements, examples, metadata_text)

    # Display results
    console.print(f"\n[bold]Generated {len(result.get('roles', []))} RLS role(s)[/bold]")
    for role in result.get("roles", []):
        console.print(f"  Role: [cyan]{role['role_name']}[/cyan]")
        for perm in role.get("table_permissions", []):
            console.print(f"    Table: {perm['table']}")
            console.print(f"    Filter: {perm['filter_expression']}")

    # Show validation
    console.print("\n[bold]Validation against examples:[/bold]")
    for v in result.get("validation_results", []):
        status = "[green]PASS[/green]" if v.get("passed") else "[red]FAIL[/red]"
        console.print(f"  {status} {v.get('example_user', '')}: {v.get('explanation', '')}")

    # Show TMDL output
    tmdl = result.get("tmdl_output", "")
    if tmdl:
        console.print("\n[bold]TMDL Role Definition:[/bold]")
        console.print(f"[dim]{tmdl}[/dim]")

    # Show warnings
    for w in result.get("warnings", []):
        console.print(f"  [yellow]WARNING:[/yellow] {w}")

    # Save config
    write_json(output, result)
    console.print(f"\n[green]RLS config saved to: {output}[/green]")

    # Apply if dataset ID provided
    if dataset_id:
        console.print(f"\n[bold]Applying RLS to dataset {dataset_id}...[/bold]")
        apply_result = agent.apply_rls(result, dataset_id)
        for a in apply_result.get("assignments", []):
            status = "[green]OK[/green]" if a.get("status") == "assigned" else f"[red]{a.get('error', 'failed')}[/red]"
            console.print(f"  {status} {a.get('member', '')} -> {a.get('role', '')}")


if __name__ == "__main__":
    app()
