# polytext_cli.py
import typer
from pathlib import Path
import json # For JSON output
import os
import sys

# --- PyInstaller: START ---
# This block handles path adjustments when running as a bundled executable.
# It ensures that external binaries (like ffmpeg) included with --add-binary
# are found at runtime.
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    # Add the bundled ffmpeg directory to the system's PATH
    os.environ['PATH'] += os.pathsep + os.path.join(bundle_dir, 'ffmpeg')
# --- PyInstaller: END ---

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

# Aggiungi la directory principale del progetto al sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import BaseLoader instead of specific loaders for the main command logic
from polytext.loader import BaseLoader
from polytext.exceptions import EmptyDocument, ConversionError

# Create an instance of the Typer application
app = typer.Typer()

@app.command()
def process(
    input_source: str = typer.Argument(
        ...,
        help="Path to the local input file OR URL of the web page/YouTube video to process."
    ),
    output_path: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Path where to write the processing result as JSON."
    ),
    timeout: int = typer.Option(
        300,
        "--timeout",
        "-t",
        help="Timeout for processing operations in seconds. Defaults to 300 (5 minutes)."
    )
):
    """
    Processes a local input file or a URL using BaseLoader
    and writes the result as JSON to an output file.
    """
    typer.echo("Starting processing...")
    typer.echo(f"Input source: {input_source}")
    typer.echo(f"Output file: {output_path}")
    typer.echo(f"Using timeout: {timeout} seconds")
    timeout_minutes = round(timeout / 60)  # Convert seconds to minutes for BaseLoader

    try:
        # Instantiate BaseLoader.
        # BaseLoader will determine the source (local/cloud) from the input string.
        # As requested, we explicitly set the source to "local" for the CLI.
        loader = BaseLoader(markdown_output=True, source="local", timeout_minutes=timeout_minutes)

        typer.echo(f"Using BaseLoader to process: {input_source}")

        # BaseLoader.get_text expects a list of inputs.
        # It will determine the input type and use the appropriate specific loader.
        result_dict = loader.get_text(input_list=[input_source])

        if result_dict and "text" in result_dict: # Check if BaseLoader returned a valid dictionary
            # Convert the result dictionary to a JSON string
            # ensure_ascii=False is good for UTF-8 handling in JSON.
            processed_content_json = json.dumps(result_dict, indent=4, ensure_ascii=False)

            # Write the JSON content to the output file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(processed_content_json, encoding='utf-8')

            typer.secho(f"Result successfully written as JSON to: {output_path}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Error: BaseLoader failed to process '{input_source}' or returned an empty/invalid result structure.", fg=typer.colors.RED, err=True)
            sys.exit(1)

        typer.echo("Processing completed.")

    except EmptyDocument as e:
        typer.secho(f"Processing Warning: The document appears to be empty or lacks extractable content. Reason: {e.message}", fg=typer.colors.YELLOW, err=True)
        if sentry_sdk:
            sentry_sdk.flush()
        sys.exit(1)
    except ConversionError as e:
        typer.secho(f"File Conversion Error: Could not convert the input file. This may require system dependencies like LibreOffice. Details: {e.message}", fg=typer.colors.RED, err=True)
        if sentry_sdk:
            sentry_sdk.flush()
        sys.exit(1)
    except FileNotFoundError:
        # This can be raised if a local file path is incorrect.
        typer.secho(f"Error: Input file not found at '{input_source}'. Please check the path.", fg=typer.colors.RED, err=True)
        if sentry_sdk:
            sentry_sdk.flush()
        sys.exit(1)
    except PermissionError:
         typer.secho(f"Error: Permission denied. Could not read '{input_source}' or write to '{output_path}'.", fg=typer.colors.RED, err=True)
         if sentry_sdk:
            sentry_sdk.flush()
         sys.exit(1)
    except Exception as e: # Catch-all for other errors from BaseLoader or its sub-loaders
        error_details = {
            'message': getattr(e, 'message', str(e)),
            'code': getattr(e, 'code', None),
            'status': getattr(e, 'status', None)
        }
        # Filter out None values to keep the JSON clean
        filtered_error_details = {k: v for k, v in error_details.items() if v is not None}
        error_json = json.dumps(filtered_error_details, ensure_ascii=False)
        typer.secho(error_json, fg=typer.colors.RED, err=True)
        typer.echo(error_json)
        
        # For debugging, you might want to print the full traceback:
        # import traceback
        # traceback.print_exc()
        if sentry_sdk:
            sentry_sdk.flush()
        sys.exit(1)

if __name__ == "__main__":
    app()