from __future__ import annotations

import typer

app = typer.Typer(
    name="archkg",
    help="ArchReview-KG: civil-architecture drawing review CLI.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """ArchReview-KG."""


@app.command()
def version() -> None:
    """Print archkg version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        typer.echo(_v("archkg"))
    except PackageNotFoundError:
        typer.echo("0.0.1")


if __name__ == "__main__":
    app()
