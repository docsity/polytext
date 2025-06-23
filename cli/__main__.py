import typer
from pathlib import Path
import sys
import os

# Configurazione del percorso per gli import relativi
if getattr(sys, 'frozen', False):
    # Se l'applicazione è "frozen" (compilata con PyInstaller)
    application_path = os.path.dirname(sys.executable)
    project_root = os.path.dirname(application_path)
else:
    # Se l'applicazione è in esecuzione da script
    application_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(application_path))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from polytext.loader.html import HtmlLoader
except ImportError as e:
    typer.secho(f"Errore nell'importazione dei moduli polytext: {e}", fg=typer.colors.RED, err=True)
    sys.exit(1)

# Create Typer application instance
app = typer.Typer()

@app.command()
def process(
    input_source: str = typer.Argument(
        ...,
        help="Local input file path OR web page URL to process."
    ),
    output_path: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Path where to write the processing result."
    )
):
    """
    Process a local input file or URL and write the result to an output file.
    If input is a URL, use HtmlLoader to download and convert content to Markdown.
    Otherwise, treat input as a local file path (example logic).
    """
    typer.echo(f"Starting processing...")
    typer.echo(f"Input source: {input_source}")
    typer.echo(f"Output file: {output_path}")

    processed_content: str = ""

    try:
        # Check if input_source is a URL
        if input_source.lower().startswith("http://") or input_source.lower().startswith("https://"):
            typer.echo(f"Detected URL: {input_source}")
            typer.echo("Using HtmlLoader to download and convert content...")

            loader = HtmlLoader()
            result_dict = loader.get_text_from_url(input_source)

            if result_dict and "text" in result_dict and result_dict["text"] is not None:
                processed_content = result_dict["text"]
                typer.echo("HTML content successfully processed to Markdown using HtmlLoader.")
            else:
                typer.secho(f"Error: HtmlLoader failed to process URL {input_source} or returned empty result.", fg=typer.colors.RED, err=True)
                sys.exit(1)

        else:
            # Input is considered a local file path
            typer.echo(f"Detected local file path: {input_source}")
            input_file_path = Path(input_source)

            if not input_file_path.exists():
                typer.secho(f"Error: Local input file not found: {input_file_path}", fg=typer.colors.RED, err=True)
                sys.exit(1)
            if not input_file_path.is_file():
                typer.secho(f"Error: Local input path is not a file: {input_file_path}", fg=typer.colors.RED, err=True)
                sys.exit(1)
            if not input_file_path.stat().st_size > 0:
                 typer.secho(f"Warning: Local input file is empty: {input_file_path}", fg=typer.colors.YELLOW, err=True)

            try:
                content = input_file_path.read_text(encoding='utf-8')
                typer.echo("Local input file successfully read.")
                processed_content = f"Content read from local file '{input_file_path}':\n---\n{content}\n---"
                typer.echo("Local file processing (example) completed.")
            except Exception as e:
                typer.secho(f"Error reading or processing local file {input_file_path}: {e}", fg=typer.colors.RED, err=True)
                sys.exit(1)

        # Write processed content to output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(processed_content, encoding='utf-8')

        typer.secho(f"Result successfully written to: {output_path}", fg=typer.colors.GREEN)
        typer.echo("Processing completed.")

    except Exception as e:
        typer.secho(f"An unexpected error occurred during processing: {e}", fg=typer.colors.RED, err=True)
        sys.exit(1)

if __name__ == "__main__":
    app()