"""CLI entry point for adversarial-wiki."""

import click
from dotenv import load_dotenv

from adversarial_wiki.utils import init_topic_dirs, get_topic_dir
from adversarial_wiki.compiler import compile_wiki
from adversarial_wiki.research import run_research
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

    topic_dir = init_topic_dirs(topic, mode)
    click.echo(f"Initialized topic directory: {topic_dir}")

    if mode == "manual":
        pro_raw = topic_dir / "raw" / "pro"
        con_raw = topic_dir / "raw" / "con"
        pro_files = list(pro_raw.iterdir()) if pro_raw.exists() else []
        con_files = list(con_raw.iterdir()) if con_raw.exists() else []

        if not pro_files and not con_files:
            click.echo(f"No source files found. Add files to:\n  {pro_raw}\n  {con_raw}")
            return

        click.echo(f"Compiling wiki from {len(pro_files)} pro source(s) and {len(con_files)} con source(s)...")
        pro_sources = [f.read_text(encoding="utf-8", errors="ignore") for f in pro_files if f.is_file()]
        con_sources = [f.read_text(encoding="utf-8", errors="ignore") for f in con_files if f.is_file()]
        compile_wiki(topic, "pro", pro_sources, topic_dir)
        compile_wiki(topic, "con", con_sources, topic_dir)

    elif mode == "auto":
        click.echo(f"Running auto research for topic: {topic}")
        run_research(topic, pro_stance, con_stance, topic_dir)

    click.echo("Done.")


@cli.command()
@click.option("--topic", required=True, help="Topic name.")
@click.option("--question", required=True, help="Question to debate.")
def debate(topic, question):
    """Ask a question and get a structured debate with hidden assumption surfacing."""
    topic_dir = get_topic_dir(topic)

    if not (topic_dir / "wiki" / "pro" / "index.md").exists() or \
       not (topic_dir / "wiki" / "con" / "index.md").exists():
        raise click.ClickException(
            f"Wiki not compiled for topic '{topic}'. Run `compile` first."
        )

    run_debate(topic, question, topic_dir)


@cli.command()
@click.option("--topic", required=True, help="Topic name.")
def lint(topic):
    """Run health checks on the compiled wikis for a topic."""
    topic_dir = get_topic_dir(topic)

    if not topic_dir.exists():
        raise click.ClickException(f"Topic '{topic}' not found.")

    passed = run_lint(topic, topic_dir)
    raise SystemExit(0 if passed else 1)
