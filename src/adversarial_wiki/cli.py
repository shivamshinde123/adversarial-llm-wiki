"""CLI entry point for adversarial-wiki."""

import click
from dotenv import load_dotenv

from adversarial_wiki.utils import init_topic_dirs, get_topic_dir
from adversarial_wiki.compiler import compile_wiki
from adversarial_wiki.research import run_research
from adversarial_wiki.sources import read_sources_from_dir
from adversarial_wiki.debate import run_debate
from adversarial_wiki.lint import run_lint

load_dotenv()


@click.group()
def cli():
    """Adversarial Wiki — two opposing knowledge bases that debate each other."""


@cli.command()
@click.option("--topic", required=True, help="Topic name (used as folder name).")
@click.option("--manual", "mode", flag_value="manual", help="Compile from files in raw/pro and raw/con.")
@click.option("--auto", "mode", flag_value="auto", help="Autonomously research and compile wikis.")
@click.option("--pro", "pro_stance", default=None, help="Custom pro stance description (auto mode only).")
@click.option("--con", "con_stance", default=None, help="Custom con stance description (auto mode only).")
def compile(topic, mode, pro_stance, con_stance):
    """Compile two opposing wikis for a topic."""
    if not mode:
        raise click.UsageError("Specify either --manual or --auto.")

    try:
        topic_dir = init_topic_dirs(topic, mode)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="'--topic'")
    click.echo(f"Initialized topic directory: {topic_dir}")

    if mode == "manual":
        pro_raw = topic_dir / "raw" / "pro"
        con_raw = topic_dir / "raw" / "con"

        pro_sources = read_sources_from_dir(pro_raw)
        con_sources = read_sources_from_dir(con_raw)

        if not pro_sources and not con_sources:
            click.echo(f"No source files found. Add files to:\n  {pro_raw}\n  {con_raw}")
            return

        click.echo(f"Compiling wiki from {len(pro_sources)} pro source(s) and {len(con_sources)} con source(s)...")
        if pro_sources:
            compile_wiki(topic, "pro", pro_sources, topic_dir)
        else:
            click.echo(f"Skipping pro wiki: no source files found in {pro_raw}")

        if con_sources:
            compile_wiki(topic, "con", con_sources, topic_dir)
        else:
            click.echo(f"Skipping con wiki: no source files found in {con_raw}")

    elif mode == "auto":
        click.echo(f"Running auto research for topic: {topic}")
        try:
            run_research(topic, pro_stance, con_stance, topic_dir)
        except NotImplementedError:
            raise click.ClickException("Auto research is not implemented yet (coming in Stage 3).")

    click.echo("Done.")


@cli.command()
@click.option("--topic", required=True, help="Topic name.")
@click.option("--question", required=True, help="Question to debate.")
def debate(topic, question):
    """Ask a question and get a structured debate with hidden assumption surfacing."""
    try:
        topic_dir = get_topic_dir(topic)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="'--topic'")

    if not (topic_dir / "wiki" / "pro" / "index.md").exists() or \
       not (topic_dir / "wiki" / "con" / "index.md").exists():
        raise click.ClickException(
            f"Wiki not compiled for topic '{topic}'. Run `compile` first."
        )

    try:
        run_debate(topic, question, topic_dir)
    except NotImplementedError:
        raise click.ClickException("The debate command is not implemented yet (coming in Stage 4).")


@cli.command()
@click.option("--topic", required=True, help="Topic name.")
def lint(topic):
    """Run health checks on the compiled wikis for a topic."""
    try:
        topic_dir = get_topic_dir(topic)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="'--topic'")

    if not topic_dir.exists():
        raise click.ClickException(f"Topic '{topic}' not found.")

    try:
        passed = run_lint(topic, topic_dir)
    except NotImplementedError:
        raise click.ClickException("The lint command is not implemented yet (coming in Stage 6).")
    raise SystemExit(0 if passed else 1)
