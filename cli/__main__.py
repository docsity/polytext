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

def get_loader(timeout: int, note_id: int, input_source_id: int) -> BaseLoader:
	timeout_minutes = round(timeout / 60)
	return BaseLoader(
		markdown_output=True, 
		source="local", 
		timeout_minutes=timeout_minutes, 
		note_id=note_id, 
		input_source_id=input_source_id
	)


@app.command()
def transcript(
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
	),
	note_id: int = typer.Option(
		None,
		"--note_id",
		"-n",
		help="(Internal use) Note ID for tracking purposes."
	),
	input_source_id: int = typer.Option(
		None,
		"--input_source_id",
		"-i",
		help="(Internal use) Input Source ID for tracking purposes."
	)
):
	"""
	Transcript a local input file or a URL using BaseLoader
	and writes the result as JSON to an output file.
	"""
	typer.echo("Starting transcript...")
	typer.echo(f"Input source: {input_source}")
	typer.echo(f"Output file: {output_path}")
	typer.echo(f"Using timeout: {timeout} seconds")
	timeout_minutes = round(timeout / 60)  # Convert seconds to minutes for BaseLoader

	try:
		# Instantiate BaseLoader.
		# BaseLoader will determine the source (local/cloud) from the input string.
		# As requested, we explicitly set the source to "local" for the CLI.
		loader = BaseLoader(markdown_output=True, source="local", timeout_minutes=timeout_minutes, note_id=note_id, input_source_id=input_source_id)

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

	except Exception as e:
		handle_exception(e, input_source, output_path)

@app.command()
def faircopy(
	input_source: Path = typer.Argument(
		...,
		exists=True, file_okay=True, dir_okay=False, resolve_path=True,
		help="Path to the local transcript input file"
	),
	output_path: Path = typer.Argument(
		...,
		file_okay=True, dir_okay=False, writable=True, resolve_path=True,
		help="Path where to write the processing result as JSON."
	),
	chapters: bool = typer.Option(
		True, 
		"--chapters/--no-chapters", 
		help="Turn chaptering on or off."
	),
	timeout: int = typer.Option(
		300,
		"--timeout",
		"-t",
		help="Timeout for processing operations in seconds. Defaults to 300 (5 minutes)."
	),
	note_id: int = typer.Option(
		None,
		"--note_id",
		"-n",
		help="(Internal use) Note ID for tracking purposes."
	),
	input_source_id: int = typer.Option(
		None,
		"--input_source_id",
		"-i",
		help="(Internal use) Input Source ID for tracking purposes."
	)
):

	"""
	Generate a fair copy from transcript local input file using BaseLoader
	and writes the result as JSON to an output file.
	"""
	typer.echo("Starting fairCopy...")
	typer.echo(f"Input source: {input_source}")
	typer.echo(f"Output file: {output_path}")
	typer.echo(f"Using timeout: {timeout} seconds")
	timeout_minutes = round(timeout / 60)  # Convert seconds to minutes for BaseLoader

	try:
		transcript_text = input_source.read_text(encoding='utf-8')
		loader = BaseLoader(source="local", timeout_minutes=timeout_minutes, note_id=note_id, input_source_id=input_source_id)
		
		result_dict = loader.get_beautiful_text(input_list=[transcript_text], active_chapters=chapters)

		if result_dict:
			processed_content_json = json.dumps(result_dict, indent=4, ensure_ascii=False)
			output_path.parent.mkdir(parents=True, exist_ok=True)
			output_path.write_text(processed_content_json, encoding='utf-8')
			typer.secho(f"Beautiful text saved to: {output_path}", fg=typer.colors.GREEN)
		else:
			typer.secho("Error: get_beautiful_text returned an empty result.", fg=typer.colors.RED, err=True)
			sys.exit(1)

	except Exception as e:
		handle_exception(e, input_source, output_path)



def handle_exception(e, input_source, output_path):
	"""Helper per centralizzare la gestione errori."""
	if isinstance(e, EmptyDocument):
		typer.secho(f"Processing Warning: The document appears to be empty or lacks extractable content. Reason: {e.message}", fg=typer.colors.YELLOW, err=True)
	elif isinstance(e, ConversionError):
		typer.secho(f"File Conversion Error: Could not convert the input file. This may require system dependencies like LibreOffice. Details: {e.message}", fg=typer.colors.RED, err=True)
	elif isinstance(e, FileNotFoundError):
		typer.secho(f"Error: Input file not found at '{input_source}'. Please check the path.", fg=typer.colors.RED, err=True)
	elif isinstance(e, PermissionError):
		typer.secho(f"Error: Permission denied. Could not read '{input_source}' or write to '{output_path}'.", fg=typer.colors.RED, err=True)
	else:
		error_details = {
			'message': getattr(e, 'message', str(e)),
			'code': getattr(e, 'code', None),
			'status': getattr(e, 'status', None)
		}
		# Filter out None values to keep the JSON clean
		filtered = {k: v for k, v in error_details.items() if v is not None}
		typer.secho(json.dumps(filtered, ensure_ascii=False), fg=typer.colors.RED, err=True)

	# For debugging, you might want to print the full traceback:
	# import traceback
	# traceback.print_exc()
	if sentry_sdk:
		sentry_sdk.flush()
	sys.exit(1)

if __name__ == "__main__":
	app()