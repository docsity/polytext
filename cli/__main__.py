# polytext_cli.py
import typer
from pathlib import Path
import json # For JSON output
import os
import sys

# Aggiungi la directory principale del progetto al sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import BaseLoader instead of specific loaders for the main command logic
from polytext.loader.base import BaseLoader

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
    )
):
    """
    Processes a local input file or a URL using BaseLoader
    and writes the result as JSON to an output file.
    """
    typer.echo("Starting processing...")
    typer.echo(f"Input source: {input_source}")
    typer.echo(f"Output file: {output_path}")

    try:
        # Instantiate BaseLoader.
        # As requested, set source to "local".
        # markdown_output=True is a common default from the original script.
        # temp_dir defaults to "temp" in BaseLoader.
        loader = BaseLoader(source="local", markdown_output=True)

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

    except FileNotFoundError as e:
        # This can be raised by BaseLoader if the input is not found or not recognized.
        typer.secho(f"Error: Input file/resource not found, not accessible, or type not supported by BaseLoader: '{input_source}'. Details: {e}", fg=typer.colors.RED, err=True)
        sys.exit(1)
    except PermissionError:
         typer.secho(f"Error: Permission denied while accessing a file or directory.", fg=typer.colors.RED, err=True)
         sys.exit(1)
    except Exception as e: # Catch-all for other errors from BaseLoader or its sub-loaders
        typer.secho(f"An unexpected error occurred during processing: {e}", fg=typer.colors.RED, err=True)
        # For debugging, you might want to print the full traceback:
        # import traceback
        # traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    app()